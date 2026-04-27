# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Administrative authentication and RBAC request/response models.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from pragma.auth.models import UserResponse


class RoleResponse(BaseModel):
    """Serialized built-in role payload.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response values are invalid.
    """

    role_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_system: bool = True
    permission_keys: list[str] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> RoleResponse:
        """Build a role response from a storage-layer record.

        Args:
            record: Role record returned by the storage layer.

        Returns:
            RoleResponse: Serialized role payload.

        Raises:
            ValidationError: If record fields are invalid.
        """

        return cls(
            role_key=str(record['role_key']),
            name=str(record['name']),
            description=record.get('description'),
            is_system=bool(record['is_system']),
            permission_keys=[str(value) for value in record.get('permission_keys', [])],
        )


class RoleListResponse(BaseModel):
    """List payload for built-in RBAC roles.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response values are invalid.
    """

    items: list[RoleResponse] = Field(default_factory=list)
    total: int = Field(ge=0)


class AdminUserResponse(UserResponse):
    """Administrative user payload with lifecycle timestamps.

    Args:
        UserResponse: Base authenticated-user payload.

    Returns:
        None.

    Raises:
        ValidationError: If response values are invalid.
    """

    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> AdminUserResponse:
        """Build an administrative user response from a storage-layer record.

        Args:
            record: User record returned by the storage layer.

        Returns:
            AdminUserResponse: Serialized administrative user payload.

        Raises:
            ValidationError: If record fields are invalid.
        """

        return cls(
            id=record['id'],
            email=str(record['email']),
            username=str(record['username']),
            full_name=record['full_name'],
            is_active=bool(record['is_active']),
            is_superuser=bool(record['is_superuser']),
            roles=[str(value) for value in record.get('roles', [])],
            permissions=[str(value) for value in record.get('permissions', [])],
            force_password_change=bool(record.get('force_password_change', False)),
            last_login_at=record.get('last_login_at'),
            password_changed_at=record.get('password_changed_at'),
            created_at=record['created_at'],
            updated_at=record['updated_at'],
        )


class AdminUserListResponse(BaseModel):
    """List payload for administrative user management.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response values are invalid.
    """

    items: list[AdminUserResponse] = Field(default_factory=list)
    total: int = Field(ge=0)


class AdminUserCreateRequest(BaseModel):
    """Payload for creating a managed user account.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If request values are invalid.
    """

    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=64)
    full_name: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=8, max_length=512)
    is_active: bool = True
    role_keys: list[str] = Field(default_factory=list)
    force_password_change: bool = True


class AdminUserUpdateRequest(BaseModel):
    """Payload for updating an existing managed user account.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If request values are invalid.
    """

    email: str | None = Field(default=None, min_length=3, max_length=320)
    username: str | None = Field(default=None, min_length=3, max_length=64)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class UserRoleAssignmentRequest(BaseModel):
    """Payload for replacing assigned built-in roles for a user.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If request values are invalid.
    """

    role_keys: list[str] = Field(default_factory=list)


class PasswordResetResponse(BaseModel):
    """One-time administrative password reset payload.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response values are invalid.
    """

    temporary_password: str = Field(min_length=8)


class UserIdentifierResponse(BaseModel):
    """Minimal user identifier payload for mutation endpoints.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response values are invalid.
    """

    user_id: UUID
