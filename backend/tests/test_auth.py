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

from fastapi.testclient import TestClient


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
