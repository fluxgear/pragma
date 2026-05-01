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
    _create_managed_user(
        client,
        admin_headers,
        email='listed-two@example.com',
        username='listedtwo',
        password='listed-password-456',
        role_keys=['viewer'],
    )

    users_response = client.get('/api/v1/users', headers=admin_headers)
    assert users_response.status_code == 200
    users_payload = users_response.json()
    assert users_payload['total'] == 3
    assert users_payload['limit'] == 50
    assert users_payload['offset'] == 0
    assert any(item['id'] == created_user['id'] for item in users_payload['items'])
    assert all('password_hash' not in item for item in users_payload['items'])

    paged_response = client.get('/api/v1/users?limit=1&offset=1', headers=admin_headers)
    assert paged_response.status_code == 200
    paged_payload = paged_response.json()
    assert paged_payload['total'] == 3
    assert paged_payload['limit'] == 1
    assert paged_payload['offset'] == 1
    assert len(paged_payload['items']) == 1
    assert 'password_hash' not in paged_payload['items'][0]


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


def test_role_assignment_blocks_self_users_manage_removal(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify role admins cannot remove their own users.manage path.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _bootstrap_admin(client, bootstrap_payload)
    root_payload = _login_user(
        client,
        identity=bootstrap_payload['email'],
        password=bootstrap_payload['password'],
    )
    root_headers = _auth_headers(root_payload['access_token'])
    role_admin = _create_managed_user(
        client,
        root_headers,
        email='self-admin@example.com',
        username='selfadmin',
        password='self-admin-password-123',
        role_keys=['administrator'],
    )
    role_admin_payload = _login_user(
        client,
        identity='self-admin@example.com',
        password='self-admin-password-123',
    )

    response = client.put(
        f"/api/v1/users/{role_admin['id']}/roles",
        headers=_auth_headers(role_admin_payload['access_token']),
        json={'role_keys': ['viewer']},
    )

    assert response.status_code == 400
    assert response.json() == {
        'detail': 'You cannot remove your own users.manage access',
        'code': 'AUTH_SELF_USERS_MANAGE_REQUIRED',
    }


def test_password_reset_revokes_refresh_and_forces_password_change(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify password reset revokes refresh and access sessions.

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

    reset_login_payload = _login_user(
        client,
        identity='reset@example.com',
        password='reset-password-123',
    )
    reset_response = client.post(
        f"/api/v1/users/{created_user['id']}/password-reset",
        headers=admin_headers,
    )
    assert reset_response.status_code == 200
    temporary_password = reset_response.json()['temporary_password']
    assert len(temporary_password) >= 8

    stale_access_response = client.get(
        '/api/v1/auth/me',
        headers=_auth_headers(reset_login_payload['access_token']),
    )
    assert stale_access_response.status_code == 401
    assert stale_access_response.json() == {
        'detail': 'Access token was issued before the current password change',
        'code': 'TOKEN_REVOKED',
    }

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
