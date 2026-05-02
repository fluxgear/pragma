# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Theme runtime services for discovery, resolution, and fallback behavior.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from jinja2 import (
    BaseLoader,
    Environment,
    Template,
    TemplateNotFound,
    TemplateSyntaxError,
    select_autoescape,
)

from pragma.config import Settings
from pragma.errors import ThemeError
from pragma.themes.loader import (
    DiscoveredTheme,
    discover_themes,
    resolve_theme_relative_path,
)
from pragma.themes.manifest import ThemeManifest

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ResolvedThemePath:
    """Resolved filesystem path for a theme-owned artifact.

    Args:
        theme_id: Theme identifier that satisfied the lookup.
        relative_path: Relative lookup path.
        filesystem_path: Absolute filesystem path.

    Returns:
        None.

    Raises:
        None.
    """

    theme_id: str
    relative_path: str
    filesystem_path: Path


class ThemeRuntime:
    """Runtime theme catalog and resolution service.

    Args:
        settings: Application settings.

    Returns:
        None.

    Raises:
        ConfigError: If the configured theme root is invalid.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._themes = discover_themes(settings.theme_root_path)
        self._environment = Environment(
            loader=_ThemeTemplateLoader(self),
            autoescape=select_autoescape(enabled_extensions=('html', 'xml')),
            auto_reload=True,
            cache_size=400,
        )
        self._environment_overlays: dict[tuple[str, ...], Environment] = {}

    @property
    def environment(self) -> Environment:
        """Return the backing Jinja environment for theme templates.

        Args:
            None.

        Returns:
            Environment: Jinja environment with theme-aware loading.

        Raises:
            None.
        """

        return self._environment

    def list_themes(self) -> tuple[ThemeManifest, ...]:
        """Return discovered theme manifests.

        Args:
            None.

        Returns:
            tuple[ThemeManifest, ...]: Discovered theme manifests.

        Raises:
            None.
        """

        return tuple(theme.manifest for theme in self._themes.values())

    def resolve_active_theme(self) -> DiscoveredTheme:
        """Resolve the effective active theme with default fallback.

        Args:
            None.

        Returns:
            DiscoveredTheme: Active theme if available, otherwise the default theme.

        Raises:
            ThemeError: If neither the active nor default theme is available.
        """

        return self._candidate_themes()[0]

    def resolve_default_theme(self) -> DiscoveredTheme:
        """Resolve the configured default theme.

        Args:
            None.

        Returns:
            DiscoveredTheme: Configured default theme.

        Raises:
            ThemeError: If the configured default theme is unavailable.
        """

        default_theme = self._themes.get(self._settings.theme_default_id)
        if default_theme is None:
            raise ThemeError(
                detail='Configured default theme could not be resolved',
                code='THEME_DEFAULT_NOT_FOUND',
            )
        return default_theme

    def resolve_template_path(self, name: str) -> ResolvedThemePath:
        """Resolve a template path using active-first fallback order.

        Args:
            name: Relative template lookup path.

        Returns:
            ResolvedThemePath: Resolved template path metadata.

        Raises:
            ThemeError: If the template cannot be resolved.
        """

        candidates = self.iter_template_candidates(name)
        if not candidates:
            normalized = _normalize_lookup_path(
                name,
                kind='template',
                code='THEME_TEMPLATE_PATH_INVALID',
            )
            raise ThemeError(
                detail=(
                    f'Theme template {normalized.as_posix()} was not found in the active '
                    'or default theme'
                ),
                code='THEME_TEMPLATE_NOT_FOUND',
            )
        return candidates[0]

    def iter_template_candidates(self, name: str) -> tuple[ResolvedThemePath, ...]:
        """Return existing template candidates in deterministic fallback order.

        Args:
            name: Relative template lookup path.

        Returns:
            tuple[ResolvedThemePath, ...]: Existing template candidates.

        Raises:
            ThemeError: If the lookup path is invalid or no fallback themes exist.
        """

        normalized = _normalize_lookup_path(
            name,
            kind='template',
            code='THEME_TEMPLATE_PATH_INVALID',
        )
        return self._resolve_existing_paths(
            normalized,
            path_getter=lambda theme: theme.templates_path,
            code='THEME_TEMPLATE_PATH_INVALID',
        )

    def resolve_asset_path(self, name: str) -> ResolvedThemePath:
        """Resolve a static asset path using active-first fallback order.

        Args:
            name: Relative static asset lookup path.

        Returns:
            ResolvedThemePath: Resolved static asset path metadata.

        Raises:
            ThemeError: If the asset cannot be resolved.
        """

        normalized = _normalize_lookup_path(
            name,
            kind='asset',
            code='THEME_ASSET_PATH_INVALID',
        )
        candidates = self._resolve_existing_paths(
            normalized,
            path_getter=lambda theme: theme.static_path,
            code='THEME_ASSET_PATH_INVALID',
        )
        if not candidates:
            raise ThemeError(
                detail=(
                    f'Theme asset {normalized.as_posix()} was not found in the active or '
                    'default theme'
                ),
                code='THEME_ASSET_NOT_FOUND',
            )
        return candidates[0]

    def get_template(self, name: str) -> Template:
        """Load a compiled Jinja template with default-theme fallback.

        Args:
            name: Relative template lookup path.

        Returns:
            Template: Compiled Jinja template.

        Raises:
            ThemeError: If the template cannot be loaded or compiled.
        """

        normalized = _normalize_lookup_path(
            name,
            kind='template',
            code='THEME_TEMPLATE_PATH_INVALID',
        )
        attempts = self._iter_template_attempts(normalized)
        if not attempts:
            raise self._template_not_found_error(normalized)

        last_error: ThemeError | None = None
        for resolved_path, candidate_themes in attempts:
            environment = self._build_environment(candidate_themes)
            try:
                return environment.get_template(normalized.as_posix())
            except TemplateNotFound as exc:
                last_error = self._template_not_found_error(normalized)
                logger.warning(
                    'Skipping missing theme template %s from theme %s: %s',
                    resolved_path.relative_path,
                    resolved_path.theme_id,
                    exc,
                )
            except ThemeError as exc:
                logger.warning(
                    'Skipping unusable theme template %s from theme %s: %s',
                    resolved_path.relative_path,
                    resolved_path.theme_id,
                    exc.detail,
                )
                last_error = exc

        if last_error is not None:
            raise last_error
        raise self._template_not_found_error(normalized)

    def render_template(self, name: str, context: dict[str, Any] | None = None) -> str:
        """Render a template to a string.

        Args:
            name: Relative template lookup path.
            context: Render context values.

        Returns:
            str: Rendered template output.

        Raises:
            ThemeError: If the template cannot be resolved or compiled.
        """

        normalized = _normalize_lookup_path(
            name,
            kind='template',
            code='THEME_TEMPLATE_PATH_INVALID',
        )
        attempts = self._iter_template_attempts(normalized)
        if not attempts:
            raise self._template_not_found_error(normalized)

        render_context = {} if context is None else context
        last_error: ThemeError | None = None
        for resolved_path, candidate_themes in attempts:
            environment = self._build_environment(candidate_themes)
            try:
                template = environment.get_template(normalized.as_posix())
                return template.render(render_context)
            except TemplateNotFound as exc:
                last_error = self._template_not_found_error(normalized)
                logger.warning(
                    'Skipping missing theme template %s from theme %s: %s',
                    resolved_path.relative_path,
                    resolved_path.theme_id,
                    exc,
                )
            except ThemeError as exc:
                logger.warning(
                    'Skipping unusable theme template %s from theme %s: %s',
                    resolved_path.relative_path,
                    resolved_path.theme_id,
                    exc.detail,
                )
                last_error = exc
            except Exception as exc:
                logger.warning(
                    'Skipping render-failed theme template %s from theme %s: %s',
                    resolved_path.relative_path,
                    resolved_path.theme_id,
                    exc,
                )
                last_error = ThemeError(
                    detail=(
                        f'Theme template {normalized.as_posix()} could not be rendered in '
                        'the active or default theme'
                    ),
                    code='THEME_TEMPLATE_RENDER_FAILED',
                )

        if last_error is not None:
            raise last_error
        raise self._template_not_found_error(normalized)

    def _build_environment(
        self,
        candidate_themes: tuple[DiscoveredTheme, ...] | None = None,
    ) -> Environment:
        """Build a Jinja environment for a specific theme fallback chain.

        Args:
            candidate_themes: Ordered fallback chain for template resolution.

        Returns:
            Environment: Jinja environment bound to the requested theme chain.

        Raises:
            None.
        """

        if candidate_themes is None:
            return self._environment

        cache_key = tuple(theme.manifest.id for theme in candidate_themes)
        environment = self._environment_overlays.get(cache_key)
        if environment is None:
            environment = self._environment.overlay(
                loader=_ThemeTemplateLoader(self, candidate_themes)
            )
            self._environment_overlays[cache_key] = environment
        return environment

    def _iter_template_attempts(
        self,
        relative_path: PurePosixPath,
    ) -> tuple[tuple[ResolvedThemePath, tuple[DiscoveredTheme, ...]], ...]:
        """Return root-template attempts with theme-local fallback chains.

        Args:
            relative_path: Normalized relative template lookup path.

        Returns:
            tuple[tuple[ResolvedThemePath, tuple[DiscoveredTheme, ...]], ...]:
                Resolution attempts ordered from active theme to default theme.

        Raises:
            ThemeError: If no usable active/default theme exists.
        """

        attempts: list[tuple[ResolvedThemePath, tuple[DiscoveredTheme, ...]]] = []
        candidate_themes = self._candidate_themes()
        for index, theme in enumerate(candidate_themes):
            resolved = self._resolve_existing_paths(
                relative_path,
                path_getter=lambda candidate: candidate.templates_path,
                code='THEME_TEMPLATE_PATH_INVALID',
                themes=(theme,),
            )
            if not resolved:
                continue
            attempts.append((resolved[0], candidate_themes[index:]))
        return tuple(attempts)


    def _compile_template(
        self,
        environment: Environment,
        name: str,
        resolved_path: ResolvedThemePath,
        globals: dict[str, Any] | None = None,
        *,
        force_reload: bool = False,
    ) -> Template:
        """Compile a resolved template path inside the provided environment.

        Args:
            environment: Jinja environment that will own the compiled template.
            name: Normalized template lookup path.
            resolved_path: Resolved template metadata.
            globals: Optional template globals.
            force_reload: Whether the returned template should be reloaded on next use.

        Returns:
            Template: Compiled template bound to the provided environment.

        Raises:
            ThemeError: If the template cannot be read or compiled.
        """

        try:
            source = resolved_path.filesystem_path.read_text(encoding='utf-8')
            source_stat = resolved_path.filesystem_path.stat()
        except OSError as exc:
            raise ThemeError(
                detail=(
                    f'Theme template {name} could not be read from the active or default '
                    'theme'
                ),
                code='THEME_TEMPLATE_READ_FAILED',
            ) from exc

        try:
            code = environment.compile(
                source,
                name,
                str(resolved_path.filesystem_path),
            )
        except TemplateSyntaxError as exc:
            raise ThemeError(
                detail=(
                    f'Theme template {name} could not be compiled in the active or default '
                    'theme'
                ),
                code='THEME_TEMPLATE_INVALID',
            ) from exc

        def uptodate(
            path: Path = resolved_path.filesystem_path,
            expected_mtime_ns: int = source_stat.st_mtime_ns,
            expected_size: int = source_stat.st_size,
        ) -> bool:
            """Report whether the compiled template source is unchanged.

            Args:
                path: Filesystem path for the compiled template.
                expected_mtime_ns: Source mtime captured at compile time.
                expected_size: Source size captured at compile time.

            Returns:
                bool: True when the template source is unchanged.

            Raises:
                None.
            """

            if force_reload:
                return False
            try:
                current_stat = path.stat()
            except OSError:
                return False
            return (
                current_stat.st_mtime_ns == expected_mtime_ns
                and current_stat.st_size == expected_size
            )

        return environment.template_class.from_code(
            environment,
            code,
            {} if globals is None else globals,
            uptodate,
        )

    def _template_not_found_error(self, relative_path: PurePosixPath) -> ThemeError:
        """Build a stable not-found error for unresolved templates.

        Args:
            relative_path: Normalized relative template lookup path.

        Returns:
            ThemeError: Stable template-not-found error.

        Raises:
            None.
        """

        return ThemeError(
            detail=(
                f'Theme template {relative_path.as_posix()} was not found in the active or '
                'default theme'
            ),
            code='THEME_TEMPLATE_NOT_FOUND',
        )

    def _candidate_themes(self) -> tuple[DiscoveredTheme, ...]:
        """Return fallback themes in deterministic resolution order.

        Args:
            None.

        Returns:
            tuple[DiscoveredTheme, ...]: Resolution-ordered themes.

        Raises:
            ThemeError: If no usable active/default theme exists.
        """

        active_theme = self._themes.get(self._settings.theme_active_id)
        default_theme = self._themes.get(self._settings.theme_default_id)
        ordered: list[DiscoveredTheme] = []
        if active_theme is not None:
            ordered.append(active_theme)
        if default_theme is not None and default_theme not in ordered:
            ordered.append(default_theme)
        if ordered:
            return tuple(ordered)
        raise ThemeError(
            detail='Neither the configured active nor default theme is available',
            code='THEME_FALLBACK_UNAVAILABLE',
        )

    def _resolve_existing_paths(
        self,
        relative_path: PurePosixPath,
        *,
        path_getter: Callable[[DiscoveredTheme], Path],
        code: str,
        themes: tuple[DiscoveredTheme, ...] | None = None,
    ) -> tuple[ResolvedThemePath, ...]:
        """Resolve existing theme-owned files for a relative lookup path.

        Args:
            relative_path: Relative lookup path.
            path_getter: Callable returning the owning base directory for a theme.
            code: Stable machine-readable error code for containment failures.
            themes: Optional explicit theme chain override.

        Returns:
            tuple[ResolvedThemePath, ...]: Existing candidate paths.

        Raises:
            ThemeError: If no usable fallback themes exist or containment fails.
        """

        resolved: list[ResolvedThemePath] = []
        last_path_error: ThemeError | None = None
        selected_themes = self._candidate_themes() if themes is None else themes
        for theme in selected_themes:
            try:
                candidate = resolve_theme_relative_path(
                    path_getter(theme),
                    relative_path,
                    code=code,
                    label='lookup path',
                )
            except ThemeError as exc:
                logger.warning(
                    'Skipping invalid theme lookup path %s from theme %s: %s',
                    relative_path.as_posix(),
                    theme.manifest.id,
                    exc.detail,
                )
                last_path_error = exc
                continue
            if candidate.is_file():
                resolved.append(
                    ResolvedThemePath(
                        theme_id=theme.manifest.id,
                        relative_path=relative_path.as_posix(),
                        filesystem_path=candidate,
                    )
                )
        if resolved:
            return tuple(resolved)
        if last_path_error is not None:
            raise last_path_error
        return ()


class _ThemeTemplateLoader(BaseLoader):
    """Jinja loader with active-theme and default-theme fallback semantics.

    Args:
        runtime: Theme runtime owning discovery and resolution state.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        runtime: ThemeRuntime,
        candidate_themes: tuple[DiscoveredTheme, ...] | None = None,
    ) -> None:
        self._runtime = runtime
        self._candidate_themes = candidate_themes

    def _selected_themes(self) -> tuple[DiscoveredTheme, ...]:
        """Return the loader's effective fallback chain.

        Args:
            None.

        Returns:
            tuple[DiscoveredTheme, ...]: Effective theme chain for this loader.

        Raises:
            ThemeError: If no usable active/default theme exists.
        """

        if self._candidate_themes is not None:
            return self._candidate_themes
        return self._runtime._candidate_themes()

    def load(
        self,
        environment: Environment,
        name: str,
        globals: dict[str, Any] | None = None,
    ) -> Template:
        """Load a template with compile-time fallback to the default theme.

        Args:
            environment: Jinja environment requesting the template.
            name: Relative template lookup path.
            globals: Template globals from Jinja.

        Returns:
            Template: Compiled Jinja template.

        Raises:
            TemplateNotFound: If no candidate template exists.
            ThemeError: If all candidate templates fail to read or compile.
        """

        normalized = _normalize_lookup_path(
            name,
            kind='template',
            code='THEME_TEMPLATE_PATH_INVALID',
        )
        try:
            candidate_themes = self._selected_themes()
        except ThemeError as exc:
            raise TemplateNotFound(normalized.as_posix()) from exc

        last_error: ThemeError | None = None
        candidates = self._runtime._resolve_existing_paths(
            normalized,
            path_getter=lambda theme: theme.templates_path,
            code='THEME_TEMPLATE_PATH_INVALID',
            themes=candidate_themes,
        )
        for candidate in candidates:
            try:
                return self._runtime._compile_template(
                    environment,
                    normalized.as_posix(),
                    candidate,
                    globals,
                    force_reload=last_error is not None,
                )
            except ThemeError as exc:
                logger.warning(
                    'Skipping unusable theme template %s from theme %s: %s',
                    candidate.relative_path,
                    candidate.theme_id,
                    exc.detail,
                )
                last_error = exc

        if last_error is not None:
            raise last_error
        raise TemplateNotFound(normalized.as_posix())

    def list_templates(self) -> list[str]:
        """List all discoverable templates across active/default theme directories.

        Args:
            None.

        Returns:
            list[str]: Sorted unique template names.

        Raises:
            None.
        """

        names: set[str] = set()
        try:
            candidate_themes = self._selected_themes()
        except ThemeError:
            return []

        for theme in candidate_themes:
            if not theme.templates_path.is_dir():
                continue
            for candidate in theme.templates_path.rglob('*'):
                if not candidate.is_file():
                    continue
                relative_name = candidate.relative_to(theme.templates_path).as_posix()
                names.add(relative_name)
        return sorted(names)


def build_theme_runtime(settings: Settings) -> ThemeRuntime:
    """Build a theme runtime from application settings.

    Args:
        settings: Application settings.

    Returns:
        ThemeRuntime: Configured runtime theme service.

    Raises:
        ConfigError: If theme configuration is invalid.
    """

    return ThemeRuntime(settings)


def _normalize_lookup_path(name: str, *, kind: str, code: str) -> PurePosixPath:
    """Normalize and validate a relative theme lookup path.

    Args:
        name: Raw template or asset lookup path.
        kind: Human-readable lookup kind.
        code: Stable machine-readable error code.

    Returns:
        PurePosixPath: Normalized relative lookup path.

    Raises:
        ThemeError: If the lookup path is empty, absolute, or escapes the theme root.
    """

    normalized = PurePosixPath(name.strip())
    if normalized.as_posix() in {'', '.'}:
        raise ThemeError(
            detail=f'Theme {kind} lookups must not be empty',
            code=code,
        )
    if normalized.is_absolute() or '..' in normalized.parts:
        raise ThemeError(
            detail=f'Theme {kind} lookups must remain within the theme root',
            code=code,
        )
    return normalized
