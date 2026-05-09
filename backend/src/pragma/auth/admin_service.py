# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Administrative RBAC and user-management service functions.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import secrets
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

from psycopg import Error as PsycopgError
from psycopg import IntegrityError

from pragma.auth.admin_models import (
    AdminUserCreateRequest,
    AdminUserListParams,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    PasswordResetResponse,
    PermissionDefinitionResponse,
    RoleCreateRequest,
    RoleListResponse,
    RoleResponse,
    RolesAdminListResponse,
    UserRoleAssignmentRequest,
)
from pragma.auth.permissions import (
    PERMISSION_USERS_MANAGE,
    ROLE_ADMINISTRATOR,
    normalize_role_keys,
)
from pragma.auth.security import hash_password, normalize_identity, utc_now, verify_password
from pragma.errors import AuthError, ConfigError, StorageError
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.auth_sessions import revoke_refresh_sessions_for_user
from pragma.storage.queries.roles import (
    count_active_users_with_permission,
    list_roles,
    replace_user_roles,
)
from pragma.storage.queries.users import (
    count_superusers,
    count_users,
    create_user,
    get_user_by_id,
    list_users,
    set_user_force_password_change,
    set_user_password,
    update_user_profile,
)


def _require_user_id(current_user: dict[str, object]) -> UUID:
    """Return the authenticated administrative user identifier.

    Args:
        current_user: Authenticated user context.

    Returns:
        UUID: Administrative user identifier.

    Raises:
        AuthError: If the authenticated user context is invalid.
    """

    candidate = current_user.get('id')
    if not isinstance(candidate, UUID):
        raise AuthError(
            detail='Authenticated user is invalid',
            code='AUTH_USER_INVALID',
            status_code=HTTPStatus.UNAUTHORIZED,
        )
    return candidate


_PROTECTED_LAST_ACTIVE_PERMISSION_ERRORS: tuple[tuple[str, str, str], ...] = (
    (
        PERMISSION_USERS_MANAGE,
        'At least one active users.manage administrator is required',
        'AUTH_LAST_USERS_MANAGER_REQUIRED',
    ),
    (
        'admin.access',
        'At least one active admin.access holder is required',
        'AUTH_LAST_ADMIN_ACCESS_REQUIRED',
    ),
    (
        'roles.manage',
        'At least one active roles.manage holder is required',
        'AUTH_LAST_ROLES_MANAGER_REQUIRED',
    ),
)


def _permissions_for_role_keys(role_keys: list[str]) -> set[str]:
    """Return effective permission keys granted by built-in role assignments.

    Args:
        role_keys: Normalized built-in role keys.

    Returns:
        set[str]: Permission keys granted by the requested built-in roles.

    Raises:
        None.
    """

    from pragma.auth.permissions import ROLE_DEFINITION_BY_KEY

    permission_keys: set[str] = set()
    for role_key in role_keys:
        permission_keys.update(ROLE_DEFINITION_BY_KEY[role_key].permissions)
    return permission_keys


def _record_permission_keys(user: dict[str, object]) -> set[str]:
    """Return permission keys carried on a user record.

    Args:
        user: User record or authenticated user context.

    Returns:
        set[str]: Permission keys from the record.

    Raises:
        None.
    """

    permissions = user.get('permissions')
    if not isinstance(permissions, list):
        return set()
    return {value for value in permissions if isinstance(value, str)}


def _user_has_effective_permission(
    user: dict[str, object], permission_key: str
) -> bool:
    """Return whether a user record effectively holds a permission.

    Args:
        user: User record or authenticated user context.
        permission_key: Permission key to inspect.

    Returns:
        bool: True when the user is superuser or has the permission key.

    Raises:
        None.
    """

    return bool(user.get('is_superuser')) or permission_key in _record_permission_keys(user)


