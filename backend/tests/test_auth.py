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
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg import Connection
from pydantic import ValidationError

from pragma.auth import service as auth_service
from pragma.auth.models import LoginRequest
from pragma.auth.security import REFRESH_TOKEN_TYPE, decode_token
from pragma.config import get_settings
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


def test_login_success_sets_refresh_cookie(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify successful login returns an access token and refresh cookie.

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


def test_login_failure_returns_structured_error(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify login failure returns the structured API error contract.

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
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid credentials",
        "code": "INVALID_CREDENTIALS",
    }


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


def test_concurrent_refresh_reuse_creates_single_successor(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify concurrent reuse of one refresh token creates one successor.

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
        assert successor_row == {"active_count": 1, "total_count": 1}
    finally:
        first_lookup_release.set()
        storage.close()


def test_change_password_revokes_existing_refresh_session(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify self-service password change revokes existing refresh sessions.

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

    change_response = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
        json={
            "current_password": bootstrap_payload["password"],
            "new_password": "new-bootstrap-password-123",
        },
    )
    assert change_response.status_code == 200

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
