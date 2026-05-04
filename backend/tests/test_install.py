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

from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from pydantic import ValidationError

from pragma.install.models import BootstrapRequest
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


def test_install_status_reports_schema_not_ready_when_bootstrap_dependencies_missing(
    runtime_database: dict[str, str],
) -> None:
    """Verify partial migration tables are not enough for bootstrap readiness.

    Args:
        runtime_database: Environment values for the isolated test database.

    Returns:
        None.

    Raises:
        None.
    """

    from pragma.app import create_app

    dsn = build_database_dsn(runtime_database, runtime_database["PRAGMA_DATABASE_NAME"])
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        connection.execute(
            """
            CREATE TABLE pragma_install_state (
                id INTEGER PRIMARY KEY,
                is_installed BOOLEAN NOT NULL DEFAULT FALSE,
                installed_at TIMESTAMPTZ,
                installed_by_user_id UUID
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE pragma_users (
                id UUID PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT,
                password_hash TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
                last_login_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE pragma_refresh_tokens (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                revoked_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()

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


def test_bootstrap_rejects_missing_or_invalid_configured_setup_secret(
    migrated_database: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify configured setup secrets are required before first-run bootstrap.

    Args:
        migrated_database: Environment values for the migrated test database.
        monkeypatch: Pytest monkeypatch fixture.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    from pragma.app import create_app
    from pragma.config import clear_settings_cache

    del migrated_database
    setup_secret = 'operator-controlled-setup-secret-1234567890'
    monkeypatch.setenv('PRAGMA_SETUP_SECRET', setup_secret)
    clear_settings_cache()

    with TestClient(create_app()) as secret_client:
        missing_response = secret_client.post(
            "/api/v1/install/bootstrap", json=bootstrap_payload
        )
        invalid_response = secret_client.post(
            "/api/v1/install/bootstrap",
            json=bootstrap_payload,
            headers={"X-Pragma-Setup-Secret": "wrong-secret"},
        )
        valid_response = secret_client.post(
            "/api/v1/install/bootstrap",
            json=bootstrap_payload,
            headers={"X-Pragma-Setup-Secret": setup_secret},
        )

    assert missing_response.status_code == 403
    assert missing_response.json() == {
        "detail": "Invalid install setup secret",
        "code": "INVALID_SETUP_SECRET",
    }
    assert invalid_response.status_code == 403
    assert invalid_response.json() == {
        "detail": "Invalid install setup secret",
        "code": "INVALID_SETUP_SECRET",
    }
    assert valid_response.status_code == 201


def test_bootstrap_setup_secret_fails_closed_in_production(
    runtime_database: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify production bootstrap requires an operator setup secret.

    Args:
        runtime_database: Environment values for the isolated test database.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    from pragma.config import get_settings
    from pragma.errors import ConfigError
    from pragma.install.service import verify_bootstrap_setup_secret

    del runtime_database
    monkeypatch.delenv('PRAGMA_SETUP_SECRET', raising=False)
    monkeypatch.delenv('PRAGMA_SETUP_SECRET_FILE', raising=False)
    production_settings = get_settings().model_copy(
        update={"runtime_environment": "production"}
    )

    with pytest.raises(ConfigError) as exc_info:
        verify_bootstrap_setup_secret(production_settings, None)

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == 'SETUP_SECRET_REQUIRED'


def test_bootstrap_setup_secret_uses_file_secret(
    runtime_database: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Verify bootstrap setup secret can be loaded from a configured file.

    Args:
        runtime_database: Environment values for the isolated test database.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory for the setup-secret source file.

    Returns:
        None.

    Raises:
        None.
    """

    from pragma.config import get_settings
    from pragma.errors import ConfigError
    from pragma.install.service import verify_bootstrap_setup_secret

    del runtime_database
    setup_secret = 'file-backed-setup-secret-12345678901234567890'
    setup_secret_file = tmp_path / 'setup-secret'
    setup_secret_file.write_text(f'  {setup_secret}\n', encoding='utf-8')
    monkeypatch.delenv('PRAGMA_SETUP_SECRET', raising=False)
    monkeypatch.setenv('PRAGMA_SETUP_SECRET_FILE', str(setup_secret_file))

    verify_bootstrap_setup_secret(get_settings(), setup_secret)
    with pytest.raises(ConfigError) as exc_info:
        verify_bootstrap_setup_secret(get_settings(), 'wrong-secret')

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 'INVALID_SETUP_SECRET'


def test_bootstrap_setup_secret_rejects_raw_and_file_sources(
    runtime_database: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Verify setup-secret raw and file sources are mutually exclusive.

    Args:
        runtime_database: Environment values for the isolated test database.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory for the setup-secret source file.

    Returns:
        None.

    Raises:
        None.
    """

    from pragma.config import get_settings
    from pragma.errors import ConfigError
    from pragma.install.service import verify_bootstrap_setup_secret

    del runtime_database
    setup_secret_file = tmp_path / 'setup-secret'
    setup_secret_file.write_text('file-backed-setup-secret-12345678901234567890', encoding='utf-8')
    monkeypatch.setenv('PRAGMA_SETUP_SECRET', 'raw-setup-secret-123456789012345678901234')
    monkeypatch.setenv('PRAGMA_SETUP_SECRET_FILE', str(setup_secret_file))

    with pytest.raises(ConfigError) as exc_info:
        verify_bootstrap_setup_secret(get_settings(), 'raw-setup-secret-123456789012345678901234')

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == 'SETUP_SECRET_SOURCE_CONFLICT'


def test_bootstrap_setup_secret_fails_closed_for_invalid_production_file(
    runtime_database: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify production setup fails closed when the configured file is missing.

    Args:
        runtime_database: Environment values for the isolated test database.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    from pragma.config import get_settings
    from pragma.errors import ConfigError
    from pragma.install.service import verify_bootstrap_setup_secret

    del runtime_database
    monkeypatch.delenv('PRAGMA_SETUP_SECRET', raising=False)
    monkeypatch.setenv('PRAGMA_SETUP_SECRET_FILE', '/missing/pragma/setup-secret')
    production_settings = get_settings().model_copy(
        update={"runtime_environment": "production"}
    )

    with pytest.raises(ConfigError) as exc_info:
        verify_bootstrap_setup_secret(production_settings, None)

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == 'SETUP_SECRET_FILE_UNREADABLE'


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


def test_concurrent_bootstrap_allows_only_one_superuser(
    client: TestClient,
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify concurrent first-run bootstrap requests serialize to one root user.

    Args:
        client: FastAPI test client.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    competing_payload = {
        **bootstrap_payload,
        "email": "admin-two@example.com",
        "username": "admin-two",
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                client.post,
                "/api/v1/install/bootstrap",
                json=payload,
            )
            for payload in (bootstrap_payload, competing_payload)
        ]
        responses = [future.result(timeout=15) for future in futures]

    assert sorted(response.status_code for response in responses) == [201, 409]
    failure_response = next(response for response in responses if response.status_code == 409)
    assert failure_response.json() == {
        "detail": "Install bootstrap has already completed",
        "code": "INSTALL_ALREADY_COMPLETED",
    }

    dsn = build_database_dsn(migrated_database, migrated_database["PRAGMA_DATABASE_NAME"])
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM pragma_users
            WHERE is_superuser = TRUE AND is_active = TRUE
            """
        ).fetchone()

    assert row["total"] == 1


def test_bootstrap_request_strips_identity_fields_before_length_validation() -> None:
    """Verify bootstrap email and username strip before validation.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    with pytest.raises(ValidationError):
        BootstrapRequest(
            email='   ',
            username='admin',
            password='valid-password-123',
        )
    with pytest.raises(ValidationError):
        BootstrapRequest(
            email='not-an-email',
            username='admin',
            password='valid-password-123',
        )
    with pytest.raises(ValidationError):
        BootstrapRequest(
            email='admin@example.com',
            username='   ',
            password='valid-password-123',
        )

    request = BootstrapRequest(
        email='  admin@example.com  ',
        username='  admin  ',
        password='valid-password-123',
    )

    assert request.email == 'admin@example.com'
    assert request.username == 'admin'


def test_install_openapi_documents_structured_error_responses(client: TestClient) -> None:
    """Verify install endpoints publish structured error schemas in OpenAPI.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    api_error_schema = schema["components"]["schemas"]["ApiError"]
    assert set(api_error_schema["required"]) == {"detail", "code"}
    assert set(api_error_schema["properties"]) == {"detail", "code"}

    api_error_ref = {"$ref": "#/components/schemas/ApiError"}
    documented_responses = {
        ("/api/v1/install/status", "get"): ("503",),
        ("/api/v1/install/bootstrap", "post"): ("403", "409", "422", "503"),
    }

    for (path, method), status_codes in documented_responses.items():
        responses = schema["paths"][path][method]["responses"]
        for status_code in status_codes:
            assert responses[status_code]["content"]["application/json"]["schema"] == api_error_ref
