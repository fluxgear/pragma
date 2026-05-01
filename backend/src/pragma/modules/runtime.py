# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Runtime registry and dispatcher for trusted operator-installed backend modules.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, RLock
from time import perf_counter
from types import ModuleType
from typing import cast

from psycopg import Error as PsycopgError
from psycopg.errors import UndefinedTable

from pragma.config import Settings
from pragma.errors import ModuleError
from pragma.modules.loader import DiscoveredModule, discover_modules
from pragma.modules.manifest import ModuleHookEvent
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.modules import list_module_states

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ModuleSnapshot:
    """Materialized module state used by runtime and API responses.

    Args:
        module_id: Stable module identifier.
        name: Human-readable module name.
        version: Module version string from manifest metadata.
        order: Deterministic module ordering weight.
        enabled: Whether persisted state enables this module.
        loaded: Whether hook loading completed successfully.
        hooks: Sorted list of registered event names for the module.
        error_code: Optional structured load failure code.

    Returns:
        None.

    Raises:
        None.
    """

    module_id: str
    name: str
    version: str
    order: int
    enabled: bool
    loaded: bool
    hooks: tuple[str, ...]
    error_code: str | None


@dataclass(frozen=True, slots=True)
class _ModuleHookBinding:
    """Resolved event-hook binding for a loaded module.

    Args:
        module_id: Module identifier owning the hook.
        hook_name: Callable name in the module entrypoint.
        handler: Bound hook callable.

    Returns:
        None.

    Raises:
        None.
    """

    module_id: str
    hook_name: str
    handler: Callable[[Mapping[str, object]], None]


@dataclass(frozen=True, slots=True)
class _ModuleFileFingerprint:
    """Content metadata for a module-controlled file used by the load cache."""

    path: str
    mtime_ns: int
    size: int
    digest: str


@dataclass(frozen=True, slots=True)
class _ModuleEntrypointCacheKey:
    """Stable cache key for a trusted module entrypoint import."""

    module_id: str
    manifest: _ModuleFileFingerprint
    entrypoint: _ModuleFileFingerprint


