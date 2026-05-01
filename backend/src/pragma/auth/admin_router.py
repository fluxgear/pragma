# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Administrative user and role-management routes for Pragma.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from pragma.auth.admin_models import (
    AdminUserCreateRequest,
    AdminUserListParams,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    PasswordResetResponse,
    RoleListResponse,
    UserRoleAssignmentRequest,
)
from pragma.auth.admin_service import (
    create_user_record,
    list_role_catalog,
    list_user_records,
    replace_user_role_assignments,
    reset_user_password,
    update_user_record,
)
from pragma.auth.dependencies import (
    get_current_user,
    require_password_change_cleared,
    require_permission,
)
from pragma.auth.permissions import PERMISSION_USERS_MANAGE
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

router = APIRouter(
    prefix='/users',
    tags=['users'],
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

_ADMIN_ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {
        'description': 'Administrative user-management request is invalid',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_401_UNAUTHORIZED: {
        'description': 'Authentication required',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_403_FORBIDDEN: {
        'description': 'Administrator privileges required',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_404_NOT_FOUND: {
        'description': 'User account was not found',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_409_CONFLICT: {
        'description': 'User identity already exists',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        'description': 'Request validation failed',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        'description': 'User-management storage is unavailable',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}


@router.get('', response_model=AdminUserListResponse, responses=_ADMIN_ERROR_RESPONSES)
def list_users(
    params: Annotated[AdminUserListParams, Query()],
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_USERS_MANAGE))
    ],
) -> AdminUserListResponse:
    """Return managed user accounts.

    Args:
        params: User-list query parameters.
        storage: Initialized database pool manager.
        current_user: Authenticated administrator context.

    Returns:
        AdminUserListResponse: Paginated administrative user payload.

    Raises:
        AuthError: If administrative privileges are missing.
        StorageError: If PostgreSQL access fails.
    """

    _ = current_user
    return list_user_records(storage, params)


@router.get('/roles', response_model=RoleListResponse, responses=_ADMIN_ERROR_RESPONSES)
def list_user_roles(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_USERS_MANAGE))
    ],
) -> RoleListResponse:
    """Return the built-in role catalog.

    Args:
        storage: Initialized database pool manager.
        current_user: Authenticated administrator context.

    Returns:
        RoleListResponse: Built-in role catalog payload.

    Raises:
        AuthError: If administrative privileges are missing.
        StorageError: If PostgreSQL access fails.
    """

    _ = current_user
    return list_role_catalog(storage)


@router.post(
    '',
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ADMIN_ERROR_RESPONSES,
)
def create_user(
    payload: AdminUserCreateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_USERS_MANAGE))
    ],
) -> AdminUserResponse:
    """Create a new managed user account.

    Args:
        payload: Administrative user-create payload.
        storage: Initialized database pool manager.
        current_user: Authenticated administrator context.

    Returns:
        AdminUserResponse: Created administrative user payload.

    Raises:
        AuthError: If administrative privileges are missing.
        ConfigError: If the request conflicts with existing identities.
        StorageError: If PostgreSQL access fails.
    """

    return create_user_record(storage, payload, current_user)


@router.patch(
    '/{user_id}',
    response_model=AdminUserResponse,
    responses=_ADMIN_ERROR_RESPONSES,
)
def update_user(
    user_id: UUID,
    payload: AdminUserUpdateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_USERS_MANAGE))
    ],
) -> AdminUserResponse:
    """Update a managed user account.

    Args:
        user_id: Managed user identifier.
        payload: Administrative user-update payload.
        storage: Initialized database pool manager.
        current_user: Authenticated administrator context.

    Returns:
        AdminUserResponse: Updated administrative user payload.

    Raises:
        AuthError: If administrative privileges are missing or the change would lock out the actor.
        ConfigError: If the target account does not exist or conflicts.
        StorageError: If PostgreSQL access fails.
    """

    return update_user_record(storage, user_id, payload, current_user)


@router.put(
    '/{user_id}/roles',
    response_model=AdminUserResponse,
    responses=_ADMIN_ERROR_RESPONSES,
)
def replace_roles(
    user_id: UUID,
    payload: UserRoleAssignmentRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_USERS_MANAGE))
    ],
) -> AdminUserResponse:
    """Replace assigned built-in roles for a managed user.

    Args:
        user_id: Managed user identifier.
        payload: Complete role-replacement payload.
        storage: Initialized database pool manager.
        current_user: Authenticated administrator context.

    Returns:
        AdminUserResponse: Updated administrative user payload.

    Raises:
        AuthError: If administrative privileges are missing.
        ConfigError: If the target user or role payload is invalid.
        StorageError: If PostgreSQL access fails.
    """

    return replace_user_role_assignments(storage, user_id, payload, current_user)


@router.post(
    '/{user_id}/password-reset',
    response_model=PasswordResetResponse,
    responses=_ADMIN_ERROR_RESPONSES,
)
def reset_password(
    user_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_USERS_MANAGE))
    ],
) -> PasswordResetResponse:
    """Reset a managed user's password to a generated temporary password.

    Args:
        user_id: Managed user identifier.
        storage: Initialized database pool manager.
        current_user: Authenticated administrator context.

    Returns:
        PasswordResetResponse: One-time temporary password payload.

    Raises:
        AuthError: If administrative privileges are missing.
        ConfigError: If the target user does not exist.
        StorageError: If PostgreSQL access fails.
    """

    return reset_user_password(storage, user_id, current_user)
