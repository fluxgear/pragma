# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Module-management API routes for Pragma's backend runtime.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from pragma.auth.dependencies import get_current_superuser, get_current_user
from pragma.modules.dependencies import get_module_runtime
from pragma.modules.models import ModuleListResponse, ModuleStateResponse, ModuleStateUpdateRequest
from pragma.modules.runtime import ModuleRuntime
from pragma.modules.service import list_module_snapshots, update_module_state
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

router = APIRouter(
    prefix='/modules',
    tags=['modules'],
    dependencies=[Depends(get_current_user)],
)

_ERROR_RESPONSE_SCHEMA = {
    'type': 'object',
    'required': ['detail', 'code'],
    'properties': {
        'detail': {'type': 'string'},
        'code': {'type': 'string'},
    },
}

_MODULE_ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {
        'description': 'Module request is invalid',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_401_UNAUTHORIZED: {
        'description': 'Authentication required',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_403_FORBIDDEN: {
        'description': 'Superuser privileges required',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_404_NOT_FOUND: {
        'description': 'Module is not discoverable',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        'description': 'Request validation failed',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        'description': 'Module storage or runtime is unavailable',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}


@router.get('', response_model=ModuleListResponse, responses=_MODULE_ERROR_RESPONSES)
def list_modules(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    runtime: Annotated[ModuleRuntime, Depends(get_module_runtime)],
    current_user: Annotated[dict[str, object], Depends(get_current_superuser)],
) -> ModuleListResponse:
    """Return discovered modules and their persisted lifecycle state.

    Args:
        storage: Initialized database pool manager.
        runtime: Initialized module runtime instance.
        current_user: Authenticated superuser context.

    Returns:
        ModuleListResponse: Ordered discovered-module state payload.

    Raises:
        ModuleError: If module state refresh fails.
    """

    _ = current_user
    return list_module_snapshots(storage, runtime)


@router.put(
    '/{module_id}/state',
    response_model=ModuleStateResponse,
    responses=_MODULE_ERROR_RESPONSES,
)
def update_module(
    module_id: Annotated[str, Path(min_length=1, max_length=64)],
    payload: ModuleStateUpdateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    runtime: Annotated[ModuleRuntime, Depends(get_module_runtime)],
    current_user: Annotated[dict[str, object], Depends(get_current_superuser)],
) -> ModuleStateResponse:
    """Enable or disable a discovered module in persisted module state.

    Args:
        module_id: Target module identifier.
        payload: Module-state update payload.
        storage: Initialized database pool manager.
        runtime: Initialized module runtime instance.
        current_user: Authenticated superuser context.

    Returns:
        ModuleStateResponse: Updated module state payload.

    Raises:
        AuthError: If superuser privileges are missing.
        ModuleError: If the module state update fails.
    """

    return update_module_state(storage, runtime, module_id, payload, current_user)
