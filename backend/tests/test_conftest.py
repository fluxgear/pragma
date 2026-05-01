# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Regression tests for backend test-fixture environment helpers.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import pytest

from tests.conftest import _build_isolated_runtime_env


def test_build_isolated_runtime_env_keeps_generated_database_name(
    monkeypatch: pytest.MonkeyPatch,
    example_env_values: dict[str, str],
) -> None:
    """Ensure host PRAGMA_DATABASE_NAME cannot override isolated worker DB names.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        example_env_values: Parsed environment example values.

    Returns:
        None.

    Raises:
        None.
    """

    monkeypatch.setenv('PRAGMA_DATABASE_NAME', 'pragma')
    monkeypatch.setenv('PRAGMA_DATABASE_HOST', 'isolated-host')

    database_name, env_values = _build_isolated_runtime_env(example_env_values, 'gw0')

    assert database_name.startswith('pragma_test_gw0_')
    assert env_values['PRAGMA_DATABASE_NAME'] == database_name
    assert env_values['PRAGMA_DATABASE_HOST'] == 'isolated-host'
