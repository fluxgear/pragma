# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Pydantic contracts for navigation menu administration."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_RELATIVE_PATH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~!$&()*+,;=:@%/-]*(?:[?#].*)?$")
_ALLOWED_ABSOLUTE_SCHEMES = {'http', 'https'}


class NavigationLinkType(StrEnum):
    """Supported primary navigation link targets."""

    CONTENT_ENTRY = 'content_entry'
    CUSTOM_URL = 'custom_url'


class NavigationMenuItemRequest(BaseModel):
    """One submitted menu item in replacement order."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, use_enum_values=True)

    label: str = Field(min_length=1, max_length=80)
    link_type: NavigationLinkType
    content_entry_id: UUID | None = None
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    enabled: bool = True

    @field_validator('label')
    @classmethod
    def validate_label(cls, value: str) -> str:
        """Normalize and validate display labels."""

        normalized = ' '.join(value.split())
        if not normalized:
            raise ValueError('Navigation item labels are required')
        return normalized

    @field_validator('url')
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        """Allow relative paths and http(s) URLs only."""

        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError('Custom URLs are required for custom navigation links')
        if any(character in normalized for character in ('\r', '\n', '\t')):
            raise ValueError('Custom URLs must not contain control characters')

        parsed = urlsplit(normalized)
        if parsed.scheme:
            if parsed.scheme.lower() not in _ALLOWED_ABSOLUTE_SCHEMES or not parsed.netloc:
                raise ValueError('Custom URLs must be relative paths or http(s) URLs')
            return normalized

        if parsed.netloc or normalized.startswith('//'):
            raise ValueError('Scheme-relative custom URLs are not supported')

        if normalized.startswith(('/', './', '../', '#', '?')):
            return normalized
        if _RELATIVE_PATH_PATTERN.fullmatch(normalized):
            return normalized
        raise ValueError('Custom URLs must be relative paths or http(s) URLs')

    @model_validator(mode='after')
    def validate_target_shape(self) -> Self:
        """Require exactly one target shape for each link type."""

        if self.link_type == NavigationLinkType.CONTENT_ENTRY:
            if self.content_entry_id is None:
                raise ValueError('Internal navigation links require content_entry_id')
            if self.url is not None:
                raise ValueError('Internal navigation links must not include url')
        if self.link_type == NavigationLinkType.CUSTOM_URL:
            if self.url is None:
                raise ValueError('Custom navigation links require url')
            if self.content_entry_id is not None:
                raise ValueError('Custom navigation links must not include content_entry_id')
        return self


class NavigationMenuReplaceRequest(BaseModel):
    """Primary menu replacement payload."""

    model_config = ConfigDict(extra='forbid')

    items: list[NavigationMenuItemRequest] = Field(default_factory=list, max_length=100)


class NavigationMenuItemResponse(BaseModel):
    """Persisted menu item projection."""

    model_config = ConfigDict(extra='forbid', use_enum_values=True)

    id: UUID
    position: int
    label: str
    link_type: NavigationLinkType
    enabled: bool
    content_entry_id: UUID | None = None
    url: str | None = None
    href: str | None = None
    content_type_slug: str | None = None
    entry_slug: str | None = None
    entry_status: str | None = None


class NavigationWarningResponse(BaseModel):
    """Non-blocking warning emitted with a menu snapshot."""

    model_config = ConfigDict(extra='forbid')

    code: str
    detail: str
    item_position: int
    item_label: str
    content_entry_id: UUID | None = None


class NavigationMenuResponse(BaseModel):
    """Current primary navigation menu with validation warnings."""

    model_config = ConfigDict(extra='forbid')

    key: str = 'primary'
    items: list[NavigationMenuItemResponse] = Field(default_factory=list)
    warnings: list[NavigationWarningResponse] = Field(default_factory=list)
