# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Roles administration API integration tests for C2.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from pragma.auth.permissions import get_permission_definitions
from tests.helpers import build_database_dsn


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Create the first super-admin for roles-admin tests.

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
) -> dict[str, Any]:
    """Create a managed user through the user-admin API.

    Args:
        client: FastAPI test client.
        headers: Administrative bearer-auth headers.
        email: User email.
        username: User username.
        password: Initial raw password.
        role_keys: Built-in role assignments.

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
            'force_password_change': False,
        },
    )
    assert response.status_code == 201
    return response.json()


def _insert_custom_role(
    migrated_database: dict[str, str],
    *,
    role_key: str,
    permission_keys: list[str],
) -> None:
    """Insert a custom role directly for authorization-path setup.

    Args:
        migrated_database: Environment values for the migrated test database.
        role_key: Stable role identifier to insert.
        permission_keys: Permission grants for the role.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL cannot insert the role.
    """

    timestamp = datetime.now(UTC)
    dsn = build_database_dsn(migrated_database, migrated_database['PRAGMA_DATABASE_NAME'])
    with psycopg.connect(dsn, row_factory=dict_row) as connection, connection.transaction():
        connection.execute(
            """
            INSERT INTO pragma_roles (
                role_key,
                name,
                description,
                is_system,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                role_key,
                role_key.replace('-', ' ').title(),
                'Direct role fixture',
                False,
                timestamp,
                timestamp,
            ),
        )
        for permission_key in permission_keys:
            connection.execute(
                """
                INSERT INTO pragma_role_permissions (role_key, permission_key, created_at)
                VALUES (%s, %s, %s)
                """,
                (role_key, permission_key, timestamp),
            )


def _assign_custom_role(
    migrated_database: dict[str, str],
    *,
    user_id: str,
    role_key: str,
) -> None:
    """Assign a custom role directly without changing assignment API scope.

    Args:
        migrated_database: Environment values for the migrated test database.
        user_id: User identifier receiving the role.
        role_key: Role identifier to assign.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL cannot insert the assignment.
    """

    timestamp = datetime.now(UTC)
    dsn = build_database_dsn(migrated_database, migrated_database['PRAGMA_DATABASE_NAME'])
    with psycopg.connect(dsn) as connection, connection.transaction():
        connection.execute(
            """
            INSERT INTO pragma_user_roles (
                user_id,
                role_key,
                assigned_by_user_id,
                created_at
            )
            VALUES (%s, %s, NULL, %s)
            """,
            (user_id, role_key, timestamp),
        )


