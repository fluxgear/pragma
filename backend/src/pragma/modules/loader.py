# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Filesystem module-discovery helpers for Pragma's module runtime.

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

from pragma.errors import ConfigError, ModuleError
from pragma.modules.manifest import ModuleManifest

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DiscoveredModule:
    """Resolved filesystem data for a discovered module.

    Args:
        manifest: Validated module manifest.
        root_path: Absolute module root path.
        manifest_path: Absolute module manifest path.
        entrypoint_path: Absolute hook-entrypoint path.

    Returns:
        None.

    Raises:
        None.
    """

    manifest: ModuleManifest
    root_path: Path
    manifest_path: Path
    entrypoint_path: Path


def discover_modules(root_path: Path) -> dict[str, DiscoveredModule]:
    """Discover valid module manifests beneath the configured module root.

    Args:
        root_path: Configured root directory for discoverable modules.

    Returns:
        dict[str, DiscoveredModule]: Discovered modules keyed by module id.

    Raises:
        ConfigError: If the configured module root is not a directory.
    """

    resolved_root = root_path.resolve()
    if not resolved_root.exists():
        return {}
    if not resolved_root.is_dir():
        raise ConfigError(
            detail='Configured module root is not a directory',
            code='MODULE_ROOT_INVALID',
        )

    discovered: dict[str, DiscoveredModule] = {}
    for candidate in sorted(resolved_root.iterdir()):
        if not candidate.is_dir():
            continue

        resolved_candidate = candidate.resolve()
        if not _is_within_root(resolved_root, resolved_candidate):
            logger.warning(
                'Skipping module directory %s because it escapes the configured module root',
                candidate,
                extra={'module_code': 'MODULE_ROOT_ESCAPE'},
            )
            continue

        manifest_path = resolved_candidate / 'module.json'
        if not manifest_path.is_file():
            continue

        try:
            manifest = load_module_manifest(manifest_path)
            module = DiscoveredModule(
                manifest=manifest,
                root_path=resolved_candidate,
                manifest_path=manifest_path,
                entrypoint_path=resolve_module_relative_path(
                    resolved_candidate,
                    PurePosixPath(manifest.entrypoint),
                    code='MODULE_MANIFEST_INVALID',
                    label='entrypoint',
                ),
            )
            if not module.entrypoint_path.is_file():
                raise ModuleError(
                    detail=f'Module entrypoint is missing at {module.entrypoint_path}',
                    code='MODULE_ENTRYPOINT_NOT_FOUND',
                    status_code=500,
                )
        except ModuleError as exc:
            logger.warning(
                'Skipping invalid module at %s: %s',
                candidate,
                exc.detail,
                extra={'module_code': exc.code},
            )
            continue

        if manifest.id in discovered:
            logger.warning(
                'Skipping duplicate module id %s at %s; first definition from %s wins',
                manifest.id,
                resolved_candidate,
                discovered[manifest.id].root_path,
                extra={'module_code': 'MODULE_DUPLICATE_ID'},
            )
            continue

        discovered[manifest.id] = module

    return discovered


def load_module_manifest(manifest_path: Path) -> ModuleManifest:
    """Load and validate a module manifest from disk.

    Args:
        manifest_path: Absolute path to the manifest file.

    Returns:
        ModuleManifest: Validated module manifest model.

    Raises:
        ModuleError: If the manifest cannot be read or validated.
    """

    try:
        payload = manifest_path.read_text(encoding='utf-8')
    except OSError as exc:
        raise ModuleError(
            detail=f'Unable to read module manifest at {manifest_path}',
            code='MODULE_MANIFEST_READ_FAILED',
            status_code=500,
        ) from exc

    try:
        return ModuleManifest.model_validate_json(payload)
    except ValidationError as exc:
        raise ModuleError(
            detail=f'Invalid module manifest at {manifest_path}',
            code='MODULE_MANIFEST_INVALID',
            status_code=400,
        ) from exc


def resolve_module_relative_path(
    root_path: Path,
    relative_path: PurePosixPath,
    *,
    code: str,
    label: str,
) -> Path:
    """Resolve a relative module-owned path and enforce root containment.

    Args:
        root_path: Absolute module root path.
        relative_path: Relative path beneath the module root.
        code: Stable machine-readable error code.
        label: Human-readable label for the failing path.

    Returns:
        Path: Absolute resolved path within the module root.

    Raises:
        ModuleError: If the resolved path escapes the module root.
    """

    candidate = (root_path / relative_path.as_posix()).resolve()
    if not _is_within_root(root_path, candidate):
        raise ModuleError(
            detail=f'Module {label} escaped the module root',
            code=code,
            status_code=400,
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