def _require_role_assignment_not_escalating(
    normalized_roles: list[str], current_user: dict[str, object]
) -> None:
    """Reject role assignments that grant permissions the actor lacks.

    Args:
        normalized_roles: Normalized built-in role keys requested for assignment.
        current_user: Authenticated administrator context.

    Returns:
        None.

    Raises:
        AuthError: If a non-superuser actor assigns permissions they lack.
    """

    if bool(current_user.get('is_superuser')):
        return

    requested_permissions = _permissions_for_role_keys(normalized_roles)
    actor_permissions = _record_permission_keys(current_user)
    if requested_permissions.issubset(actor_permissions):
        return

    raise AuthError(
        detail='You cannot assign roles with permissions you do not hold',
        code='AUTH_ROLE_ASSIGNMENT_ESCALATION_FORBIDDEN',
        status_code=HTTPStatus.FORBIDDEN,
    )


def _ensure_last_active_protected_permissions(
    connection: Any,
    existing_user: dict[str, object],
    *,
    next_permission_keys: set[str],
    next_is_active: bool,
) -> None:
    """Prevent removing the final active holder of protected permissions.

    Args:
        connection: Open PostgreSQL connection inside a transaction.
        existing_user: Current target user record.
        next_permission_keys: Permission keys the user will hold after mutation.
        next_is_active: Whether the user remains active after mutation.

    Returns:
        None.

    Raises:
        AuthError: If the mutation removes the final active protected holder.
        ConfigError: If the target user disappears while locks are acquired.
    """

    from pragma.storage.queries.roles import lock_active_users_with_permission

    if not bool(existing_user['is_active']):
        return

    user_id = existing_user['id']
    for permission_key, detail, code in _PROTECTED_LAST_ACTIVE_PERMISSION_ERRORS:
        if not _user_has_effective_permission(existing_user, permission_key):
            continue
        next_has_permission = next_is_active and (
            bool(existing_user['is_superuser']) or permission_key in next_permission_keys
        )
        if next_has_permission:
            continue

        lock_active_users_with_permission(connection, permission_key)
        refreshed_user = get_user_by_id(connection, user_id)
        if refreshed_user is None:
            raise ConfigError(
                detail='User account not found',
                code='USER_NOT_FOUND',
                status_code=HTTPStatus.NOT_FOUND,
            )
        existing_user = refreshed_user
        if not bool(existing_user['is_active']):
            continue
        if not _user_has_effective_permission(existing_user, permission_key):
            continue
        next_has_permission = next_is_active and (
            bool(existing_user['is_superuser']) or permission_key in next_permission_keys
        )
        if next_has_permission:
            continue
        if count_active_users_with_permission(connection, permission_key) <= 1:
            raise AuthError(
                detail=detail,
                code=code,
                status_code=HTTPStatus.BAD_REQUEST,
            )


def list_user_records(
    storage: DatabasePool, params: AdminUserListParams
) -> AdminUserListResponse:
    """Return managed user accounts for administrative review.

    Args:
        storage: Initialized database pool manager.
        params: User-list query parameters.

    Returns:
        AdminUserListResponse: Paginated administrative user payload.

    Raises:
        StorageError: If PostgreSQL access fails.
    """

    try:
        with storage.connection() as connection:
            rows = list_users(connection, limit=params.limit, offset=params.offset)
            total = count_users(connection)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load user accounts',
            code='USER_LIST_FAILED',
        ) from exc

    items = [AdminUserResponse.from_record(row) for row in rows]
    return AdminUserListResponse(
        items=items,
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


def list_role_catalog(storage: DatabasePool) -> RoleListResponse:
    """Return the built-in role and permission catalog.

    Args:
        storage: Initialized database pool manager.

    Returns:
        RoleListResponse: Ordered role catalog payload.

    Raises:
        StorageError: If PostgreSQL access fails.
    """

    try:
        with storage.connection() as connection:
            rows = list_roles(connection)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load role catalog',
            code='ROLE_LIST_FAILED',
        ) from exc

    items = [RoleResponse.from_record(row) for row in rows]
    return RoleListResponse(items=items, total=len(items))


