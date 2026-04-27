# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Module manifest models for Pragma's constrained extension runtime.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MODULE_ID_PATTERN = re.compile(r'^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$')
_HOOK_SYMBOL_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


class ModuleHookEvent(StrEnum):
    """Supported module hook events exposed by core content operations.

    Args:
        StrEnum: String enum base class.

    Returns:
        None.

    Raises:
        None.
    """

    CONTENT_ENTRY_CREATED = 'content.entry.created'
    CONTENT_ENTRY_UPDATED = 'content.entry.updated'
    CONTENT_ENTRY_DELETED = 'content.entry.deleted'


def normalize_module_id(value: str) -> str:
    """Normalize and validate a module identifier.

    Args:
        value: Candidate module identifier.

    Returns:
        str: Normalized lowercase module identifier.

    Raises:
        ValueError: If the identifier format is invalid.
    """

    normalized = value.strip().lower()
    if not _MODULE_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            'Module id must use lowercase letters, numbers, hyphens, or underscores'
        )
    return normalized


def _validate_relative_file_path(value: str, label: str) -> str:
    """Validate a module-owned relative file path.

    Args:
        value: Candidate path string.
        label: Human-readable field label for error messages.

    Returns:
        str: Normalized POSIX relative path.

    Raises:
        ValueError: If the path is empty, absolute, or escapes the module root.
    """

    candidate = PurePosixPath(value.strip())
    if candidate.as_posix() in {'', '.'}:
        raise ValueError(f'{label} must not be empty')
    if candidate.is_absolute() or '..' in candidate.parts:
        raise ValueError(f'{label} must stay within the module root')
    return candidate.as_posix()


class ModuleManifest(BaseModel):
    """Validated manifest for a discoverable backend module.

    Args:
        BaseModel: Pydantic base model.

    Returns:
        None.

    Raises:
        ValidationError: If the manifest payload is invalid.
    """

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=500)
    author: str | None = Field(default=None, max_length=255)
    order: int = Field(default=100, ge=0, le=10_000)
    entrypoint: str = Field(default='hooks.py', min_length=1)
    hooks: dict[str, str] = Field(default_factory=dict)

    @field_validator('id')
    @classmethod
    def validate_module_id(cls, value: str) -> str:
        """Validate the module identifier format.

        Args:
            value: Module identifier from the manifest.

        Returns:
            str: Normalized module identifier.

        Raises:
            ValueError: If the identifier format is invalid.
        """

        return normalize_module_id(value)

    @field_validator('entrypoint')
    @classmethod
    def validate_entrypoint(cls, value: str) -> str:
        """Validate the hook entrypoint path.

        Args:
            value: Entrypoint path from the manifest.

        Returns:
            str: Normalized module-local entrypoint path.

        Raises:
            ValueError: If the entrypoint path is invalid.
        """

        return _validate_relative_file_path(value, 'Module entrypoint')

    @field_validator('hooks')
    @classmethod
    def validate_hooks(cls, value: dict[str, str]) -> dict[str, str]:
        """Validate hook-event to callable-name mappings.

        Args:
            value: Hook registration map from the manifest.

        Returns:
            dict[str, str]: Normalized hook mapping.

        Raises:
            ValueError: If an event name or hook callable name is invalid.
        """

        normalized: dict[str, str] = {}
        allowed_events = {event.value for event in ModuleHookEvent}
        for event_name, hook_name in value.items():
            if event_name not in allowed_events:
                raise ValueError(f'Unsupported module hook event: {event_name}')
            candidate = hook_name.strip()
            if not _HOOK_SYMBOL_PATTERN.fullmatch(candidate):
                raise ValueError(f'Invalid hook callable name for {event_name}: {hook_name}')
            normalized[event_name] = candidate
        return normalized
