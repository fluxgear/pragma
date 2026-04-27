# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Module runtime exports for the Pragma backend.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from pragma.modules.loader import DiscoveredModule, discover_modules, load_module_manifest
from pragma.modules.manifest import ModuleHookEvent, ModuleManifest, normalize_module_id
from pragma.modules.runtime import (
    ModuleRuntime,
    ModuleSnapshot,
    build_module_runtime,
    get_active_module_runtime,
    set_active_module_runtime,
)

__all__ = [
    'DiscoveredModule',
    'ModuleHookEvent',
    'ModuleManifest',
    'ModuleRuntime',
    'ModuleSnapshot',
    'build_module_runtime',
    'discover_modules',
    'get_active_module_runtime',
    'load_module_manifest',
    'normalize_module_id',
    'set_active_module_runtime',
]
