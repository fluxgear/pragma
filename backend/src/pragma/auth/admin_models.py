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

import typing
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pragma.auth.models import UserResponse, user_access_payload_from_record

EmailField = typing.Annotated[
    str,
    Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]

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


class PermissionDefinitionResponse(BaseModel):
    """Permission catalog metadata for role administration.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response values are invalid.
    """

    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    domain: str = Field(min_length=1, max_length=64)

    @classmethod
    def from_definition(cls, definition: Any) -> PermissionDefinitionResponse:
        """Build permission metadata from the runtime registry definition.

        Args:
            definition: Runtime permission definition.

        Returns:
            PermissionDefinitionResponse: Serialized permission metadata.

        Raises:
            ValidationError: If definition fields are invalid.
        """

        key = str(definition.key)
        return cls(
            key=key,
            name=str(definition.name),
            description=definition.description,
            domain=key.split('.', maxsplit=1)[0],
        )


class RolesAdminListResponse(BaseModel):
    """Dedicated roles-admin list payload with permission metadata.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response values are invalid.
    """

    items: list[RoleResponse] = Field(default_factory=list)
    total: int = Field(ge=0)
    permission_definitions: list[PermissionDefinitionResponse] = Field(default_factory=list)


class RoleCreateRequest(BaseModel):
    """Payload for creating a custom DB-backed role.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If request values are invalid.
    """

    model_config = ConfigDict(extra="forbid")

    role_key: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    permission_keys: list[str] = Field(default_factory=list)

    @field_validator("role_key", mode="before")
    @classmethod
    def normalize_role_key(cls, value: object) -> object:
        """Normalize a custom role identifier before validation.

        Args:
            value: Raw role identifier input.

        Returns:
            object: Lowercase stripped string for string input; original value otherwise.

        Raises:
            None.
        """

        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("name", mode="before")
    @classmethod
    def strip_role_name(cls, value: object) -> object:
        """Strip a custom role name before validation.

        Args:
            value: Raw role name input.

        Returns:
            object: Stripped string for string input; original value otherwise.

        Raises:
            None.
        """

        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        """Strip an optional role description before validation.

        Args:
            value: Raw description input.

        Returns:
            object: Stripped string, None for blank strings, or original value otherwise.

        Raises:
            None.
        """

        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("permission_keys")
    @classmethod
    def normalize_permission_keys(cls, value: list[str]) -> list[str]:
        """Strip and de-duplicate requested permission keys.

        Args:
            value: Raw permission key list.

        Returns:
            list[str]: Ordered unique stripped permission keys.

        Raises:
            None.
        """

        normalized: list[str] = []
        seen: set[str] = set()
        for permission_key in value:
            candidate = permission_key.strip()
            if candidate not in seen:
                normalized.append(candidate)
                seen.add(candidate)
        return normalized


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
            force_password_change=bool(record.get('force_password_change', False)),
            last_login_at=record.get('last_login_at'),
            password_changed_at=record.get('password_changed_at'),
            created_at=record['created_at'],
            updated_at=record['updated_at'],
            **user_access_payload_from_record(record),
        )


class AdminUserListParams(BaseModel):
    """Query parameters for administrative user listing.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If query parameter values are invalid.
    """

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, gt=0, le=100)
    offset: int = Field(default=0, ge=0)


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
    limit: int = Field(gt=0)
    offset: int = Field(ge=0)


class AdminUserCreateRequest(BaseModel):
    """Payload for creating a managed user account.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If request values are invalid.
    """

    email: EmailField
    username: str = Field(min_length=3, max_length=64)
    full_name: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=8, max_length=512)
    is_active: bool = True
    role_keys: list[str] = Field(default_factory=list)
    force_password_change: bool = True

    @field_validator("email", "username", mode="before")
    @classmethod
    def strip_identity_fields(cls, value: object) -> object:
        """Strip managed-user identity fields before validation.

        Args:
            value: Raw email or username input.

        Returns:
            object: Stripped string for string input; original value otherwise.

        Raises:
            None.
        """

        if isinstance(value, str):
            return value.strip()
        return value


class AdminUserUpdateRequest(BaseModel):
    """Payload for updating an existing managed user account.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If request values are invalid.
    """

    email: EmailField | None = None
    username: str | None = Field(default=None, min_length=3, max_length=64)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None

    @field_validator("email", "username", mode="before")
    @classmethod
    def strip_identity_fields(cls, value: object) -> object:
        """Strip managed-user identity fields before validation.

        Args:
            value: Raw email or username input.

        Returns:
            object: Stripped string for string input; original value otherwise.

        Raises:
            None.
        """

        if isinstance(value, str):
            return value.strip()
        return value


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