class ModuleRuntime:
    """Manage module discovery, loading, and deterministic event dispatch.

    Args:
        settings: Application settings for module discovery.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = RLock()
        self._snapshots: dict[str, ModuleSnapshot] = {}
        self._bindings: dict[str, tuple[_ModuleHookBinding, ...]] = {
            event.value: tuple() for event in ModuleHookEvent
        }
        self._entrypoint_cache: dict[_ModuleEntrypointCacheKey, ModuleType] = {}

    def refresh(self, storage: DatabasePool) -> None:
        """Rebuild runtime module state from manifests and persisted flags.

        Args:
            storage: Initialized database pool manager.

        Returns:
            None.

        Raises:
            ModuleError: If persisted state cannot be loaded from storage.
        """

        discovered = discover_modules(self._settings.module_root_path)
        persisted_state = self._load_persisted_state(storage)

        snapshots: dict[str, ModuleSnapshot] = {}
        bindings: dict[str, list[_ModuleHookBinding]] = {
            event.value: [] for event in ModuleHookEvent
        }
        current_cache_keys: set[_ModuleEntrypointCacheKey] = set()

        ordered = sorted(
            discovered.values(),
            key=lambda item: (item.manifest.order, item.manifest.id),
        )
        for discovered_module in ordered:
            module_id = discovered_module.manifest.id
            enabled = bool(persisted_state.get(module_id, False))
            loaded = False
            hooks: tuple[str, ...] = tuple()
            error_code: str | None = None
            entrypoint_cache_key: _ModuleEntrypointCacheKey | None = None

            try:
                entrypoint_cache_key = self._build_entrypoint_cache_key(discovered_module)
                current_cache_keys.add(entrypoint_cache_key)
            except ModuleError as exc:
                if enabled:
                    error_code = exc.code
                    logger.warning(
                        'Module load failed',
                        extra={
                            'module_id': module_id,
                            'module_code': exc.code,
                        },
                    )

            if enabled and error_code is None and entrypoint_cache_key is not None:
                try:
                    resolved_bindings = self._load_module_hooks(
                        discovered_module,
                        entrypoint_cache_key,
                    )
                    loaded = True
                    hooks = tuple(sorted(resolved_bindings.keys()))
                    for event_name, binding in resolved_bindings.items():
                        bindings[event_name].append(binding)
                except ModuleError as exc:
                    error_code = exc.code
                    logger.warning(
                        'Module load failed',
                        extra={
                            'module_id': module_id,
                            'module_code': exc.code,
                        },
                    )
                except Exception:
                    error_code = 'MODULE_LOAD_FAILED'
                    logger.warning(
                        'Module load failed with an unexpected exception',
                        extra={
                            'module_id': module_id,
                            'module_code': 'MODULE_LOAD_FAILED',
                        },
                        exc_info=True,
                    )

            snapshots[module_id] = ModuleSnapshot(
                module_id=module_id,
                name=discovered_module.manifest.name,
                version=discovered_module.manifest.version,
                order=discovered_module.manifest.order,
                enabled=enabled,
                loaded=loaded,
                hooks=hooks,
                error_code=error_code,
            )

        frozen_bindings = {
            event_name: tuple(event_bindings)
            for event_name, event_bindings in bindings.items()
        }
        with self._lock:
            self._snapshots = snapshots
            self._bindings = frozen_bindings
            self._prune_entrypoint_cache_locked(current_cache_keys)

    def list_snapshots(self) -> list[ModuleSnapshot]:
        """Return discovered module states in deterministic runtime order.

        Args:
            None.

        Returns:
            list[ModuleSnapshot]: Ordered module state snapshots.

        Raises:
            None.
        """

        with self._lock:
            snapshots = list(self._snapshots.values())
        return sorted(snapshots, key=lambda item: (item.order, item.module_id))

    def get_snapshot(self, module_id: str) -> ModuleSnapshot | None:
        """Return a discovered module snapshot by identifier.

        Args:
            module_id: Module identifier to locate.

        Returns:
            ModuleSnapshot | None: Matching module snapshot when discovered.

        Raises:
            None.
        """

        with self._lock:
            return self._snapshots.get(module_id)

    def has_module(self, module_id: str) -> bool:
        """Return whether a module identifier is currently discoverable.

        Args:
            module_id: Module identifier to test.

        Returns:
            bool: True when the module is discovered by manifest scan.

        Raises:
            None.
        """

        with self._lock:
            return module_id in self._snapshots

    def dispatch(self, event: str, payload: Mapping[str, object]) -> None:
        """Dispatch a stable module event to enabled hooks in deterministic order."""

        allowed_events = {hook_event.value for hook_event in ModuleHookEvent}
        if event not in allowed_events:
            raise ModuleError(
                detail=f'Unsupported module hook event: {event}',
                code='MODULE_EVENT_UNSUPPORTED',
                status_code=400,
            )

        with self._lock:
            bindings = self._bindings.get(event, tuple())

        for binding in bindings:
            started_at = perf_counter()
            try:
                binding.handler(payload)
            except ModuleError as exc:
                logger.warning(
                    'Module hook failed',
                    extra={
                        'event': event,
                        'module_id': binding.module_id,
                        'hook_name': binding.hook_name,
                        'module_code': exc.code,
                    },
                )
            except Exception:
                logger.warning(
                    'Module hook failed with an unexpected exception',
                    extra={
                        'event': event,
                        'module_id': binding.module_id,
                        'hook_name': binding.hook_name,
                        'module_code': 'MODULE_HOOK_EXECUTION_FAILED',
                    },
                    exc_info=True,
                )
            finally:
                elapsed_seconds = perf_counter() - started_at
                elapsed_ms = elapsed_seconds * 1000
                log_extra = {
                    'event': event,
                    'module_id': binding.module_id,
                    'hook_name': binding.hook_name,
                    'elapsed_ms': elapsed_ms,
                }
                logger.debug('Module hook completed', extra=log_extra)
                if elapsed_seconds >= self._settings.module_hook_slow_seconds:
                    logger.warning(
                        'Module hook exceeded latency warning threshold',
                        extra={
                            **log_extra,
                            'module_code': 'MODULE_HOOK_SLOW',
                            'threshold_seconds': self._settings.module_hook_slow_seconds,
                        },
                    )

    def _load_persisted_state(self, storage: DatabasePool) -> dict[str, bool]:
        """Load persisted module enable/disable state from storage.

        Args:
            storage: Initialized database pool manager.

        Returns:
            dict[str, bool]: Mapping of module id to enabled flag.

        Raises:
            ModuleError: If the state query fails unexpectedly.
        """

        try:
            with storage.connection() as connection:
                rows = list_module_states(connection)
        except UndefinedTable:
            logger.warning(
                'Module state table is unavailable; all modules default to disabled',
                extra={'module_code': 'MODULE_STATE_TABLE_UNAVAILABLE'},
            )
            return {}
        except PsycopgError as exc:
            raise ModuleError(
                detail='Unable to load module state from storage',
                code='MODULE_STATE_QUERY_FAILED',
                status_code=503,
            ) from exc

        return {str(row['module_id']): bool(row['enabled']) for row in rows}

    def _load_module_hooks(
        self,
        discovered_module: DiscoveredModule,
        entrypoint_cache_key: _ModuleEntrypointCacheKey,
    ) -> dict[str, _ModuleHookBinding]:
        """Load declared module hooks from an entrypoint module.

        Args:
            discovered_module: Module manifest and filesystem metadata.
            entrypoint_cache_key: Current content cache key for the entrypoint.

        Returns:
            dict[str, _ModuleHookBinding]: Bound hook handlers keyed by event name.

        Raises:
            ModuleError: If module entrypoint loading or hook binding fails.
        """

        entrypoint_module = self._load_module_entrypoint(
            discovered_module,
            entrypoint_cache_key,
        )
        bindings: dict[str, _ModuleHookBinding] = {}
        for event_name, hook_name in discovered_module.manifest.hooks.items():
            attribute = getattr(entrypoint_module, hook_name, None)
            if attribute is None:
                raise ModuleError(
                    detail=(
                        f'Module hook callable {hook_name} is not defined for event {event_name}'
                    ),
                    code='MODULE_HOOK_NOT_FOUND',
                    status_code=500,
                )
            if not callable(attribute):
                raise ModuleError(
                    detail=(
                        f'Module hook callable {hook_name} is not callable for event {event_name}'
                    ),
                    code='MODULE_HOOK_NOT_CALLABLE',
                    status_code=500,
                )
            bindings[event_name] = _ModuleHookBinding(
                module_id=discovered_module.manifest.id,
                hook_name=hook_name,
                handler=cast(Callable[[Mapping[str, object]], None], attribute),
            )
        return bindings

    def _load_module_entrypoint(
        self,
        discovered_module: DiscoveredModule,
        cache_key: _ModuleEntrypointCacheKey,
    ) -> ModuleType:
        """Load the Python entrypoint module for a discovered backend module.

        Args:
            discovered_module: Module manifest and filesystem metadata.
            cache_key: Current manifest/entrypoint content cache key.

        Returns:
            ModuleType: Loaded Python module object.

        Raises:
            ModuleError: If the module entrypoint cannot be imported.
        """

        with self._lock:
            cached_module = self._entrypoint_cache.get(cache_key)
        if cached_module is not None:
            return cached_module

        module_token = discovered_module.manifest.id.replace('-', '_')
        module_digest = cache_key.entrypoint.digest[:12]
        module_name = f'pragma.modules.runtime_{module_token}_{module_digest}'
        spec = importlib.util.spec_from_file_location(
            module_name,
            discovered_module.entrypoint_path,
        )
        if spec is None or spec.loader is None:
            raise ModuleError(
                detail=(
                    'Unable to load module entrypoint specification '
                    f'for {discovered_module.manifest.id}'
                ),
                code='MODULE_ENTRYPOINT_LOAD_FAILED',
                status_code=500,
            )

        module = importlib.util.module_from_spec(spec)
        logger.warning(
            'Loading trusted operator-installed module Python code; module entrypoints '
            'execute in the backend process with application privileges and are not sandboxed',
            extra={
                'module_id': discovered_module.manifest.id,
                'module_code': 'MODULE_TRUSTED_CODE_EXECUTION',
                'module_entrypoint': str(discovered_module.entrypoint_path),
            },
        )
        try:
            spec.loader.exec_module(module)
        except ModuleError:
            raise
        except Exception as exc:
            raise ModuleError(
                detail=(
                    f'Module entrypoint raised during import for '
                    f'{discovered_module.manifest.id}'
                ),
                code='MODULE_ENTRYPOINT_LOAD_FAILED',
                status_code=500,
            ) from exc

        with self._lock:
            self._entrypoint_cache = {
                stored_key: stored_module
                for stored_key, stored_module in self._entrypoint_cache.items()
                if stored_key.module_id != discovered_module.manifest.id
            }
            self._entrypoint_cache[cache_key] = module

        return module

    def _build_entrypoint_cache_key(
        self,
        discovered_module: DiscoveredModule,
    ) -> _ModuleEntrypointCacheKey:
        """Return the content-sensitive entrypoint cache key for a module."""

        return _ModuleEntrypointCacheKey(
            module_id=discovered_module.manifest.id,
            manifest=self._fingerprint_module_file(
                discovered_module.manifest_path,
                discovered_module.manifest.id,
                'manifest',
            ),
            entrypoint=self._fingerprint_module_file(
                discovered_module.entrypoint_path,
                discovered_module.manifest.id,
                'entrypoint',
            ),
        )

    def _fingerprint_module_file(
        self,
        path: Path,
        module_id: str,
        label: str,
    ) -> _ModuleFileFingerprint:
        """Hash module-controlled file content and stat metadata for cache invalidation."""

        try:
            resolved_path = path.resolve()
            content = resolved_path.read_bytes()
            stat = resolved_path.stat()
        except OSError as exc:
            raise ModuleError(
                detail=f'Unable to read module {label} for {module_id}',
                code='MODULE_ENTRYPOINT_LOAD_FAILED',
                status_code=500,
            ) from exc

        return _ModuleFileFingerprint(
            path=str(resolved_path),
            mtime_ns=stat.st_mtime_ns,
            size=stat.st_size,
            digest=hashlib.sha256(content).hexdigest(),
        )

    def _prune_entrypoint_cache_locked(
        self,
        current_cache_keys: set[_ModuleEntrypointCacheKey],
    ) -> None:
        """Drop cached entrypoints that no longer match discovered module files."""

        self._entrypoint_cache = {
            cache_key: cached_module
            for cache_key, cached_module in self._entrypoint_cache.items()
            if cache_key in current_cache_keys
        }


def build_module_runtime(settings: Settings) -> ModuleRuntime:
    """Build a backend module runtime from application settings.

    Args:
        settings: Application settings.

    Returns:
        ModuleRuntime: Configured runtime module service.

    Raises:
        None.
    """

    return ModuleRuntime(settings)


_active_runtime_lock = Lock()
_active_runtime: ModuleRuntime | None = None


def set_active_module_runtime(runtime: ModuleRuntime | None) -> None:
    """Set the process-local active module runtime reference.

    Args:
        runtime: Runtime instance to expose globally, or ``None`` to clear it.

    Returns:
        None.

    Raises:
        None.
    """

    global _active_runtime
    with _active_runtime_lock:
        _active_runtime = runtime


def get_active_module_runtime() -> ModuleRuntime | None:
    """Return the process-local active module runtime reference.

    Args:
        None.

    Returns:
        ModuleRuntime | None: Active runtime instance when available.

    Raises:
        None.
    """

    with _active_runtime_lock:
        return _active_runtime
