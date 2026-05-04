# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Authentication integration tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg import Connection
from pydantic import ValidationError

from pragma.app import create_app
from pragma.auth import service as auth_service
from pragma.auth.models import LoginRequest
from pragma.auth.security import REFRESH_TOKEN_TYPE, decode_token
from pragma.config import clear_settings_cache, get_settings
from pragma.errors import AuthError
from pragma.storage.pool import DatabasePool


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Create the first super-admin for auth-flow tests.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        AssertionError: If bootstrap fails unexpectedly.
    """

    response = client.post("/api/v1/install/bootstrap", json=bootstrap_payload)
    assert response.status_code == 201


def _login_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> dict[str, object]:
    """Log in the bootstrapped admin and return the auth payload.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        dict[str, object]: Parsed login response payload.

    Raises:
        AssertionError: If login fails unexpectedly.
    """

    response = client.post(
        "/api/v1/auth/login",
        json={
            "identity": bootstrap_payload["email"],
            "password": bootstrap_payload["password"],
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture()
def samesite_none_client(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: dict[str, str],
) -> Iterator[TestClient]:
    """Return a test client configured for SameSite=None refresh cookies.

    Args:
        monkeypatch: Pytest monkeypatch helper.
        migrated_database: Migrated database environment for this test.

    Returns:
        Iterator[TestClient]: HTTPS test client with cross-site cookies enabled.

    Raises:
        None.
    """

    _ = migrated_database
    monkeypatch.setenv("PRAGMA_REFRESH_COOKIE_SAMESITE", "none")
    monkeypatch.setenv("PRAGMA_REFRESH_COOKIE_SECURE", "true")
    monkeypatch.setenv("PRAGMA_BASE_URL", "https://pragma.example")
    clear_settings_cache()
    try:
        with TestClient(
            create_app(),
            base_url="https://api.pragma.example",
        ) as test_client:
            yield test_client
    finally:
        clear_settings_cache()


def test_login_success_sets_refresh_cookie(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify successful login returns validated JWTs and refresh cookie.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    response = client.post(
        "/api/v1/auth/login",
        json={
            "identity": bootstrap_payload["email"],
            "password": bootstrap_payload["password"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["email"] == bootstrap_payload["email"]
    assert "pragma_refresh_token=" in response.headers["set-cookie"]

    settings = get_settings()
    access_payload = decode_token(
        settings=settings,
        token=payload["access_token"],
        expected_token_type="access",
    )
    assert access_payload["iss"] == settings.jwt_issuer
    assert access_payload["aud"] == settings.jwt_audience
    assert "pwd" in access_payload

    refresh_token = client.cookies.get(settings.refresh_cookie_name)
    assert refresh_token is not None
    refresh_payload = decode_token(
        settings=settings,
        token=refresh_token,
        expected_token_type=REFRESH_TOKEN_TYPE,
    )
    assert refresh_payload["iss"] == settings.jwt_issuer
    assert refresh_payload["aud"] == settings.jwt_audience


def test_login_failure_returns_structured_error(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify login failures keep the structured API error contract.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch helper.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    response = client.post(
        "/api/v1/auth/login",
        json={
            "identity": bootstrap_payload["email"],
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid credentials",
        "code": "INVALID_CREDENTIALS",
    }

    verify_calls: list[tuple[str, str]] = []

    def fake_verify_password(password: str, password_hash: str) -> bool:
        verify_calls.append((password, password_hash))
        return False

    monkeypatch.setattr(auth_service, "verify_password", fake_verify_password)
    missing_response = client.post(
        "/api/v1/auth/login",
        json={"identity": "missing@example.com", "password": "missing-password"},
    )

    assert missing_response.status_code == 401
    assert missing_response.json() == {
        "detail": "Invalid credentials",
        "code": "INVALID_CREDENTIALS",
    }
    assert len(verify_calls) == 1
    assert verify_calls[0][0] == "missing-password"

    logged_validation_errors: list[dict[str, object]] = []

    def fake_validation_warning(
        message: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        _ = args
        if message != "Request validation failed":
            return
        extra = kwargs.get("extra")
        if not isinstance(extra, dict):
            return
        errors = extra.get("errors")
        if isinstance(errors, list):
            logged_validation_errors.extend(
                error for error in errors if isinstance(error, dict)
            )

    monkeypatch.setattr("pragma.errors.logger.warning", fake_validation_warning)
    validation_response = client.post(
        "/api/v1/auth/login",
        json={
            "identity": "invalid@example.com",
            "password": {
                "raw": "super-secret-password",
                "api_key": "sk-test-secret-key",
            },
        },
    )

    assert validation_response.status_code == 422
    assert validation_response.json() == {
        "detail": "Request validation failed",
        "code": "VALIDATION_ERROR",
    }
    assert logged_validation_errors
    assert all("input" not in error for error in logged_validation_errors)
    assert all("super-secret-password" not in str(error) for error in logged_validation_errors)
    assert all("sk-test-secret-key" not in str(error) for error in logged_validation_errors)


def test_refresh_success_rotates_session(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify refresh succeeds when a valid refresh cookie is present.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    first_login = _login_admin(client, bootstrap_payload)
    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"] != first_login["access_token"]
    assert "pragma_refresh_token=" in response.headers["set-cookie"]


def test_samesite_none_refresh_requires_same_site_origin(
    samesite_none_client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify SameSite=None refresh rejects missing or cross-site origins.

    Args:
        samesite_none_client: HTTPS client configured for SameSite=None cookies.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(samesite_none_client, bootstrap_payload)
    _login_admin(samesite_none_client, bootstrap_payload)

    missing_origin_response = samesite_none_client.post("/api/v1/auth/refresh")
    assert missing_origin_response.status_code == 403
    assert missing_origin_response.json() == {
        "detail": "Origin or Referer header is required",
        "code": "CSRF_ORIGIN_REQUIRED",
    }

    cross_site_response = samesite_none_client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://evil.example"},
    )
    assert cross_site_response.status_code == 403
    assert cross_site_response.json() == {
        "detail": "Origin is not allowed for this request",
        "code": "CSRF_ORIGIN_FORBIDDEN",
    }

    malformed_origin_response = samesite_none_client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://[::1"},
    )
    assert malformed_origin_response.status_code == 403
    assert malformed_origin_response.json() == {
        "detail": "Origin is not allowed for this request",
        "code": "CSRF_ORIGIN_FORBIDDEN",
    }

    same_site_response = samesite_none_client.post(
        "/api/v1/auth/refresh",
        headers={"Origin": "https://pragma.example"},
    )
    assert same_site_response.status_code == 200
    assert same_site_response.json()["token_type"] == "bearer"


def test_concurrent_refresh_reuse_creates_single_successor(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify concurrent reuse revokes the rotated successor.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch helper.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    _login_admin(client, bootstrap_payload)
    settings = get_settings()
    refresh_token = client.cookies.get(settings.refresh_cookie_name)
    assert refresh_token is not None

    token_payload = decode_token(
        settings=settings,
        token=refresh_token,
        expected_token_type=REFRESH_TOKEN_TYPE,
    )
    refresh_session_id = UUID(str(token_payload["jti"]))

    storage = DatabasePool(settings)
    storage.open()
    first_lookup_started = Event()
    first_lookup_release = Event()
    first_refresh_started = Event()
    second_refresh_started = Event()
    lookup_lock = Lock()
    lookup_count = 0
    original_get_user_by_id = auth_service.get_user_by_id

    def delayed_get_user_by_id(
        connection: Connection, user_id: UUID
    ) -> dict[str, object] | None:
        nonlocal lookup_count

        user = original_get_user_by_id(connection, user_id)
        with lookup_lock:
            lookup_count += 1
            is_first_lookup = lookup_count == 1
            if is_first_lookup:
                first_lookup_started.set()

        if is_first_lookup:
            assert first_lookup_release.wait(timeout=5)
        return user

    def refresh_once(started: Event) -> tuple[str, str]:
        started.set()
        try:
            auth_service.refresh_user_session(storage, settings, refresh_token)
        except AuthError as exc:
            return ("auth_error", exc.code)
        return ("success", "")

    monkeypatch.setattr(auth_service, "get_user_by_id", delayed_get_user_by_id)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(refresh_once, first_refresh_started)
            assert first_refresh_started.wait(timeout=5)
            assert first_lookup_started.wait(timeout=5)

            second_future = executor.submit(refresh_once, second_refresh_started)
            assert second_refresh_started.wait(timeout=5)
            time.sleep(0.2)
            with lookup_lock:
                assert lookup_count == 1

            first_lookup_release.set()
            results = [
                first_future.result(timeout=5),
                second_future.result(timeout=5),
            ]

        with storage.connection() as connection:
            successor_row = connection.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE revoked_at IS NULL) AS active_count,
                    COUNT(*) AS total_count
                FROM pragma_refresh_tokens
                WHERE rotated_from_id = %s
                """,
                (refresh_session_id,),
            ).fetchone()

        assert results.count(("success", "")) == 1
        assert results.count(("auth_error", "TOKEN_REVOKED")) == 1
        assert successor_row == {"active_count": 0, "total_count": 1}
    finally:
        first_lookup_release.set()
        storage.close()


