# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Application configuration for the Pragma backend.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the backend application.

    Args:
        BaseSettings: Pydantic settings base class.

    Returns:
        None.

    Raises:
        ValidationError: If required configuration is missing or invalid.
    """

    model_config = SettingsConfigDict(
        env_prefix='PRAGMA_',
        env_file=_BACKEND_ROOT / '.env',
        case_sensitive=False,
        extra='ignore',
    )

    database_host: str = Field(min_length=1)
    database_port: int = Field(ge=1, le=65535)
    database_name: str = Field(min_length=1)
    database_user: str = Field(min_length=1)
    database_password: str = Field(min_length=1)
    database_admin_database: str = Field(default='postgres', min_length=1)
    database_pool_min_size: int = Field(default=1, ge=1)
    database_pool_max_size: int = Field(default=10, ge=1)
    jwt_secret_key: str = Field(min_length=16)
    jwt_algorithm: str = Field(default='HS256', min_length=3)
    jwt_access_token_ttl_minutes: int = Field(default=15, ge=1)
    jwt_refresh_token_ttl_days: int = Field(default=7, ge=1)
    refresh_cookie_name: str = Field(default='pragma_refresh_token', min_length=1)
    refresh_cookie_path: str = Field(default='/api/v1/auth', min_length=1)
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: Literal['lax', 'strict', 'none'] = 'lax'
    media_storage_backend: Literal['local'] = 'local'
    media_root: str = Field(default='media', min_length=1)
    media_max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    media_allowed_mime_types: str = Field(
        default='image/jpeg,image/png,image/gif,image/webp',
        min_length=1,
    )
    base_url: str = Field(min_length=1)
    theme_root: str = Field(default='../themes', min_length=1)
    module_root: str = Field(default='../modules', min_length=1)
    theme_active_id: str = Field(default='default', min_length=1)
    theme_default_id: str = Field(default='default', min_length=1)
    log_level: str = Field(default='INFO', min_length=1)
    search_enable_semantic: bool = False
    realtime_enabled: bool = True
    realtime_channel: str = Field(default='pragma_realtime', min_length=1, max_length=63)
    realtime_queue_size: int = Field(default=256, ge=1, le=2048)
    realtime_reconnect_min_seconds: float = Field(default=0.5, gt=0)
    realtime_reconnect_max_seconds: float = Field(default=30.0, gt=0)
    realtime_ticket_ttl_seconds: int = Field(default=60, ge=5, le=600)

    @staticmethod
    def _normalize_theme_identifier(value: str) -> str:
        """Normalize and validate a configured theme identifier.

        Args:
            value: Theme identifier from configuration.

        Returns:
            str: Normalized theme identifier.

        Raises:
            ValueError: If the identifier format is invalid.
        """

        normalized = value.strip().lower()
        is_valid = (
            1 <= len(normalized) <= 64
            and normalized[0].isalnum()
            and normalized[-1].isalnum()
            and all(character.isalnum() or character in {'-', '_'} for character in normalized)
        )
        if not is_valid:
            raise ValueError(
                'Theme id must use lowercase letters, numbers, hyphens, or underscores'
            )
        return normalized

    @model_validator(mode='after')
    def normalize_theme_identifiers(self) -> Settings:
        """Normalize configured theme identifiers before runtime lookup.

        Args:
            None.

        Returns:
            Settings: Validated settings object.

        Raises:
            ValueError: If a configured theme identifier is invalid.
        """

        self.theme_active_id = self._normalize_theme_identifier(self.theme_active_id)
        self.theme_default_id = self._normalize_theme_identifier(self.theme_default_id)
        return self

    @staticmethod
    def _normalize_realtime_channel(value: str) -> str:
        """Normalize and validate a configured realtime channel identifier.

        Args:
            value: Realtime channel identifier from configuration.

        Returns:
            str: Normalized realtime channel identifier.

        Raises:
            ValueError: If the identifier format is invalid.
        """

        normalized = value.strip().lower()
        is_valid = (
            1 <= len(normalized) <= 63
            and normalized[0].isalnum()
            and all(character.isalnum() or character == '_' for character in normalized)
        )
        if not is_valid:
            raise ValueError('Realtime channel must use lowercase letters, numbers, or underscores')
        return normalized

    @model_validator(mode='after')
    def validate_refresh_cookie_policy(self) -> Settings:
        """Validate refresh-cookie security policy compatibility.

        Args:
            None.

        Returns:
            Settings: Validated settings object.

        Raises:
            ValueError: If SameSite=None is configured without secure cookies.
        """

        if self.refresh_cookie_samesite == 'none' and not self.refresh_cookie_secure:
            raise ValueError(
                'refresh_cookie_secure must be true when refresh_cookie_samesite is "none"'
            )
        return self

    @model_validator(mode='after')
    def validate_realtime_settings(self) -> Settings:
        """Validate realtime channel naming and reconnect policy settings.

        Args:
            None.

        Returns:
            Settings: Validated settings object.

        Raises:
            ValueError: If realtime configuration values are inconsistent.
        """

        self.realtime_channel = self._normalize_realtime_channel(self.realtime_channel)
        if self.realtime_reconnect_min_seconds > self.realtime_reconnect_max_seconds:
            raise ValueError(
                'realtime_reconnect_min_seconds must be less than or equal to '
                'realtime_reconnect_max_seconds'
            )
        return self

    @property
    def database_dsn(self) -> str:
        """Build the psycopg connection string for the application database.

        Args:
            None.

        Returns:
            str: psycopg-compatible database DSN.

        Raises:
            None.
        """

        user = quote(self.database_user, safe='')
        password = quote(self.database_password, safe='')
        return (
            f'postgresql://{user}:{password}@{self.database_host}:'
            f'{self.database_port}/{self.database_name}'
        )

    @property
    def maintenance_database_dsn(self) -> str:
        """Build the psycopg connection string for database administration tasks.

        Args:
            None.

        Returns:
            str: psycopg-compatible database DSN for the maintenance database.

        Raises:
            None.
        """

        user = quote(self.database_user, safe='')
        password = quote(self.database_password, safe='')
        return (
            f'postgresql://{user}:{password}@{self.database_host}:'
            f'{self.database_port}/{self.database_admin_database}'
        )

    @property
    def sqlalchemy_database_url(self) -> str:
        """Build the SQLAlchemy URL used by Alembic.

        Args:
            None.

        Returns:
            str: SQLAlchemy database URL for Alembic migrations.

        Raises:
            None.
        """

        user = quote(self.database_user, safe='')
        password = quote(self.database_password, safe='')
        return (
            f'postgresql+psycopg://{user}:{password}@{self.database_host}:'
            f'{self.database_port}/{self.database_name}'
        )

    @property
    def refresh_token_ttl_seconds(self) -> int:
        """Return the refresh token lifetime in seconds.

        Args:
            None.

        Returns:
            int: Refresh token lifetime expressed in seconds.

        Raises:
            None.
        """

        return self.jwt_refresh_token_ttl_days * 24 * 60 * 60

    @property
    def media_root_path(self) -> Path:
        """Resolve the configured media root into an absolute filesystem path.

        Args:
            None.

        Returns:
            Path: Absolute media root path.

        Raises:
            None.
        """

        root = Path(self.media_root)
        if root.is_absolute():
            return root.resolve()
        return (_BACKEND_ROOT / root).resolve()

    @property
    def theme_root_path(self) -> Path:
        """Resolve the configured theme root into an absolute filesystem path.

        Args:
            None.

        Returns:
            Path: Absolute theme root path.

        Raises:
            None.
        """

        root = Path(self.theme_root)
        if root.is_absolute():
            return root.resolve()
        return (_BACKEND_ROOT / root).resolve()

    @property
    def module_root_path(self) -> Path:
        """Resolve the configured module root into an absolute filesystem path.

        Args:
            None.

        Returns:
            Path: Absolute module root path.

        Raises:
            None.
        """

        root = Path(self.module_root)
        if root.is_absolute():
            return root.resolve()
        return (_BACKEND_ROOT / root).resolve()

    @property
    def media_allowed_mime_type_set(self) -> frozenset[str]:
        """Return configured media MIME types as a normalized set.

        Args:
            None.

        Returns:
            frozenset[str]: Normalized allowed MIME types.

        Raises:
            None.
        """

        values = {
            part.strip().lower()
            for part in self.media_allowed_mime_types.split(',')
            if part.strip()
        }
        return frozenset(values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache application settings.

    Args:
        None.

    Returns:
        Settings: Validated application settings.

    Raises:
        ValidationError: If required configuration is missing or invalid.
    """

    return Settings()


def clear_settings_cache() -> None:
    """Clear the cached settings instance.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    get_settings.cache_clear()
