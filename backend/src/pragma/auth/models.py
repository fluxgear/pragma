# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Authentication request and response models.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from pragma.auth.permissions import get_permission_definitions

PermissionSource = Literal['roles', 'superuser']


def user_access_payload_from_record(record: Mapping[str, Any]) -> dict[str, object]:
    """Build assigned/effective permission response fields from a user record.

    Args:
        record: User record returned by the storage layer.

    Returns:
        dict[str, object]: Access response fields for the user payload.

    Raises:
        None.
    """

    assigned_permissions = [str(value) for value in record.get('permissions', [])]
    if bool(record['is_superuser']):
        effective_permissions = [
            definition.key for definition in get_permission_definitions()
        ]
        return {
            'assigned_permissions': assigned_permissions,
            'effective_permissions': effective_permissions,
            'has_all_permissions': True,
            'permission_source': 'superuser',
            'permissions': effective_permissions,
        }

    return {
        'assigned_permissions': assigned_permissions,
        'effective_permissions': assigned_permissions,
        'has_all_permissions': False,
        'permission_source': 'roles',
        'permissions': assigned_permissions,
    }


class UserResponse(BaseModel):
    """Authenticated user response payload.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    id: UUID
    email: str
    username: str
    full_name: str | None
    is_active: bool
    is_superuser: bool
    roles: list[str] = Field(default_factory=list)
    assigned_permissions: list[str] = Field(default_factory=list)
    effective_permissions: list[str] = Field(default_factory=list)
    has_all_permissions: bool = False
    permission_source: PermissionSource = 'roles'
    permissions: list[str] = Field(default_factory=list)
    force_password_change: bool = False

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> UserResponse:
        """Build a response model from a storage-layer record.

        Args:
            record: User record returned by the storage layer.

        Returns:
            UserResponse: Serialized user payload.

        Raises:
            ValidationError: If record fields are invalid.
        """

        return cls(
            id=record["id"],
            email=str(record["email"]),
            username=str(record["username"]),
            full_name=record["full_name"],
            is_active=bool(record["is_active"]),
            is_superuser=bool(record["is_superuser"]),
            roles=[str(value) for value in record.get('roles', [])],
            force_password_change=bool(record.get('force_password_change', False)),
            **user_access_payload_from_record(record),
        )


class LoginRequest(BaseModel):
    """Login request payload.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    identity: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=512)

    @field_validator("identity", mode="before")
    @classmethod
    def strip_identity(cls, value: object) -> object:
        """Strip login identity before length validation.

        Args:
            value: Raw identity input.

        Returns:
            object: Stripped string for string input; original value otherwise.

        Raises:
            None.
        """

        if isinstance(value, str):
            return value.strip()
        return value


class ChangePasswordRequest(BaseModel):
    """Authenticated password-change request payload.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    current_password: str = Field(min_length=8, max_length=512)
    new_password: str = Field(min_length=8, max_length=512)


class TokenResponse(BaseModel):
    """Access-token response payload.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
