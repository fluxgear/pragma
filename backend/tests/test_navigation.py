# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Navigation API and public rendering tests."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Create the first super-admin."""

    response = client.post('/api/v1/install/bootstrap', json=bootstrap_payload)
    assert response.status_code == 201


def _login_user(
    client: TestClient,
    *,
    identity: str,
    password: str,
) -> dict[str, Any]:
    """Log in a user and return the parsed auth payload."""

    response = client.post(
        '/api/v1/auth/login',
        json={'identity': identity, 'password': password},
    )
    assert response.status_code == 200
    return response.json()


def _auth_headers(access_token: str) -> dict[str, str]:
    """Build bearer authentication headers."""

    return {'Authorization': f'Bearer {access_token}'}


def _admin_headers(client: TestClient, bootstrap_payload: dict[str, str]) -> dict[str, str]:
    """Bootstrap/login admin and return headers."""

    _bootstrap_admin(client, bootstrap_payload)
    payload = _login_user(
        client,
        identity=bootstrap_payload['email'],
        password=bootstrap_payload['password'],
    )
    return _auth_headers(payload['access_token'])


def _create_managed_user(
    client: TestClient,
    headers: dict[str, str],
    *,
    email: str,
    username: str,
    password: str,
    role_keys: list[str],
) -> dict[str, Any]:
    """Create a managed user with the supplied built-in roles."""

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
            'force_password_change': False,
        },
    )
    assert response.status_code == 201
    return response.json()


def _content_type_payload(name: str, slug: str) -> dict[str, object]:
    """Return a minimal page/post content-type payload."""

    return {
        'name': name,
        'slug': slug,
        'field_definitions': [
            {
                'name': 'title',
                'label': 'Title',
                'kind': 'text',
                'required': True,
                'min_length': 1,
                'max_length': 200,
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


def _create_content_type(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = 'Pages',
    slug: str = 'page',
) -> dict[str, Any]:
    """Create a content type for navigation tests."""

    response = client.post(
        '/api/v1/content/types',
        headers=headers,
        json=_content_type_payload(name, slug),
    )
    assert response.status_code == 201
    return response.json()


def _create_entry(
    client: TestClient,
    headers: dict[str, str],
    content_type_id: str,
    *,
    title: str,
    status: str = 'published',
) -> dict[str, Any]:
    """Create a page entry for menu target tests."""

    response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type_id,
            'status': status,
            'payload': {'title': title, 'body': f'<p>{title} body</p>'},
        },
    )
    assert response.status_code == 201
    return response.json()


def test_navigation_api_requires_manage_permission(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify primary menu API requires navigation.manage."""

    unauthenticated_response = client.get('/api/v1/navigation/primary')

    admin_headers = _admin_headers(client, bootstrap_payload)
    _create_managed_user(
        client,
        admin_headers,
        email='viewer-navigation@example.com',
        username='viewer-navigation',
        password='viewer-navigation-password-123',
        role_keys=['viewer'],
    )
    viewer_payload = _login_user(
        client,
        identity='viewer-navigation@example.com',
        password='viewer-navigation-password-123',
    )
    viewer_headers = _auth_headers(viewer_payload['access_token'])

    forbidden_response = client.get('/api/v1/navigation/primary', headers=viewer_headers)

    assert unauthenticated_response.status_code == 401
    assert forbidden_response.status_code == 403
    assert forbidden_response.json() == {
        'detail': 'Permission navigation.manage is required',
        'code': 'AUTH_PERMISSION_DENIED',
    }


def test_primary_navigation_replace_warns_for_drafts_and_renders_public_menu(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify menu replacement supports custom/internal links and public rendering."""

    headers = _admin_headers(client, bootstrap_payload)
    page_type = _create_content_type(client, headers)
    published_entry = _create_entry(
        client,
        headers,
        str(page_type['id']),
        title='Published Navigation Page',
        status='published',
    )
    draft_entry = _create_entry(
        client,
        headers,
        str(page_type['id']),
        title='Draft Navigation Page',
        status='draft',
    )

    empty_response = client.get('/api/v1/navigation/primary', headers=headers)
    invalid_url_response = client.put(
        '/api/v1/navigation/primary',
        headers=headers,
        json={
            'items': [
                {
                    'label': 'Bad',
                    'link_type': 'custom_url',
                    'url': 'javascript:alert(1)',
                }
            ]
        },
    )
    save_response = client.put(
        '/api/v1/navigation/primary',
        headers=headers,
        json={
            'items': [
                {
                    'label': 'Published Link',
                    'link_type': 'content_entry',
                    'content_entry_id': published_entry['id'],
                    'enabled': True,
                },
                {
                    'label': 'Draft Link',
                    'link_type': 'content_entry',
                    'content_entry_id': draft_entry['id'],
                    'enabled': True,
                },
                {
                    'label': 'Docs',
                    'link_type': 'custom_url',
                    'url': 'https://example.com/docs',
                    'enabled': True,
                },
                {
                    'label': 'Hidden Link',
                    'link_type': 'custom_url',
                    'url': '/hidden',
                    'enabled': False,
                },
            ]
        },
    )
    get_response = client.get('/api/v1/navigation/primary', headers=headers)
    public_response = client.get('/')

    assert empty_response.status_code == 200
    assert empty_response.json() == {'key': 'primary', 'items': [], 'warnings': []}
    assert invalid_url_response.status_code == 422

    assert save_response.status_code == 200
    saved_payload = save_response.json()
    assert [item['label'] for item in saved_payload['items']] == [
        'Published Link',
        'Draft Link',
        'Docs',
        'Hidden Link',
    ]
    assert [item['position'] for item in saved_payload['items']] == [1, 2, 3, 4]
    assert saved_payload['items'][0]['href'] == f"/pages/{published_entry['slug']}"
    assert saved_payload['items'][2]['href'] == 'https://example.com/docs'
    assert saved_payload['warnings'] == [
        {
            'code': 'NAVIGATION_TARGET_NOT_PUBLISHED',
            'detail': 'Internal navigation target is not currently published.',
            'item_position': 2,
            'item_label': 'Draft Link',
            'content_entry_id': draft_entry['id'],
        }
    ]
    assert get_response.status_code == 200
    assert get_response.json()['items'] == saved_payload['items']

    assert public_response.status_code == 200
    assert 'Published Link' in public_response.text
    assert f"/pages/{published_entry['slug']}" in public_response.text
    assert 'https://example.com/docs' in public_response.text
    assert 'Draft Link' not in public_response.text
    assert str(draft_entry['slug']) not in public_response.text
    assert 'Hidden Link' not in public_response.text
