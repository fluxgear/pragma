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
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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