def test_change_password_revokes_existing_refresh_session(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify self-service password change revokes existing sessions.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    login_payload = _login_admin(client, bootstrap_payload)
    old_access_token = login_payload["access_token"]

    change_response = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {old_access_token}"},
        json={
            "current_password": bootstrap_payload["password"],
            "new_password": "new-bootstrap-password-123",
        },
    )
    assert change_response.status_code == 200

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert me_response.status_code == 401
    assert me_response.json() == {
        "detail": "Access token was issued before the current password change",
        "code": "TOKEN_REVOKED",
    }

    refresh_response = client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 401
    assert refresh_response.json() == {
        "detail": "Refresh token is not active",
        "code": "TOKEN_REVOKED",
    }


def test_refresh_failure_without_cookie(client: TestClient) -> None:
    """Verify refresh fails with a structured error when the cookie is missing.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Refresh token is required",
        "code": "REFRESH_TOKEN_REQUIRED",
    }


def test_protected_endpoint_requires_auth(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify protected endpoints reject requests without an access token.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required",
        "code": "AUTH_REQUIRED",
    }


def test_auth_openapi_documents_structured_error_responses(client: TestClient) -> None:
    """Verify auth endpoints publish structured error schemas in OpenAPI.

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
        ("/api/v1/auth/login", "post"): ("401", "422", "503"),
        ("/api/v1/auth/refresh", "post"): ("401", "422", "503"),
        ("/api/v1/auth/me", "get"): ("401", "503"),
        ("/api/v1/auth/change-password", "post"): ("401", "422", "503"),
    }

    for (path, method), status_codes in documented_responses.items():
        responses = schema["paths"][path][method]["responses"]
        for status_code in status_codes:
            assert responses[status_code]["content"]["application/json"]["schema"] == api_error_ref