def list_roles_admin_catalog(storage: DatabasePool) -> RolesAdminListResponse:
    """Return DB-backed roles with canonical permission metadata.

    Args:
        storage: Initialized database pool manager.

    Returns:
        RolesAdminListResponse: Ordered role catalog plus permission metadata.

    Raises:
        StorageError: If PostgreSQL access fails.
    """

    from pragma.auth.permissions import get_permission_definitions

    try:
        with storage.connection() as connection:
            rows = list_roles(connection)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load role catalog',
            code='ROLE_LIST_FAILED',
        ) from exc

    items = [RoleResponse.from_record(row) for row in rows]
    permission_definitions = [
        PermissionDefinitionResponse.from_definition(definition)
        for definition in get_permission_definitions()
    ]
    return RolesAdminListResponse(
        items=items,
        total=len(items),
        permission_definitions=permission_definitions,
    )


def _normalize_role_permission_keys(permission_keys: list[str]) -> list[str]:
    """Validate requested role permissions against the runtime registry.

    Args:
        permission_keys: Requested canonical permission keys.

    Returns:
        list[str]: Ordered unique permission keys.

    Raises:
        ConfigError: If any permission key is not a canonical registry key.
    """

    from pragma.auth.permissions import get_permission_definitions

    canonical_keys = {definition.key for definition in get_permission_definitions()}
    normalized: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for permission_key in permission_keys:
        if permission_key not in canonical_keys:
            invalid.append(permission_key)
            continue
        if permission_key not in seen:
            normalized.append(permission_key)
            seen.add(permission_key)

    if invalid:
        invalid_permissions = ', '.join(
            sorted({'<blank>' if value == '' else value for value in invalid})
        )
        raise ConfigError(
            detail=f'Unknown permission requested: {invalid_permissions}',
            code='ROLE_PERMISSION_INVALID',
            status_code=HTTPStatus.BAD_REQUEST,
        )
    return normalized


def create_role_record(
    storage: DatabasePool,
    payload: RoleCreateRequest,
    current_user: dict[str, object],
) -> RoleResponse:
    """Create a custom DB-backed role with validated permission grants.

    Args:
        storage: Initialized database pool manager.
        payload: Custom role creation payload.
        current_user: Authenticated role administrator context.

    Returns:
        RoleResponse: Created custom role payload.

    Raises:
        AuthError: If the authenticated user context is invalid.
        ConfigError: If the role key or permission grants are invalid.
        StorageError: If PostgreSQL access fails.
    """

    from pragma.auth.permissions import ROLE_DEFINITION_BY_KEY
    from pragma.storage.queries.roles import (
        create_role,
        get_role_by_key,
        replace_role_permissions,
    )

    _require_user_id(current_user)
    role_key = payload.role_key
    if role_key in ROLE_DEFINITION_BY_KEY:
        raise ConfigError(
            detail='Role key conflicts with a built-in system role',
            code='ROLE_SYSTEM_KEY_CONFLICT',
            status_code=HTTPStatus.CONFLICT,
        )
    permission_keys = _normalize_role_permission_keys(payload.permission_keys)
    timestamp = utc_now()

    try:
        with storage.connection() as connection, connection.transaction():
            existing_role = get_role_by_key(connection, role_key)
            if existing_role is not None:
                raise ConfigError(
                    detail='Role key already exists',
                    code='ROLE_KEY_CONFLICT',
                    status_code=HTTPStatus.CONFLICT,
                )
            create_role(
                connection,
                role_key=role_key,
                name=payload.name,
                description=payload.description,
                is_system=False,
                created_at=timestamp,
            )
            replace_role_permissions(
                connection,
                role_key=role_key,
                permission_keys=permission_keys,
                created_at=timestamp,
            )
            stored_role = get_role_by_key(connection, role_key)
    except ConfigError:
        raise
    except IntegrityError as exc:
        raise ConfigError(
            detail='Role key already exists',
            code='ROLE_KEY_CONFLICT',
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to create role',
            code='ROLE_CREATE_FAILED',
        ) from exc

    if stored_role is None:
        raise StorageError(
            detail='Unable to reload created role',
            code='ROLE_RELOAD_FAILED',
        )
    return RoleResponse.from_record(stored_role)


