# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Administrative role-definition routes for Pragma.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from pragma.auth.admin_models import (
    RoleCreateRequest,
    RoleResponse,
    RolesAdminListResponse,
)
from pragma.auth.admin_service import create_role_record, list_roles_admin_catalog
from pragma.auth.dependencies import (
    get_current_user,
    require_password_change_cleared,
    require_permission,
)
from pragma.auth.permissions import PERMISSION_ROLES_MANAGE
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

router = APIRouter(
    prefix='/roles',
    tags=['roles'],
    dependencies=[Depends(get_current_user), Depends(require_password_change_cleared)],
)

_ERROR_RESPONSE_SCHEMA = {
    'type': 'object',
    'required': ['detail', 'code'],
    'properties': {
        'detail': {'type': 'string'},
        'code': {'type': 'string'},
    },
}

_ROLES_ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {
        'description': 'Role-management request is invalid',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_401_UNAUTHORIZED: {
        'description': 'Authentication required',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_403_FORBIDDEN: {
        'description': 'roles.manage permission required',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_409_CONFLICT: {
        'description': 'Role key already exists',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        'description': 'Request validation failed',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        'description': 'Role-management storage is unavailable',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}


@router.get('', response_model=RolesAdminListResponse, responses=_ROLES_ERROR_RESPONSES)
def list_roles_admin(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_ROLES_MANAGE))
    ],
) -> RolesAdminListResponse:
    """Return DB-backed roles and canonical permission metadata.

    Args:
        storage: Initialized database pool manager.
        current_user: Authenticated role administrator context.

    Returns:
        RolesAdminListResponse: Role catalog plus permission definitions.

    Raises:
        AuthError: If roles.manage is missing.
        StorageError: If PostgreSQL access fails.
    """

    _ = current_user
    return list_roles_admin_catalog(storage)


@router.post(
    '',
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ROLES_ERROR_RESPONSES,
)
def create_role_admin(
    payload: RoleCreateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_ROLES_MANAGE))
    ],
) -> RoleResponse:
    """Create a custom DB-backed role.

    Args:
        payload: Custom role creation payload.
        storage: Initialized database pool manager.
        current_user: Authenticated role administrator context.

    Returns:
        RoleResponse: Created custom role payload.

    Raises:
        AuthError: If roles.manage is missing.
        ConfigError: If the role payload is invalid or conflicts.
        StorageError: If PostgreSQL access fails.
    """

    return create_role_record(storage, payload, current_user)
