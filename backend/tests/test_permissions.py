# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Permission-enforcement integration tests for M11.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Create the first super-admin for permission tests.

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


def _login_user(
    client: TestClient,
    *,
    identity: str,
    password: str,
) -> dict[str, Any]:
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

    response = client.post(
        '/api/v1/auth/login',
        json={'identity': identity, 'password': password},
    )
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


def _content_type_payload() -> dict[str, Any]:
    """Return a reusable content-type payload for permission tests.

    Args:
        None.

    Returns:
        dict[str, Any]: Content-type creation payload.

    Raises:
        None.
    """

    return {
        'name': 'Blog Posts',
        'description': 'Structured blog content',
        'field_definitions': [
            {
                'name': 'title',
                'label': 'Title',
                'kind': 'text',
                'required': True,
                'min_length': 3,
                'max_length': 120,
            },
            {
                'name': 'body',
                'label': 'Body',
                'kind': 'rich_text',
                'required': True,
                'min_length': 1,
            },
        ],
    }


def _create_content_type(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    """Create a reusable content type and return its payload.

    Args:
        client: FastAPI test client.
        headers: Administrative bearer-auth headers.

    Returns:
        dict[str, Any]: Parsed content-type response payload.

    Raises:
        AssertionError: If creation fails unexpectedly.
    """

    response = client.post('/api/v1/content/types', headers=headers, json=_content_type_payload())
    assert response.status_code == 201
    return response.json()


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


def test_viewer_role_can_read_but_not_manage_content_types(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify viewer role can read content types but cannot mutate them.

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
    _create_content_type(client, admin_headers)

    _create_managed_user(
        client,
        admin_headers,
        email='viewer@example.com',
        username='viewer',
        password='viewer-password-123',
        role_keys=['viewer'],
    )
    viewer_payload = _login_user(
        client,
        identity='viewer@example.com',
        password='viewer-password-123',
    )
    viewer_headers = _auth_headers(viewer_payload['access_token'])

    list_response = client.get('/api/v1/content/types', headers=viewer_headers)
    assert list_response.status_code == 200
    assert list_response.json()['total'] == 1

    create_response = client.post(
        '/api/v1/content/types',
        headers=viewer_headers,
        json=_content_type_payload(),
    )
    assert create_response.status_code == 403
    assert create_response.json() == {
        'detail': 'Permission content.types.manage is required',
        'code': 'AUTH_PERMISSION_DENIED',
    }


def test_author_role_cannot_publish_entries(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify author role can draft content but cannot publish entries.

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
    content_type = _create_content_type(client, admin_headers)

    _create_managed_user(
        client,
        admin_headers,
        email='author@example.com',
        username='author',
        password='author-password-123',
        role_keys=['author'],
    )
    author_payload = _login_user(
        client,
        identity='author@example.com',
        password='author-password-123',
    )
    author_headers = _auth_headers(author_payload['access_token'])

    draft_response = client.post(
        '/api/v1/content/entries',
        headers=author_headers,
        json={
            'content_type_id': content_type['id'],
            'slug': None,
            'status': 'draft',
            'payload': {'title': 'Author Draft', 'body': '<p>Draft</p>'},
        },
    )
    assert draft_response.status_code == 201
    assert draft_response.json()['status'] == 'draft'

    publish_response = client.post(
        '/api/v1/content/entries',
        headers=author_headers,
        json={
            'content_type_id': content_type['id'],
            'slug': None,
            'status': 'published',
            'payload': {'title': 'Author Publish', 'body': '<p>Publish</p>'},
        },
    )
    assert publish_response.status_code == 403
    assert publish_response.json() == {
        'detail': 'Permission content.entries.publish is required',
        'code': 'AUTH_PERMISSION_DENIED',
    }

    published_entry_response = client.post(
        '/api/v1/content/entries',
        headers=admin_headers,
        json={
            'content_type_id': content_type['id'],
            'slug': None,
            'status': 'published',
            'payload': {'title': 'Admin Publish', 'body': '<p>Published</p>'},
        },
    )
    assert published_entry_response.status_code == 201
    published_entry = published_entry_response.json()

    update_published_response = client.put(
        f"/api/v1/content/entries/{published_entry['id']}",
        headers=author_headers,
        json={
            'slug': published_entry['slug'],
            'status': 'draft',
            'payload': {'title': 'Author Unpublish', 'body': '<p>Updated</p>'},
        },
    )
    assert update_published_response.status_code == 403
    assert update_published_response.json() == {
        'detail': 'Permission content.entries.publish is required',
        'code': 'AUTH_PERMISSION_DENIED',
    }


def test_editor_role_can_publish_entries(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify editor role can create published content entries.

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
    content_type = _create_content_type(client, admin_headers)

    _create_managed_user(
        client,
        admin_headers,
        email='editor@example.com',
        username='editor',
        password='editor-password-123',
        role_keys=['editor'],
    )
    editor_payload = _login_user(
        client,
        identity='editor@example.com',
        password='editor-password-123',
    )
    editor_headers = _auth_headers(editor_payload['access_token'])

    response = client.post(
        '/api/v1/content/entries',
        headers=editor_headers,
        json={
            'content_type_id': content_type['id'],
            'slug': None,
            'status': 'published',
            'payload': {'title': 'Editor Publish', 'body': '<p>Published</p>'},
        },
    )
    assert response.status_code == 201
    assert response.json()['status'] == 'published'


def test_administrator_role_can_manage_ai_modules_and_users(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify administrator role grants sensitive manage permissions.

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

    _create_managed_user(
        client,
        admin_headers,
        email='administrator@example.com',
        username='administrator',
        password='administrator-password-123',
        role_keys=['administrator'],
    )
    role_admin_payload = _login_user(
        client,
        identity='administrator@example.com',
        password='administrator-password-123',
    )
    role_admin_headers = _auth_headers(role_admin_payload['access_token'])

    users_response = client.get('/api/v1/users', headers=role_admin_headers)
    assert users_response.status_code == 200
    assert users_response.json()['total'] >= 2

    ai_response = client.get('/api/v1/ai/settings', headers=role_admin_headers)
    assert ai_response.status_code == 200

    modules_response = client.get('/api/v1/modules', headers=role_admin_headers)
    assert modules_response.status_code == 200
    assert modules_response.json()['total'] >= 0


def test_force_password_change_blocks_protected_routes_until_password_rotates(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify forced password-change users must rotate before normal access.

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
    _create_content_type(client, admin_headers)

    _create_managed_user(
        client,
        admin_headers,
        email='rotate@example.com',
        username='rotate',
        password='rotate-password-123',
        role_keys=['editor'],
        force_password_change=True,
    )
    rotate_payload = _login_user(
        client,
        identity='rotate@example.com',
        password='rotate-password-123',
    )
    rotate_headers = _auth_headers(rotate_payload['access_token'])
    assert rotate_payload['user']['force_password_change'] is True

    blocked_response = client.get('/api/v1/content/types', headers=rotate_headers)
    assert blocked_response.status_code == 403
    assert blocked_response.json() == {
        'detail': 'Password change is required before accessing this resource',
        'code': 'AUTH_PASSWORD_CHANGE_REQUIRED',
    }

    change_response = client.post(
        '/api/v1/auth/change-password',
        headers=rotate_headers,
        json={
            'current_password': 'rotate-password-123',
            'new_password': 'rotate-password-456',
        },
    )
    assert change_response.status_code == 200
    assert change_response.json()['force_password_change'] is False

    allowed_response = client.get('/api/v1/content/types', headers=rotate_headers)
    assert allowed_response.status_code == 200