def create_user_record(
    storage: DatabasePool,
    payload: AdminUserCreateRequest,
    current_user: dict[str, object],
) -> AdminUserResponse:
    """Create a managed user account and assign built-in roles.

    Args:
        storage: Initialized database pool manager.
        payload: User-creation request payload.
        current_user: Authenticated administrator context.

    Returns:
        AdminUserResponse: Created administrative user payload.

    Raises:
        AuthError: If the actor tries to assign roles with permissions they lack.
        ConfigError: If the create request conflicts with existing users or roles.
        StorageError: If PostgreSQL access fails.
    """

    created_at = utc_now()
    actor_user_id = _require_user_id(current_user)

    try:
        normalized_roles = normalize_role_keys(payload.role_keys)
    except ValueError as exc:
        raise ConfigError(
            detail=str(exc),
            code='ROLE_ASSIGNMENT_INVALID',
            status_code=HTTPStatus.BAD_REQUEST,
        ) from exc
    _require_role_assignment_not_escalating(normalized_roles, current_user)

    try:
        with storage.connection() as connection, connection.transaction():
            user = create_user(
                connection=connection,
                user_id=uuid4(),
                email=normalize_identity(payload.email),
                username=normalize_identity(payload.username),
                password_hash=hash_password(payload.password),
                full_name=payload.full_name.strip() if payload.full_name else None,
                is_superuser=False,
                is_active=payload.is_active,
                force_password_change=payload.force_password_change,
                created_at=created_at,
            )
            replace_user_roles(
                connection,
                user_id=user['id'],
                role_keys=normalized_roles,
                assigned_by_user_id=actor_user_id,
                assigned_at=created_at,
            )
            stored_user = get_user_by_id(connection, user['id'])
    except IntegrityError as exc:
        raise ConfigError(
            detail='User identity already exists',
            code='USER_IDENTITY_CONFLICT',
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to create user account',
            code='USER_CREATE_FAILED',
        ) from exc

    if stored_user is None:
        raise StorageError(
            detail='Unable to reload created user account',
            code='USER_RELOAD_FAILED',
        )
    return AdminUserResponse.from_record(stored_user)


