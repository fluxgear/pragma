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

import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from pydantic import ValidationError

from pragma.auth.admin_models import AdminUserCreateRequest, AdminUserUpdateRequest
from tests.helpers import build_database_dsn


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
    """Verify user-admin email and username strip before validation.

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
            email='not-an-email',
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
        AdminUserUpdateRequest(email='not-an-email')
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


def _insert_superuser(
    migrated_database: dict[str, str],
    *,
    email: str,
    username: str,
) -> str:
    """Insert an additional active superuser directly for race tests.

    Args:
        migrated_database: Environment values for the migrated test database.
        email: Superuser email.
        username: Superuser username.

    Returns:
        str: Inserted user identifier.

    Raises:
        psycopg.Error: If PostgreSQL cannot insert the row.
    """

    user_id = uuid4()
    timestamp = datetime.now(UTC)
    dsn = build_database_dsn(migrated_database, migrated_database['PRAGMA_DATABASE_NAME'])
    with psycopg.connect(dsn, row_factory=dict_row) as connection, connection.transaction():
        connection.execute(
            """
            INSERT INTO pragma_users (
                id,
                email,
                username,
                full_name,
                password_hash,
                is_active,
                is_superuser,
                password_changed_at,
                force_password_change,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                email,
                username,
                username.title(),
                'not-used-in-test',
                True,
                True,
                timestamp,
                False,
                timestamp,
                timestamp,
            ),
        )
    return str(user_id)


def _set_user_active(
    migrated_database: dict[str, str],
    *,
    user_id: str,
    is_active: bool,
) -> None:
    """Update a user's active flag directly for race-test setup.

    Args:
        migrated_database: Environment values for the migrated test database.
        user_id: User identifier to update.
        is_active: Desired active flag.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL cannot update the row.
    """

    dsn = build_database_dsn(migrated_database, migrated_database['PRAGMA_DATABASE_NAME'])
    with psycopg.connect(dsn) as connection, connection.transaction():
        connection.execute(
            """
            UPDATE pragma_users
            SET is_active = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (is_active, user_id),
        )


def _count_active_superusers(migrated_database: dict[str, str]) -> int:
    """Return active superuser count from the test database.

    Args:
        migrated_database: Environment values for the migrated test database.

    Returns:
        int: Active superuser count.

    Raises:
        psycopg.Error: If PostgreSQL cannot count rows.
    """

    dsn = build_database_dsn(migrated_database, migrated_database['PRAGMA_DATABASE_NAME'])
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM pragma_users
            WHERE is_superuser = TRUE AND is_active = TRUE
            """
        ).fetchone()
    return int(row['total'])


