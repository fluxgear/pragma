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
