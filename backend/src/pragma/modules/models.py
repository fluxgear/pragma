# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Pydantic models for module-state API responses and updates.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from pragma.modules.runtime import ModuleSnapshot


class ModuleStateUpdateRequest(BaseModel):
    """Payload for updating persisted module enable/disable state.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra='forbid')

    enabled: bool


class ModuleStateResponse(BaseModel):
    """Serialized module state for superuser-facing module APIs.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response values are invalid.
    """

    model_config = ConfigDict(extra='forbid')

    module_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=32)
    order: int = Field(ge=0, le=10_000)
    enabled: bool
    loaded: bool
    hooks: list[str] = Field(default_factory=list)
    error_code: str | None = None

    @classmethod
    def from_snapshot(cls, snapshot: ModuleSnapshot) -> ModuleStateResponse:
        """Build an API response payload from a runtime module snapshot.

        Args:
            snapshot: Runtime module state snapshot.

        Returns:
            ModuleStateResponse: Serialized response payload.

        Raises:
            None.
        """

        return cls(
            module_id=snapshot.module_id,
            name=snapshot.name,
            version=snapshot.version,
            order=snapshot.order,
            enabled=snapshot.enabled,
            loaded=snapshot.loaded,
            hooks=list(snapshot.hooks),
            error_code=snapshot.error_code,
        )


class ModuleListResponse(BaseModel):
    """List response payload for discovered backend modules.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response values are invalid.
    """

    model_config = ConfigDict(extra='forbid')

    items: list[ModuleStateResponse] = Field(default_factory=list)
    total: int = Field(ge=0)
