# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Startup and system-endpoint integration tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from pragma.app import create_app
from pragma.errors import StorageError
from tests.helpers import build_runtime_env


def test_health_endpoint_returns_ok(runtime_database: dict[str, str]) -> None:
    """Verify the liveness endpoint responds on a clean database.

    Args:
        runtime_database: Environment values for the isolated test database.

    Returns:
        None.

    Raises:
        None.
    """

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_startup_fails_with_invalid_database(
    example_env_values: dict[str, str],
    apply_runtime_env: callable,
) -> None:
    """Verify application startup fails clearly for an invalid database target.

    Args:
        example_env_values: Parsed environment example values.
        apply_runtime_env: Helper that applies runtime environment values.

    Returns:
        None.

    Raises:
        None.
    """

    invalid_env = build_runtime_env(
        example_env_values,
        f"pragma_missing_{uuid4().hex[:8]}",
    )
    apply_runtime_env(invalid_env)

    with pytest.raises(StorageError), TestClient(create_app()):
        pass


def test_readiness_reports_schema_status(client: TestClient) -> None:
    """Verify readiness reports database and capability state after migration.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.get("/api/v1/system/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "up"
    assert payload["schema_ready"] is True
    assert set(payload["capabilities"].keys()) == {"pg_trgm", "pgvector"}
    for capability_name in ("pg_trgm", "pgvector"):
        capability = payload["capabilities"][capability_name]
        assert capability["available"] is True
        assert capability["installed"] is True
        assert capability["default_version"] is not None
        assert capability["installed_version"] is not None
