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
    """Verify the Alembic chain creates the required M11 schema objects.

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
                to_regclass('public.pragma_permissions') AS permissions_table,
                to_regclass('public.pragma_roles') AS roles_table,
                to_regclass('public.pragma_role_permissions') AS role_permissions_table,
                to_regclass('public.pragma_user_roles') AS user_roles_table,
                to_regclass('public.alembic_version') AS alembic_table,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'pragma_users'
                      AND column_name = 'password_changed_at'
                ) AS has_password_changed_at,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'pragma_users'
                      AND column_name = 'force_password_change'
                ) AS has_force_password_change,
                (SELECT COUNT(*) FROM pragma_permissions) AS permission_count,
                (SELECT COUNT(*) FROM pragma_roles) AS role_count,
                (SELECT COUNT(*) FROM pragma_role_permissions) AS role_permission_count,
                EXISTS (
                    SELECT 1
                    FROM pragma_roles
                    WHERE role_key = 'administrator' AND is_system = TRUE
                ) AS has_administrator_role,
                EXISTS (
                    SELECT 1
                    FROM pragma_role_permissions
                    WHERE role_key = 'administrator'
                      AND permission_key = 'users.manage'
                ) AS has_administrator_users_manage
            """
        ).fetchone()

    assert row["users_table"] == "pragma_users"
    assert row["install_state_table"] == "pragma_install_state"
    assert row["refresh_tokens_table"] == "pragma_refresh_tokens"
    assert row["permissions_table"] == "pragma_permissions"
    assert row["roles_table"] == "pragma_roles"
    assert row["role_permissions_table"] == "pragma_role_permissions"
    assert row["user_roles_table"] == "pragma_user_roles"
    assert row["alembic_table"] == "alembic_version"
    assert row["has_password_changed_at"] is True
    assert row["has_force_password_change"] is True
    assert row["permission_count"] == 12
    assert row["role_count"] == 4
    assert row["role_permission_count"] == 29
    assert row["has_administrator_role"] is True
    assert row["has_administrator_users_manage"] is True


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
    assert payload["user"]["roles"] == ["administrator"]
    assert "users.manage" in payload["user"]["permissions"]
    assert "modules.manage" in payload["user"]["permissions"]
    assert "content.entries.publish" in payload["user"]["permissions"]

    status_response = client.get("/api/v1/install/status")
    assert status_response.status_code == 200
    assert status_response.json()["is_installed"] is True

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "identity": bootstrap_payload["email"],
            "password": bootstrap_payload["password"],
        },
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["user"]["roles"] == ["administrator"]
    assert "users.manage" in login_payload["user"]["permissions"]
    assert "modules.manage" in login_payload["user"]["permissions"]
    assert "content.entries.publish" in login_payload["user"]["permissions"]


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
