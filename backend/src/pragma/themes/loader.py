# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Filesystem theme discovery helpers for the Pragma theme runtime.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from pragma.errors import ConfigError, ThemeError
from pragma.themes.manifest import ThemeManifest

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DiscoveredTheme:
    """Resolved filesystem data for a discovered theme.

    Args:
        manifest: Validated theme manifest.
        root_path: Absolute theme root path.
        manifest_path: Absolute theme manifest path.
        templates_path: Absolute template root path.
        static_path: Absolute static asset root path.

    Returns:
        None.

    Raises:
        None.
    """

    manifest: ThemeManifest
    root_path: Path
    manifest_path: Path
    templates_path: Path
    static_path: Path


def discover_themes(root_path: Path) -> dict[str, DiscoveredTheme]:
    """Discover valid themes beneath the configured theme root.

    Args:
        root_path: Configured root directory for discoverable themes.

    Returns:
        dict[str, DiscoveredTheme]: Discovered themes keyed by manifest id.

    Raises:
        ConfigError: If the configured theme root is not a directory.
    """

    resolved_root = root_path.resolve()
    if not resolved_root.exists():
        return {}
    if not resolved_root.is_dir():
        raise ConfigError(
            detail='Configured theme root is not a directory',
            code='THEME_ROOT_INVALID',
        )

    discovered: dict[str, DiscoveredTheme] = {}
    for candidate in sorted(resolved_root.iterdir()):
        if not candidate.is_dir():
            continue

        resolved_candidate = candidate.resolve()
        if not _is_within_root(resolved_root, resolved_candidate):
            logger.warning(
                'Skipping theme directory %s because it escapes the configured theme root',
                candidate,
            )
            continue

        manifest_path = resolved_candidate / 'theme.json'
        if not manifest_path.is_file():
            continue

        try:
            manifest = load_theme_manifest(manifest_path)
            theme = DiscoveredTheme(
                manifest=manifest,
                root_path=resolved_candidate,
                manifest_path=manifest_path,
                templates_path=resolve_theme_relative_path(
                    resolved_candidate,
                    PurePosixPath(manifest.templates_dir),
                    code='THEME_MANIFEST_INVALID',
                    label='templates directory',
                ),
                static_path=resolve_theme_relative_path(
                    resolved_candidate,
                    PurePosixPath(manifest.static_dir),
                    code='THEME_MANIFEST_INVALID',
                    label='static directory',
                ),
            )
        except ThemeError as exc:
            logger.warning('Skipping invalid theme at %s: %s', candidate, exc.detail)
            continue

        if manifest.id in discovered:
            logger.warning(
                'Skipping duplicate theme id %s at %s; first definition from %s wins',
                manifest.id,
                resolved_candidate,
                discovered[manifest.id].root_path,
            )
            continue

        discovered[manifest.id] = theme

    return discovered


def load_theme_manifest(manifest_path: Path) -> ThemeManifest:
    """Load and validate a theme manifest from disk.

    Args:
        manifest_path: Absolute path to the manifest file.

    Returns:
        ThemeManifest: Validated theme manifest model.

    Raises:
        ThemeError: If the manifest cannot be read or validated.
    """

    try:
        payload = manifest_path.read_text(encoding='utf-8')
    except OSError as exc:
        raise ThemeError(
            detail=f'Unable to read theme manifest at {manifest_path}',
            code='THEME_MANIFEST_READ_FAILED',
        ) from exc

    try:
        return ThemeManifest.model_validate_json(payload)
    except ValidationError as exc:
        raise ThemeError(
            detail=f'Invalid theme manifest at {manifest_path}',
            code='THEME_MANIFEST_INVALID',
        ) from exc


def resolve_theme_relative_path(
    root_path: Path,
    relative_path: PurePosixPath,
    *,
    code: str,
    label: str,
) -> Path:
    """Resolve a relative theme-owned path and enforce root containment.

    Args:
        root_path: Absolute theme root path.
        relative_path: Relative path beneath the theme root.
        code: Stable machine-readable error code.
        label: Human-readable label for the failing path.

    Returns:
        Path: Absolute resolved path within the theme root.

    Raises:
        ThemeError: If the resolved path escapes the theme root.
    """

    candidate = (root_path / relative_path.as_posix()).resolve()
    if not _is_within_root(root_path, candidate):
        raise ThemeError(
            detail=f'Theme {label} escaped the theme root',
            code=code,
        )
    return candidate


def _is_within_root(root_path: Path, candidate: Path) -> bool:
    """Return whether a candidate path stays within a configured root.

    Args:
        root_path: Absolute root path.
        candidate: Candidate path to test.

    Returns:
        bool: True when the candidate remains within the root.

    Raises:
        None.
    """

    return root_path == candidate or root_path in candidate.parents