def _count_active_users_managers(migrated_database: dict[str, str]) -> int:
    """Return active users.manage holder count from the test database.

    Args:
        migrated_database: Environment values for the migrated test database.

    Returns:
        int: Active users.manage holder count.

    Raises:
        psycopg.Error: If PostgreSQL cannot count rows.
    """

    dsn = build_database_dsn(migrated_database, migrated_database['PRAGMA_DATABASE_NAME'])
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT COUNT(DISTINCT u.id) AS total
            FROM pragma_users AS u
            LEFT JOIN pragma_user_roles AS ur ON ur.user_id = u.id
            LEFT JOIN pragma_role_permissions AS rp ON rp.role_key = ur.role_key
            WHERE u.is_active = TRUE
              AND (u.is_superuser = TRUE OR rp.permission_key = 'users.manage')
            """
        ).fetchone()
    return int(row['total'])


def _force_concurrent_count_window(
    monkeypatch: pytest.MonkeyPatch,
    target: object,
    attribute: str,
) -> None:
    """Patch a count helper so unfixed code reaches the race window.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        target: Module object that owns the count helper.
        attribute: Count helper attribute name.

    Returns:
        None.

    Raises:
        AttributeError: If the target does not expose the helper.
    """

    barrier = threading.Barrier(2)
    original = getattr(target, attribute)

    def _count_with_barrier(*args: Any) -> int:
        total = original(*args)
        with suppress(threading.BrokenBarrierError):
            barrier.wait(timeout=0.5)
        return int(total)

    monkeypatch.setattr(target, attribute, _count_with_barrier)


def test_last_superuser_deactivation_serializes_concurrent_requests(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    migrated_database: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify concurrent superuser deactivations cannot remove all roots.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.
        migrated_database: Environment values for the migrated test database.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        AssertionError: If both deactivations succeed.
    """

    from pragma.auth import admin_service as admin_service_module

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
        email='superuser-race-admin@example.com',
        username='superuserraceadmin',
        password='superuser-race-admin-password',
        role_keys=['administrator'],
    )
    role_admin_payload = _login_user(
        client,
        identity='superuser-race-admin@example.com',
        password='superuser-race-admin-password',
    )
    role_admin_headers = _auth_headers(role_admin_payload['access_token'])
    second_superuser_id = _insert_superuser(
        migrated_database,
        email='second-root@example.com',
        username='secondroot',
    )

    _force_concurrent_count_window(monkeypatch, admin_service_module, 'count_superusers')

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                client.patch,
                f"/api/v1/users/{root_payload['user']['id']}",
                headers=role_admin_headers,
                json={'is_active': False},
            ),
            executor.submit(
                client.patch,
                f'/api/v1/users/{second_superuser_id}',
                headers=role_admin_headers,
                json={'is_active': False},
            ),
        ]
        responses = [future.result(timeout=5) for future in futures]

    assert role_admin['roles'] == ['administrator']
    assert sorted(response.status_code for response in responses) == [200, 400]
    assert [
        response.json()
        for response in responses
        if response.status_code == 400
    ] == [
        {
            'detail': 'At least one active superuser account is required',
            'code': 'AUTH_LAST_SUPERUSER_REQUIRED',
        }
    ]
    assert _count_active_superusers(migrated_database) == 1


def test_last_users_manager_role_removal_serializes_concurrent_requests(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    migrated_database: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify concurrent administrator demotions cannot remove all managers.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.
        migrated_database: Environment values for the migrated test database.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        AssertionError: If both role removals succeed.
    """

    from pragma.auth import admin_service as admin_service_module

    _bootstrap_admin(client, bootstrap_payload)
    root_payload = _login_user(
        client,
        identity=bootstrap_payload['email'],
        password=bootstrap_payload['password'],
    )
    root_headers = _auth_headers(root_payload['access_token'])
    first_admin = _create_managed_user(
        client,
        root_headers,
        email='first-manager@example.com',
        username='firstmanager',
        password='first-manager-password',
        role_keys=['administrator'],
    )
    second_admin = _create_managed_user(
        client,
        root_headers,
        email='second-manager@example.com',
        username='secondmanager',
        password='second-manager-password',
        role_keys=['administrator'],
    )
    first_payload = _login_user(
        client,
        identity='first-manager@example.com',
        password='first-manager-password',
    )
    second_payload = _login_user(
        client,
        identity='second-manager@example.com',
        password='second-manager-password',
    )
    _set_user_active(
        migrated_database,
        user_id=root_payload['user']['id'],
        is_active=False,
    )

    _force_concurrent_count_window(
        monkeypatch,
        admin_service_module,
        'count_active_users_with_permission',
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                client.put,
                f"/api/v1/users/{second_admin['id']}/roles",
                headers=_auth_headers(first_payload['access_token']),
                json={'role_keys': ['viewer']},
            ),
            executor.submit(
                client.put,
                f"/api/v1/users/{first_admin['id']}/roles",
                headers=_auth_headers(second_payload['access_token']),
                json={'role_keys': ['viewer']},
            ),
        ]
        responses = [future.result(timeout=5) for future in futures]

    assert sorted(response.status_code for response in responses) == [200, 400]
    assert [
        response.json()
        for response in responses
        if response.status_code == 400
    ] == [
        {
            'detail': 'At least one active users.manage administrator is required',
            'code': 'AUTH_LAST_USERS_MANAGER_REQUIRED',
        }
    ]
    assert _count_active_users_managers(migrated_database) == 1