def test_roles_admin_requires_roles_manage_and_legacy_users_roles_stays_users_manage(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    migrated_database: dict[str, str],
) -> None:
    """Verify /roles uses roles.manage while legacy /users/roles keeps users.manage.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.
        migrated_database: Environment values for the migrated test database.

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
    user = _create_managed_user(
        client,
        root_headers,
        email='users-manager-only@example.com',
        username='usersmanageronly',
        password='users-manager-only-password',
        role_keys=['viewer'],
    )
    _insert_custom_role(
        migrated_database,
        role_key='users-manager-only',
        permission_keys=['users.manage'],
    )
    _assign_custom_role(
        migrated_database,
        user_id=user['id'],
        role_key='users-manager-only',
    )
    users_manager_payload = _login_user(
        client,
        identity='users-manager-only@example.com',
        password='users-manager-only-password',
    )
    users_manager_headers = _auth_headers(users_manager_payload['access_token'])

    legacy_response = client.get('/api/v1/users/roles', headers=users_manager_headers)
    assert legacy_response.status_code == 200

    list_response = client.get('/api/v1/roles', headers=users_manager_headers)
    assert list_response.status_code == 403
    assert list_response.json() == {
        'detail': 'Permission roles.manage is required',
        'code': 'AUTH_PERMISSION_DENIED',
    }

    create_response = client.post(
        '/api/v1/roles',
        headers=users_manager_headers,
        json={
            'role_key': 'forbidden-role',
            'name': 'Forbidden Role',
            'description': None,
            'permission_keys': ['content.entries.read'],
        },
    )
    assert create_response.status_code == 403
    assert create_response.json() == {
        'detail': 'Permission roles.manage is required',
        'code': 'AUTH_PERMISSION_DENIED',
    }


def test_roles_admin_list_returns_system_roles_and_permission_catalog(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify roles-admin list includes DB roles and runtime permission metadata.

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
    response = client.get('/api/v1/roles', headers=_auth_headers(root_payload['access_token']))

    assert response.status_code == 200
    payload = response.json()
    role_keys = {item['role_key'] for item in payload['items']}
    assert {'administrator', 'editor', 'author', 'viewer'} <= role_keys
    assert payload['total'] == len(payload['items'])
    assert all(item['is_system'] is True for item in payload['items'])

    registry = get_permission_definitions()
    permission_definitions = payload['permission_definitions']
    assert {item['key'] for item in permission_definitions} == {
        definition.key for definition in registry
    }
    roles_manage = next(
        item for item in permission_definitions if item['key'] == 'roles.manage'
    )
    assert roles_manage == {
        'key': 'roles.manage',
        'name': 'Manage roles',
        'description': 'Create, update, and administer role definitions and permissions.',
        'domain': 'roles',
    }
    assert {item['domain'] for item in permission_definitions} >= {
        'admin',
        'users',
        'roles',
        'content',
        'media',
    }


def test_roles_admin_create_custom_role_persists_permissions(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify creating a custom role stores is_system false and permissions.

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
    headers = _auth_headers(root_payload['access_token'])

    create_response = client.post(
        '/api/v1/roles',
        headers=headers,
        json={
            'role_key': '  Support-Auditor  ',
            'name': '  Support Auditor  ',
            'description': '  Can review content and media.  ',
            'permission_keys': [
                'content.entries.read',
                'media.assets.read',
                'content.entries.read',
            ],
        },
    )

    assert create_response.status_code == 201
    created_role = create_response.json()
    assert created_role == {
        'role_key': 'support-auditor',
        'name': 'Support Auditor',
        'description': 'Can review content and media.',
        'is_system': False,
        'permission_keys': ['content.entries.read', 'media.assets.read'],
    }

    list_response = client.get('/api/v1/roles', headers=headers)
    assert list_response.status_code == 200
    stored_role = next(
        item
        for item in list_response.json()['items']
        if item['role_key'] == 'support-auditor'
    )
    assert stored_role == created_role


def test_roles_admin_create_rejects_invalid_and_conflicting_role_payloads(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify custom role creation rejects unknown permissions and key collisions.

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
    headers = _auth_headers(root_payload['access_token'])

    wildcard_response = client.post(
        '/api/v1/roles',
        headers=headers,
        json={
            'role_key': 'wildcard-role',
            'name': 'Wildcard Role',
            'description': None,
            'permission_keys': ['content.entries.*'],
        },
    )
    assert wildcard_response.status_code == 400
    assert wildcard_response.json() == {
        'detail': 'Unknown permission requested: content.entries.*',
        'code': 'ROLE_PERMISSION_INVALID',
    }

    system_response = client.post(
        '/api/v1/roles',
        headers=headers,
        json={
            'role_key': 'administrator',
            'name': 'Administrator Clone',
            'description': None,
            'permission_keys': ['content.entries.read'],
        },
    )
    assert system_response.status_code == 409
    assert system_response.json() == {
        'detail': 'Role key conflicts with a built-in system role',
        'code': 'ROLE_SYSTEM_KEY_CONFLICT',
    }

    duplicate_payload = {
        'role_key': 'duplicate-role',
        'name': 'Duplicate Role',
        'description': None,
        'permission_keys': ['content.entries.read'],
    }
    first_response = client.post('/api/v1/roles', headers=headers, json=duplicate_payload)
    assert first_response.status_code == 201
    duplicate_response = client.post(
        '/api/v1/roles',
        headers=headers,
        json=duplicate_payload,
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        'detail': 'Role key already exists',
        'code': 'ROLE_KEY_CONFLICT',
    }
