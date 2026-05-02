# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Configuration validation tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pragma.config import Settings


def _settings_kwargs(**overrides: object) -> dict[str, object]:
    """Build minimal Settings constructor values for validation tests.

    Args:
        **overrides: Field values that should replace the valid defaults.

    Returns:
        dict[str, object]: Settings keyword arguments.

    Raises:
        None.
    """

    values: dict[str, object] = {
        'database_host': '127.0.0.1',
        'database_port': 5432,
        'database_name': 'pragma_test',
        'database_user': 'pragma',
        'database_password': 'password',
        'jwt_secret_key': 'test-secret-key-123',
        'base_url': 'http://testserver',
    }
    values.update(overrides)
    return values


def test_settings_rejects_inverted_database_pool_sizes() -> None:
    """Verify DB pool minimum size cannot exceed maximum size.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    with pytest.raises(ValidationError, match='database_pool_min_size'):
        Settings(
            **_settings_kwargs(
                database_pool_min_size=8,
                database_pool_max_size=4,
            )
        )


def test_settings_normalizes_standard_log_level_names() -> None:
    """Verify supported log-level names are normalized before runtime use.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    settings = Settings(**_settings_kwargs(log_level='debug'))

    assert settings.log_level == 'DEBUG'


def test_settings_rejects_invalid_log_level_names() -> None:
    """Verify invalid log-level names fail settings validation.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    with pytest.raises(ValidationError, match='log_level must be one of'):
        Settings(**_settings_kwargs(log_level='verbose'))


def test_settings_rejects_https_base_url_with_insecure_refresh_cookie() -> None:
    """Verify HTTPS deployments must use Secure refresh cookies.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    with pytest.raises(ValidationError, match='base_url uses HTTPS'):
        Settings(**_settings_kwargs(base_url='https://example.com'))


def test_production_settings_reject_placeholder_and_short_secrets() -> None:
    """Verify production runtime mode rejects weak non-Docker secrets.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    with pytest.raises(ValidationError, match='placeholder or weak'):
        Settings(
            **_settings_kwargs(
                runtime_environment='production',
                database_password='replace-with-a-random-database-password',
                jwt_secret_key='replace-with-at-least-32-random-characters',
                refresh_cookie_secure=True,
            )
        )

    with pytest.raises(ValidationError, match='at least 32'):
        Settings(
            **_settings_kwargs(
                runtime_environment='production',
                database_password='short-but-not-placeholder',
                jwt_secret_key='short-but-not-placeholder',
                refresh_cookie_secure=True,
            )
        )


def test_production_settings_accept_strong_secrets_and_private_ai_flag() -> None:
    """Verify strong production secrets and the private-AI opt-in flag load.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    settings = Settings(
        **_settings_kwargs(
            runtime_environment='production',
            database_password='d' * 32,
            jwt_secret_key='j' * 32,
            refresh_cookie_secure=True,
            ai_allow_private_base_urls=True,
        )
    )

    assert settings.runtime_environment == 'production'
    assert settings.ai_allow_private_base_urls is True
