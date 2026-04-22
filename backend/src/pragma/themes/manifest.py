# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Theme manifest models for the Pragma theme runtime.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator

_THEME_ID_PATTERN = re.compile(r'^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$')


class ThemeManifest(BaseModel):
    """Validated manifest for a discoverable theme.

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
    templates_dir: str = Field(default='templates', min_length=1)
    static_dir: str = Field(default='static', min_length=1)

    @field_validator('id')
    @classmethod
    def validate_theme_id(cls, value: str) -> str:
        """Validate the theme identifier format.

        Args:
            value: Theme identifier from the manifest.

        Returns:
            str: Normalized theme identifier.

        Raises:
            ValueError: If the identifier format is invalid.
        """

        normalized = value.strip().lower()
        if not _THEME_ID_PATTERN.fullmatch(normalized):
            raise ValueError(
                'Theme id must use lowercase letters, numbers, hyphens, or underscores'
            )
        return normalized

    @field_validator('templates_dir', 'static_dir')
    @classmethod
    def validate_relative_directory(cls, value: str) -> str:
        """Validate manifest-owned relative directory paths.

        Args:
            value: Directory path from the manifest.

        Returns:
            str: Normalized relative directory path.

        Raises:
            ValueError: If the path is empty, absolute, or escapes the theme root.
        """

        candidate = PurePosixPath(value.strip())
        if candidate.as_posix() in {'', '.'}:
            raise ValueError('Theme manifest directories must not be empty')
        if candidate.is_absolute() or '..' in candidate.parts:
            raise ValueError('Theme manifest directories must stay within the theme root')
        return candidate.as_posix()