def test_current_user_returns_identity(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify the authenticated identity endpoint returns the current user.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    login_payload = _login_admin(client, bootstrap_payload)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == bootstrap_payload["email"]


def test_logout_clears_refresh_cookie(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify logout clears the refresh cookie and revokes the session.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    _login_admin(client, bootstrap_payload)
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert "pragma_refresh_token=" in response.headers["set-cookie"]


def test_samesite_none_logout_requires_same_site_origin_or_referer(
    samesite_none_client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify SameSite=None logout rejects unsafe cross-site requests.

    Args:
        samesite_none_client: HTTPS client configured for SameSite=None cookies.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(samesite_none_client, bootstrap_payload)
    _login_admin(samesite_none_client, bootstrap_payload)

    missing_origin_response = samesite_none_client.post("/api/v1/auth/logout")
    assert missing_origin_response.status_code == 403
    assert missing_origin_response.json() == {
        "detail": "Origin or Referer header is required",
        "code": "CSRF_ORIGIN_REQUIRED",
    }

    cross_site_response = samesite_none_client.post(
        "/api/v1/auth/logout",
        headers={"Referer": "https://evil.example/account"},
    )
    assert cross_site_response.status_code == 403
    assert cross_site_response.json() == {
        "detail": "Origin is not allowed for this request",
        "code": "CSRF_ORIGIN_FORBIDDEN",
    }

    malformed_referer_response = samesite_none_client.post(
        "/api/v1/auth/logout",
        headers={"Referer": "http://[::1/account"},
    )
    assert malformed_referer_response.status_code == 403
    assert malformed_referer_response.json() == {
        "detail": "Origin is not allowed for this request",
        "code": "CSRF_ORIGIN_FORBIDDEN",
    }

    same_site_response = samesite_none_client.post(
        "/api/v1/auth/logout",
        headers={"Referer": "https://api.pragma.example/app"},
    )
    assert same_site_response.status_code == 204
    assert "pragma_refresh_token=" in same_site_response.headers["set-cookie"]


def test_login_request_strips_identity_before_length_validation() -> None:
    """Verify login identity strips before Pydantic length validation.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    with pytest.raises(ValidationError):
        LoginRequest(identity='   ', password='valid-password')

    request = LoginRequest(identity='  admin@example.com  ', password='valid-password')

    assert request.identity == 'admin@example.com'
