# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Install and bootstrap request and response models.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from pragma.auth.models import UserResponse


class CapabilityStatus(BaseModel):
    """Capability status for a PostgreSQL extension.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    available: bool
    installed: bool
    default_version: str | None
    installed_version: str | None


class InstallStatusResponse(BaseModel):
    """Install-state response payload.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    schema_ready: bool
    is_installed: bool
    superuser_exists: bool
    capabilities: dict[str, CapabilityStatus]


class BootstrapRequest(BaseModel):
    """Bootstrap request payload for the first super-admin.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=512)
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("email", "username", mode="before")
    @classmethod
    def strip_identity_fields(cls, value: object) -> object:
        """Strip bootstrap identity fields before length validation.

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


class BootstrapResponse(BaseModel):
    """Bootstrap completion payload.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    installed: bool
    user: UserResponse