def update_user_record(
    storage: DatabasePool,
    user_id: UUID,
    payload: AdminUserUpdateRequest,
    current_user: dict[str, object],
) -> AdminUserResponse:
    """Update a managed user profile and activation state.

    Args:
        storage: Initialized database pool manager.
        user_id: Managed user identifier.
        payload: User-update request payload.
        current_user: Authenticated administrator context.

    Returns:
        AdminUserResponse: Updated administrative user payload.

    Raises:
        AuthError: If the requested lifecycle change would lock out administrators.
        ConfigError: If the user does not exist or profile values conflict.
        StorageError: If PostgreSQL access fails.
    """

    from pragma.storage.queries.users import lock_active_superusers

    actor_user_id = _require_user_id(current_user)
    timestamp = utc_now()

    try:
        with storage.connection() as connection, connection.transaction():
            existing_user = get_user_by_id(connection, user_id)
            if existing_user is None:
                raise ConfigError(
                    detail='User account not found',
                    code='USER_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )

            next_is_active = payload.is_active
            if next_is_active is False and user_id == actor_user_id:
                raise AuthError(
                    detail='You cannot deactivate your own account',
                    code='AUTH_SELF_DEACTIVATE_FORBIDDEN',
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            if next_is_active is False and bool(existing_user['is_superuser']):
                lock_active_superusers(connection)
                existing_user = get_user_by_id(connection, user_id)
                if existing_user is None:
                    raise ConfigError(
                        detail='User account not found',
                        code='USER_NOT_FOUND',
                        status_code=HTTPStatus.NOT_FOUND,
                    )
                if (
                    bool(existing_user['is_active'])
                    and bool(existing_user['is_superuser'])
                    and count_superusers(connection) <= 1
                ):
                    raise AuthError(
                        detail='At least one active superuser account is required',
                        code='AUTH_LAST_SUPERUSER_REQUIRED',
                        status_code=HTTPStatus.BAD_REQUEST,
                    )
            if next_is_active is False:
                _ensure_last_active_protected_permissions(
                    connection,
                    existing_user,
                    next_permission_keys=set(),
                    next_is_active=False,
                )

            full_name_provided = 'full_name' in payload.model_fields_set
            full_name = (
                payload.full_name.strip()
                if full_name_provided and payload.full_name is not None
                else None
            )
            updated_user = update_user_profile(
                connection,
                user_id=user_id,
                email=(
                    normalize_identity(payload.email)
                    if payload.email is not None
                    else None
                ),
                username=(
                    normalize_identity(payload.username)
                    if payload.username is not None
                    else None
                ),
                full_name=full_name,
                full_name_provided=full_name_provided,
                is_active=payload.is_active,
                updated_at=timestamp,
            )
            if updated_user is None:
                raise ConfigError(
                    detail='User account not found',
                    code='USER_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )

            if payload.is_active is False:
                revoke_refresh_sessions_for_user(connection, user_id, timestamp)
    except IntegrityError as exc:
        raise ConfigError(
            detail='User identity already exists',
            code='USER_IDENTITY_CONFLICT',
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to update user account',
            code='USER_UPDATE_FAILED',
        ) from exc

    return AdminUserResponse.from_record(updated_user)


def replace_user_role_assignments(
    storage: DatabasePool,
    user_id: UUID,
    payload: UserRoleAssignmentRequest,
    current_user: dict[str, object],
) -> AdminUserResponse:
    """Replace all built-in role assignments for a managed user.

    Args:
        storage: Initialized database pool manager.
        user_id: Managed user identifier.
        payload: Complete replacement role-assignment payload.
        current_user: Authenticated administrator context.

    Returns:
        AdminUserResponse: Updated administrative user payload.

    Raises:
        AuthError: If the assignment would escalate or remove protected access.
        ConfigError: If the target user or role assignment is invalid.
        StorageError: If PostgreSQL access fails.
    """

    actor_user_id = _require_user_id(current_user)
    assigned_at = utc_now()

    try:
        normalized_roles = normalize_role_keys(payload.role_keys)
    except ValueError as exc:
        raise ConfigError(
            detail=str(exc),
            code='ROLE_ASSIGNMENT_INVALID',
            status_code=HTTPStatus.BAD_REQUEST,
        ) from exc
    _require_role_assignment_not_escalating(normalized_roles, current_user)
    next_permission_keys = _permissions_for_role_keys(normalized_roles)

    try:
        with storage.connection() as connection, connection.transaction():
            existing_user = get_user_by_id(connection, user_id)
            if existing_user is None:
                raise ConfigError(
                    detail='User account not found',
                    code='USER_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )

            next_has_users_manage = (
                bool(existing_user['is_superuser'])
                or PERMISSION_USERS_MANAGE in next_permission_keys
            )
            if (
                user_id == actor_user_id
                and not bool(current_user.get('is_superuser'))
                and not next_has_users_manage
            ):
                raise AuthError(
                    detail='You cannot remove your own users.manage access',
                    code='AUTH_SELF_USERS_MANAGE_REQUIRED',
                    status_code=HTTPStatus.BAD_REQUEST,
                )
            _ensure_last_active_protected_permissions(
                connection,
                existing_user,
                next_permission_keys=next_permission_keys,
                next_is_active=True,
            )

            replace_user_roles(
                connection,
                user_id=user_id,
                role_keys=normalized_roles,
                assigned_by_user_id=actor_user_id,
                assigned_at=assigned_at,
            )
            updated_user = get_user_by_id(connection, user_id)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to replace user roles',
            code='ROLE_ASSIGNMENT_UPDATE_FAILED',
        ) from exc

    if updated_user is None:
        raise StorageError(
            detail='Unable to reload updated user account',
            code='USER_RELOAD_FAILED',
        )
    return AdminUserResponse.from_record(updated_user)


def reset_user_password(
    storage: DatabasePool,
    user_id: UUID,
    current_user: dict[str, object],
) -> PasswordResetResponse:
    """Generate and apply a temporary password for a managed user.

    Args:
        storage: Initialized database pool manager.
        user_id: Managed user identifier.
        current_user: Authenticated administrator context.

    Returns:
        PasswordResetResponse: One-time temporary password payload.

    Raises:
        ConfigError: If the target user does not exist.
        StorageError: If PostgreSQL access fails.
    """

    _require_user_id(current_user)
    timestamp = utc_now()
    temporary_password = secrets.token_urlsafe(18)

    try:
        with storage.connection() as connection, connection.transaction():
            existing_user = get_user_by_id(connection, user_id)
            if existing_user is None:
                raise ConfigError(
                    detail='User account not found',
                    code='USER_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )

            set_user_password(
                connection,
                user_id=user_id,
                password_hash=hash_password(temporary_password),
                password_changed_at=timestamp,
                updated_at=timestamp,
            )
            set_user_force_password_change(connection, user_id, True, timestamp)
            revoke_refresh_sessions_for_user(connection, user_id, timestamp)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to reset user password',
            code='USER_PASSWORD_RESET_FAILED',
        ) from exc

    return PasswordResetResponse(temporary_password=temporary_password)


def change_current_user_password(
    storage: DatabasePool,
    current_user: dict[str, object],
    current_password: str,
    new_password: str,
) -> dict[str, Any]:
    """Change the authenticated user's password and clear forced-reset state.

    Args:
        storage: Initialized database pool manager.
        current_user: Authenticated user context.
        current_password: Current raw password.
        new_password: Desired replacement password.

    Returns:
        dict[str, Any]: Updated authenticated user record.

    Raises:
        AuthError: If the current password is invalid.
        StorageError: If PostgreSQL access fails.
    """

    user_id = _require_user_id(current_user)
    timestamp = utc_now()

    if not verify_password(current_password, str(current_user['password_hash'])):
        raise AuthError(
            detail='Current password is invalid',
            code='CURRENT_PASSWORD_INVALID',
            status_code=HTTPStatus.UNAUTHORIZED,
        )

    try:
        with storage.connection() as connection, connection.transaction():
            set_user_password(
                connection,
                user_id=user_id,
                password_hash=hash_password(new_password),
                password_changed_at=timestamp,
                updated_at=timestamp,
            )
            set_user_force_password_change(connection, user_id, False, timestamp)
            revoke_refresh_sessions_for_user(connection, user_id, timestamp)
            updated_user = get_user_by_id(connection, user_id)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to change the current password',
            code='AUTH_PASSWORD_CHANGE_FAILED',
        ) from exc

    if updated_user is None:
        raise StorageError(
            detail='Unable to reload the authenticated user',
            code='AUTH_USER_LOOKUP_FAILED',
        )
    return updated_user


def user_is_administrator(user: dict[str, object]) -> bool:
    """Return whether the supplied user has administrator-level role access.

    Args:
        user: Authenticated user context.

    Returns:
        bool: True when the user is root or has the administrator role.

    Raises:
        None.
    """

    if bool(user.get('is_superuser')):
        return True
    roles = user.get('roles')
    return isinstance(roles, list) and ROLE_ADMINISTRATOR in roles
