# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Pydantic models for theme administration and safe design settings."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_HEX_COLOR_PATTERN = re.compile(r'^#[0-9a-fA-F]{6}$')
_THEME_ID_PATTERN = re.compile(r'^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$')


class ThemeTypographyPreset(StrEnum):
    """Safe typography presets exposed to public templates."""

    SYSTEM = 'system'
    SERIF = 'serif'
    EDITORIAL = 'editorial'


class ThemeSpacingScale(StrEnum):
    """Safe spacing scales exposed to public templates."""

    COMPACT = 'compact'
    COMFORTABLE = 'comfortable'
    SPACIOUS = 'spacious'


class ThemeRadiusScale(StrEnum):
    """Safe border-radius scales exposed to public templates."""

    NONE = 'none'
    SMALL = 'small'
    MEDIUM = 'medium'
    LARGE = 'large'


class ThemeDesignSettings(BaseModel):
    """Safe public design settings for theme templates."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, use_enum_values=True)

    primary_color: str = '#2563eb'
    accent_color: str = '#7c3aed'
    background_color: str = '#ffffff'
    text_color: str = '#111827'
    typography_preset: ThemeTypographyPreset = ThemeTypographyPreset.SYSTEM
    spacing_scale: ThemeSpacingScale = ThemeSpacingScale.COMFORTABLE
    radius_scale: ThemeRadiusScale = ThemeRadiusScale.MEDIUM

    @field_validator('primary_color', 'accent_color', 'background_color', 'text_color')
    @classmethod
    def validate_hex_color(cls, value: str) -> str:
        """Validate and normalize a hex color token."""

        normalized = value.strip().lower()
        if not _HEX_COLOR_PATTERN.fullmatch(normalized):
            raise ValueError('Design color values must be six-digit hex colors')
        return normalized

    def warning_messages(self) -> list[str]:
        """Return non-blocking design quality warnings."""

        warnings: list[str] = []
        if _contrast_ratio(self.text_color, self.background_color) < 4.5:
            warnings.append('Text and background colors may not meet WCAG AA contrast.')
        if _contrast_ratio(self.primary_color, self.background_color) < 3.0:
            warnings.append('Primary color may not have enough contrast on the background.')
        if _contrast_ratio(self.accent_color, self.background_color) < 3.0:
            warnings.append('Accent color may not have enough contrast on the background.')
        return warnings


class ThemeDesignSettingsUpdate(BaseModel):
    """Partial update payload for safe public design settings."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, use_enum_values=True)

    primary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    text_color: str | None = None
    typography_preset: ThemeTypographyPreset | None = None
    spacing_scale: ThemeSpacingScale | None = None
    radius_scale: ThemeRadiusScale | None = None

    @model_validator(mode='after')
    def validate_as_settings(self) -> ThemeDesignSettingsUpdate:
        """Reuse full settings validation for supplied fields."""

        supplied = self.model_dump(exclude_none=True)
        if supplied:
            ThemeDesignSettings(**supplied)
        return self


class ThemeManifestResponse(BaseModel):
    """Admin-safe theme manifest projection."""

    model_config = ConfigDict(extra='forbid')

    id: str
    name: str
    version: str
    description: str | None = None
    author: str | None = None
    active: bool = False
    default: bool = False
    current: bool = False
    available: bool = True


class ThemeSettingsResponse(BaseModel):
    """Serialized singleton theme administration state."""

    model_config = ConfigDict(extra='forbid')

    active_theme_id: str
    default_theme_id: str
    current_theme_id: str | None = None
    persisted_active_theme_id: str | None = None
    design_settings: ThemeDesignSettings = Field(default_factory=ThemeDesignSettings)
    design_warnings: list[str] = Field(default_factory=list)
    themes: list[ThemeManifestResponse] = Field(default_factory=list)


class ThemeSettingsUpdateRequest(BaseModel):
    """Update payload for active theme and design settings."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    active_theme_id: str | None = Field(default=None, min_length=1, max_length=64)
    design_settings: ThemeDesignSettingsUpdate | None = None

    @field_validator('active_theme_id')
    @classmethod
    def validate_theme_id(cls, value: str | None) -> str | None:
        """Normalize and validate requested active theme ids."""

        if value is None:
            return None
        normalized = value.strip().lower()
        if not _THEME_ID_PATTERN.fullmatch(normalized):
            raise ValueError(
                'Theme id must use lowercase letters, numbers, hyphens, or underscores'
            )
        return normalized


def design_settings_from_mapping(value: Any) -> ThemeDesignSettings:
    """Build safe design settings from persisted JSON."""

    if not isinstance(value, dict):
        return ThemeDesignSettings()
    return ThemeDesignSettings(**value)


def merge_design_settings(
    existing: ThemeDesignSettings,
    update: ThemeDesignSettingsUpdate | None,
) -> ThemeDesignSettings:
    """Merge a partial update into existing safe design settings."""

    if update is None:
        return existing
    values = existing.model_dump()
    values.update(update.model_dump(exclude_none=True))
    return ThemeDesignSettings(**values)


def _contrast_ratio(foreground: str, background: str) -> float:
    """Calculate WCAG contrast ratio for two normalized hex colors."""

    fore = _relative_luminance(foreground)
    back = _relative_luminance(background)
    lighter = max(fore, back)
    darker = min(fore, back)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(value: str) -> float:
    """Calculate relative luminance for a normalized hex color."""

    channels = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2])
