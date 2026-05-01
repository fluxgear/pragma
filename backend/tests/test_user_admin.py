# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""User-administration and account-hardening integration tests for M11.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pragma.auth.admin_models import AdminUserCreateRequest, AdminUserUpdateRequest


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Create the first super-admin for user-admin tests.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        AssertionError: If bootstrap fails unexpectedly.
    """

    response = client.post('/api/v1/install/bootstrap', json=bootstrap_payload)
    assert response.status_code == 201


def _login_user(client: TestClient, *, identity: str, password: str) -> dict[str, Any]:
    """Log in a user and return the authentication payload.

    Args:
        client: FastAPI test client.
        identity: Email or username credential.
        password: Raw password credential.

    Returns:
        dict[str, Any]: Parsed authentication payload.

    Raises:
        AssertionError: If login fails unexpectedly.
    """

    response = client.post('/api/v1/auth/login', json={'identity': identity, 'password': password})
    assert response.status_code == 200
    return response.json()


def _auth_headers(access_token: str) -> dict[str, str]:
    """Return bearer-auth headers for an access token.

    Args:
        access_token: JWT access token.

    Returns:
        dict[str, str]: Authorization headers.

    Raises:
        None.
    """

    return {'Authorization': f'Bearer {access_token}'}


def _create_managed_user(
    client: TestClient,
    headers: dict[str, str],
    *,
    email: str,
    username: str,
    password: str,
    role_keys: list[str],
    force_password_change: bool = False,
) -> dict[str, Any]:
    """Create a managed user through the M11 user-admin API.

    Args:
        client: FastAPI test client.
        headers: Administrative bearer-auth headers.
        email: User email.
        username: User username.
        password: Initial raw password.
        role_keys: Built-in role assignments.
        force_password_change: Whether the user must rotate password on first use.

    Returns:
        dict[str, Any]: Parsed managed-user response payload.

    Raises:
        AssertionError: If creation fails unexpectedly.
    """

    response = client.post(
        '/api/v1/users',
        headers=headers,
        json={
            'email': email,
            'username': username,
            'password': password,
            'full_name': username.title(),
            'is_active': True,
            'role_keys': role_keys,
            'force_password_change': force_password_change,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_user_admin_lists_roles_and_created_users(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify user administration exposes built-in roles and created users.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    admin_payload = _login_user(
        client,
        identity=bootstrap_payload['email'],
        password=bootstrap_payload['password'],
    )
    admin_headers = _auth_headers(admin_payload['access_token'])

    roles_response = client.get('/api/v1/users/roles', headers=admin_headers)
    assert roles_response.status_code == 200
    role_keys = {item['role_key'] for item in roles_response.json()['items']}
    assert role_keys == {'administrator', 'editor', 'author', 'viewer'}

    created_user = _create_managed_user(
        client,
        admin_headers,
        email='listed@example.com',
        username='listed',
        password='listed-password-123',
        role_keys=['viewer'],
    )
    users_response = client.get('/api/v1/users', headers=admin_headers)
    assert users_response.status_code == 200
    assert any(item['id'] == created_user['id'] for item in users_response.json()['items'])


def test_role_assignment_update_changes_effective_permissions(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify replacing roles changes downstream permission enforcement.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    admin_payload = _login_user(
        client,
        identity=bootstrap_payload['email'],
        password=bootstrap_payload['password'],
    )
    admin_headers = _auth_headers(admin_payload['access_token'])

    content_type_response = client.post(
        '/api/v1/content/types',
        headers=admin_headers,
        json={
            'name': 'Articles',
            'description': 'Role-update fixture',
            'field_definitions': [
                {
                    'name': 'title',
                    'label': 'Title',
                    'kind': 'text',
                    'required': True,
                    'min_length': 3,
                },
            ],
        },
    )
    assert content_type_response.status_code == 201
    content_type = content_type_response.json()

    created_user = _create_managed_user(
        client,
        admin_headers,
        email='role-change@example.com',
        username='rolechange',
        password='rolechange-password-123',
        role_keys=['author'],
    )

    assign_response = client.put(
        f"/api/v1/users/{created_user['id']}/roles",
        headers=admin_headers,
        json={'role_keys': ['viewer']},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()['roles'] == ['viewer']

    viewer_payload = _login_user(
        client,
        identity='role-change@example.com',
        password='rolechange-password-123',
    )
    viewer_headers = _auth_headers(viewer_payload['access_token'])
    denied_response = client.post(
        '/api/v1/content/entries',
        headers=viewer_headers,
        json={
            'content_type_id': content_type['id'],
            'slug': None,
            'status': 'draft',
            'payload': {'title': 'Blocked'},
        },
    )
    assert denied_response.status_code == 403
    assert denied_response.json() == {
        'detail': 'Permission content.entries.write is required',
        'code': 'AUTH_PERMISSION_DENIED',
    }


def test_password_reset_revokes_refresh_and_forces_password_change(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify password reset revokes refresh sessions and forces rotation.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    admin_payload = _login_user(
        client,
        identity=bootstrap_payload['email'],
        password=bootstrap_payload['password'],
    )
    admin_headers = _auth_headers(admin_payload['access_token'])
    created_user = _create_managed_user(
        client,
        admin_headers,
        email='reset@example.com',
        username='resetuser',
        password='reset-password-123',
        role_keys=['editor'],
    )

    _login_user(client, identity='reset@example.com', password='reset-password-123')
    reset_response = client.post(
        f"/api/v1/users/{created_user['id']}/password-reset",
        headers=admin_headers,
    )
    assert reset_response.status_code == 200
    temporary_password = reset_response.json()['temporary_password']
    assert len(temporary_password) >= 8

    refresh_response = client.post('/api/v1/auth/refresh')
    assert refresh_response.status_code == 401
    assert refresh_response.json() == {
        'detail': 'Refresh token is not active',
        'code': 'TOKEN_REVOKED',
    }

    rotated_payload = _login_user(client, identity='reset@example.com', password=temporary_password)
    assert rotated_payload['user']['force_password_change'] is True


def test_user_deactivation_blocks_future_login(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify deactivated users can no longer authenticate.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    admin_payload = _login_user(
        client,
        identity=bootstrap_payload['email'],
        password=bootstrap_payload['password'],
    )
    admin_headers = _auth_headers(admin_payload['access_token'])
    created_user = _create_managed_user(
        client,
        admin_headers,
        email='inactive@example.com',
        username='inactiveuser',
        password='inactive-password-123',
        role_keys=['viewer'],
    )

    deactivate_response = client.patch(
        f"/api/v1/users/{created_user['id']}",
        headers=admin_headers,
        json={'is_active': False},
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()['is_active'] is False

    login_response = client.post(
        '/api/v1/auth/login',
        json={'identity': 'inactive@example.com', 'password': 'inactive-password-123'},
    )
    assert login_response.status_code == 401
    assert login_response.json() == {
        'detail': 'User account is inactive',
        'code': 'AUTH_INACTIVE',
    }


def test_root_cannot_deactivate_own_account(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify the active root account cannot self-deactivate.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    admin_payload = _login_user(
        client,
        identity=bootstrap_payload['email'],
        password=bootstrap_payload['password'],
    )
    admin_headers = _auth_headers(admin_payload['access_token'])

    response = client.patch(
        f"/api/v1/users/{admin_payload['user']['id']}",
        headers=admin_headers,
        json={'is_active': False},
    )
    assert response.status_code == 400
    assert response.json() == {
        'detail': 'You cannot deactivate your own account',
        'code': 'AUTH_SELF_DEACTIVATE_FORBIDDEN',
    }


def test_admin_user_requests_strip_identity_fields_before_length_validation() -> None:
    """Verify user-admin identity fields strip before length validation.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    with pytest.raises(ValidationError):
        AdminUserCreateRequest(
            email='   ',
            username='managed',
            password='valid-password',
        )
    with pytest.raises(ValidationError):
        AdminUserCreateRequest(
            email='managed@example.com',
            username='   ',
            password='valid-password',
        )
    with pytest.raises(ValidationError):
        AdminUserUpdateRequest(email='   ')
    with pytest.raises(ValidationError):
        AdminUserUpdateRequest(username='   ')

    create_request = AdminUserCreateRequest(
        email='  managed@example.com  ',
        username='  managed  ',
        password='valid-password',
    )
    update_request = AdminUserUpdateRequest(
        email='  managed-updated@example.com  ',
        username='  managed-updated  ',
    )

    assert create_request.email == 'managed@example.com'
    assert create_request.username == 'managed'
    assert update_request.email == 'managed-updated@example.com'
    assert update_request.username == 'managed-updated'
