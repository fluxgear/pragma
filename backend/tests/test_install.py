# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Install-state and migration integration tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from tests.helpers import build_database_dsn


def test_install_status_reports_schema_not_ready_before_migrations(
    runtime_database: dict[str, str],
) -> None:
    """Verify install status reports a clean, unmigrated database accurately.

    Args:
        runtime_database: Environment values for the isolated test database.

    Returns:
        None.

    Raises:
        None.
    """

    from pragma.app import create_app

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/install/status")

    assert response.status_code == 200
    assert response.json()["schema_ready"] is False
    assert response.json()["is_installed"] is False


def test_migrations_create_expected_tables(migrated_database: dict[str, str]) -> None:
    """Verify the Alembic baseline creates the required M1 tables.

    Args:
        migrated_database: Environment values for the migrated test database.

    Returns:
        None.

    Raises:
        None.
    """

    dsn = build_database_dsn(migrated_database, migrated_database["PRAGMA_DATABASE_NAME"])
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT
                to_regclass('public.pragma_users') AS users_table,
                to_regclass('public.pragma_install_state') AS install_state_table,
                to_regclass('public.pragma_refresh_tokens') AS refresh_tokens_table,
                to_regclass('public.alembic_version') AS alembic_table
            """
        ).fetchone()

    assert row["users_table"] == "pragma_users"
    assert row["install_state_table"] == "pragma_install_state"
    assert row["refresh_tokens_table"] == "pragma_refresh_tokens"
    assert row["alembic_table"] == "alembic_version"


def test_install_status_reports_clean_system_after_migration(client: TestClient) -> None:
    """Verify install status reports a migrated but unbootstrapped system.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.get("/api/v1/install/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_ready"] is True
    assert payload["is_installed"] is False
    assert payload["superuser_exists"] is False
    assert set(payload["capabilities"].keys()) == {"pg_trgm", "pgvector"}
    for capability_name in ("pg_trgm", "pgvector"):
        capability = payload["capabilities"][capability_name]
        assert capability["available"] is True
        assert capability["installed"] is True
        assert capability["default_version"] is not None
        assert capability["installed_version"] is not None


def test_bootstrap_creates_first_superuser(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify bootstrap creates the first super-admin and marks installation complete.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.post("/api/v1/install/bootstrap", json=bootstrap_payload)

    assert response.status_code == 201
    payload = response.json()
    assert payload["installed"] is True
    assert payload["user"]["email"] == bootstrap_payload["email"]
    assert payload["user"]["is_superuser"] is True

    status_response = client.get("/api/v1/install/status")
    assert status_response.status_code == 200
    assert status_response.json()["is_installed"] is True


def test_bootstrap_rejects_second_attempt(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify bootstrap cannot run a second time after install completion.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    first_response = client.post("/api/v1/install/bootstrap", json=bootstrap_payload)
    second_response = client.post("/api/v1/install/bootstrap", json=bootstrap_payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "Install bootstrap has already completed",
        "code": "INSTALL_ALREADY_COMPLETED",
    }
