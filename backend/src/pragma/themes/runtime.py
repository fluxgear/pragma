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
            cache_size=0,
        )

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
        ).as_posix()
        try:
            return self._environment.get_template(normalized)
        except ThemeError:
            raise
        except TemplateNotFound as exc:
            raise ThemeError(
                detail=(
                    f'Theme template {normalized} was not found in the active or default '
                    'theme'
                ),
                code='THEME_TEMPLATE_NOT_FOUND',
            ) from exc

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

        template = self.get_template(name)
        return template.render({} if context is None else context)

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
    ) -> tuple[ResolvedThemePath, ...]:
        """Resolve existing theme-owned files for a relative lookup path.

        Args:
            relative_path: Relative lookup path.
            path_getter: Callable returning the owning base directory for a theme.
            code: Stable machine-readable error code for containment failures.

        Returns:
            tuple[ResolvedThemePath, ...]: Existing candidate paths.

        Raises:
            ThemeError: If no usable fallback themes exist or containment fails.
        """

        resolved: list[ResolvedThemePath] = []
        last_path_error: ThemeError | None = None
        for theme in self._candidate_themes():
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

    def __init__(self, runtime: ThemeRuntime) -> None:
        self._runtime = runtime

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
        ).as_posix()
        last_syntax_error: TemplateSyntaxError | None = None
        last_read_error: OSError | None = None

        for candidate in self._runtime.iter_template_candidates(normalized):
            try:
                source = candidate.filesystem_path.read_text(encoding='utf-8')
            except OSError as exc:
                logger.warning(
                    'Skipping unreadable theme template %s from theme %s: %s',
                    candidate.relative_path,
                    candidate.theme_id,
                    exc,
                )
                last_read_error = exc
                continue

            template_path = candidate.filesystem_path
            try:
                code = environment.compile(source, normalized, str(template_path))
            except TemplateSyntaxError as exc:
                logger.warning(
                    'Skipping invalid theme template %s from theme %s: %s',
                    candidate.relative_path,
                    candidate.theme_id,
                    exc,
                )
                last_syntax_error = exc
                continue

            def uptodate(path: Path = template_path) -> bool:
                """Report whether the compiled template source is unchanged.

                Args:
                    path: Filesystem path for the compiled template.

                Returns:
                    bool: True when the template source is unchanged.

                Raises:
                    None.
                """

                return path.is_file()

            return environment.template_class.from_code(
                environment,
                code,
                {} if globals is None else globals,
                uptodate,
            )

        if last_syntax_error is not None:
            raise ThemeError(
                detail=(
                    f'Theme template {normalized} could not be compiled in the active or '
                    'default theme'
                ),
                code='THEME_TEMPLATE_INVALID',
            ) from last_syntax_error
        if last_read_error is not None:
            raise ThemeError(
                detail=(
                    f'Theme template {normalized} could not be read from the active or '
                    'default theme'
                ),
                code='THEME_TEMPLATE_READ_FAILED',
            ) from last_read_error
        raise TemplateNotFound(normalized)

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
            candidate_themes = self._runtime._candidate_themes()
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
