# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Request-scoped dependencies for module runtime access.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import cast

from fastapi import Request

from pragma.errors import ModuleError
from pragma.modules.runtime import ModuleRuntime


def get_module_runtime(request: Request) -> ModuleRuntime:
    """Return the initialized module runtime from application state.

    Args:
        request: FastAPI request object.

    Returns:
        ModuleRuntime: Initialized module runtime.

    Raises:
        ModuleError: If the module runtime has not been initialized yet.
    """

    runtime = getattr(request.app.state, 'module_runtime', None)
    if runtime is None:
        raise ModuleError(
            detail='Module runtime is not initialized',
            code='MODULE_RUNTIME_UNAVAILABLE',
            status_code=503,
        )
    return cast(ModuleRuntime, runtime)
