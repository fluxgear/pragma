# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""M11 migration regression tests for install/bootstrap schema quality.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from alembic.config import Config
from psycopg.rows import dict_row

from alembic import command
from pragma.auth.permissions import get_permission_definitions, get_role_definitions
from pragma.config import clear_settings_cache
from tests.helpers import BACKEND_ROOT, build_database_dsn


def _build_alembic_config() -> Config:
    """Return an Alembic configuration rooted at the backend project.

    Args:
        None.

    Returns:
        Config: Alembic configuration for backend migrations.

    Raises:
        None.
    """

    config = Config(str(BACKEND_ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND_ROOT / 'alembic'))
    return config


def _upgrade_database(target: str) -> None:
    """Upgrade the configured test database to the requested revision.

    Args:
        target: Alembic revision target.

    Returns:
        None.

    Raises:
        CommandError: If Alembic cannot upgrade the database.
    """

    clear_settings_cache()
    command.upgrade(_build_alembic_config(), target)


def _downgrade_database(target: str) -> None:
    """Downgrade the configured test database to the requested revision.

    Args:
        target: Alembic revision target.

    Returns:
        None.

    Raises:
        CommandError: If Alembic cannot downgrade the database.
    """

    clear_settings_cache()
    command.downgrade(_build_alembic_config(), target)


def test_m11_migration_backfills_existing_superuser_and_seeds_rbac(
    runtime_database: dict[str, str],
) -> None:
    """Verify M11 backfills existing superusers and seeds RBAC metadata.

    Args:
        runtime_database: Environment values for the isolated test database.

    Returns:
        None.

    Raises:
        None.
    """

    _upgrade_database('20260427_0006')
    database_dsn = build_database_dsn(
        runtime_database, runtime_database['PRAGMA_DATABASE_NAME']
    )
    superuser_id = uuid4()
    regular_user_id = uuid4()
    created_at = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)

    with psycopg.connect(database_dsn) as connection, connection.transaction():
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
                last_login_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                superuser_id,
                'legacy-admin@example.com',
                'legacy-admin',
                'Legacy Admin',
                'hashed-password',
                True,
                True,
                None,
                created_at,
                created_at,
            ),
        )
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
                last_login_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                regular_user_id,
                'legacy-editor@example.com',
                'legacy-editor',
                'Legacy Editor',
                'hashed-password',
                True,
                False,
                None,
                created_at,
                created_at,
            ),
        )

    _upgrade_database('head')

    with psycopg.connect(database_dsn, row_factory=dict_row) as connection:
        rows = connection.execute(
            """
            SELECT
                u.id,
                u.password_changed_at,
                u.force_password_change,
                EXISTS (
                    SELECT 1
                    FROM pragma_user_roles AS ur
                    WHERE ur.user_id = u.id
                      AND ur.role_key = 'administrator'
                ) AS has_administrator_role,
                EXISTS (
                    SELECT 1
                    FROM pragma_role_permissions AS rp
                    WHERE rp.role_key = 'administrator'
                      AND rp.permission_key = 'users.manage'
                ) AS has_users_manage_permission,
                (SELECT COUNT(*) FROM pragma_permissions) AS permission_count,
                (SELECT COUNT(*) FROM pragma_roles) AS role_count,
                (SELECT COUNT(*) FROM pragma_role_permissions) AS role_permission_count
            FROM pragma_users AS u
            WHERE u.id IN (%s, %s)
            ORDER BY u.id
            """,
            (superuser_id, regular_user_id),
        ).fetchall()

    assert len(rows) == 2
    rows_by_id = {row['id']: row for row in rows}

    superuser_row = rows_by_id[superuser_id]
    assert superuser_row['password_changed_at'] == created_at
    assert superuser_row['force_password_change'] is False
    assert superuser_row['has_administrator_role'] is True
    assert superuser_row['has_users_manage_permission'] is True
    assert superuser_row['permission_count'] == 22
    assert superuser_row['role_count'] == 4
    assert superuser_row['role_permission_count'] == 39

    regular_user_row = rows_by_id[regular_user_id]
    assert regular_user_row['password_changed_at'] == created_at
    assert regular_user_row['force_password_change'] is False
    assert regular_user_row['has_administrator_role'] is False
    assert regular_user_row['has_users_manage_permission'] is True
    assert regular_user_row['permission_count'] == 22
    assert regular_user_row['role_count'] == 4
    assert regular_user_row['role_permission_count'] == 39


def test_c2_migration_seeds_registry_permissions_and_system_role_grants(
    runtime_database: dict[str, str],
) -> None:
    """Verify C2 RBAC seed rows stay aligned with the runtime registry.

    Args:
        runtime_database: Environment values for the isolated test database.

    Returns:
        None.

    Raises:
        None.
    """

    c2_permission_keys = {
        'admin.access',
        'roles.manage',
        'themes.manage',
        'settings.manage',
        'page_builder.use',
        'page_builder.design',
        'navigation.manage',
        'ai.editor_assist',
        'ai.seo_assist',
        'ai.oauth.manage',
    }
    runtime_permissions = {
        definition.key: definition for definition in get_permission_definitions()
    }
    runtime_role_permissions = {
        definition.key: set(definition.permissions) for definition in get_role_definitions()
    }
    assert c2_permission_keys <= set(runtime_permissions)

    _upgrade_database('20260502_0011')
    database_dsn = build_database_dsn(
        runtime_database, runtime_database['PRAGMA_DATABASE_NAME']
    )

    with psycopg.connect(database_dsn, row_factory=dict_row) as connection:
        pre_c2_rows = connection.execute(
            """
            SELECT permission_key
            FROM pragma_permissions
            WHERE permission_key = ANY(%s)
            """,
            (list(c2_permission_keys),),
        ).fetchall()

    assert pre_c2_rows == []

    _upgrade_database('head')

    with psycopg.connect(database_dsn, row_factory=dict_row) as connection:
        permission_rows = connection.execute(
            """
            SELECT permission_key, name, description
            FROM pragma_permissions
            ORDER BY permission_key
            """
        ).fetchall()
        role_permission_rows = connection.execute(
            """
            SELECT role_key, permission_key
            FROM pragma_role_permissions
            ORDER BY role_key, permission_key
            """
        ).fetchall()

    permission_rows_by_key = {row['permission_key']: row for row in permission_rows}
    assert set(permission_rows_by_key) == set(runtime_permissions)
    for permission_key, definition in runtime_permissions.items():
        row = permission_rows_by_key[permission_key]
        assert row['name'] == definition.name
        assert row['description'] == definition.description

    role_permissions_by_role = {role_key: set() for role_key in runtime_role_permissions}
    for row in role_permission_rows:
        role_permissions_by_role.setdefault(row['role_key'], set()).add(row['permission_key'])

    assert role_permissions_by_role['administrator'] == set(runtime_permissions)
    assert role_permissions_by_role == runtime_role_permissions


def test_m11_migration_downgrade_removes_rbac_schema(
    runtime_database: dict[str, str],
) -> None:
    """Verify downgrading M11 removes RBAC tables and user-hardening columns.

    Args:
        runtime_database: Environment values for the isolated test database.

    Returns:
        None.

    Raises:
        None.
    """

    _upgrade_database('head')
    database_dsn = build_database_dsn(
        runtime_database, runtime_database['PRAGMA_DATABASE_NAME']
    )
    user_id = uuid4()
    created_at = datetime(2026, 4, 27, 13, 0, tzinfo=UTC)

    with psycopg.connect(database_dsn) as connection, connection.transaction():
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
                last_login_at,
                password_changed_at,
                force_password_change,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                'downgrade-user@example.com',
                'downgrade-user',
                'Downgrade User',
                'hashed-password',
                True,
                False,
                None,
                created_at,
                False,
                created_at,
                created_at,
            ),
        )

    _downgrade_database('20260427_0006')

    with psycopg.connect(database_dsn, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT
                to_regclass('public.pragma_users') AS users_table,
                to_regclass('public.pragma_permissions') AS permissions_table,
                to_regclass('public.pragma_roles') AS roles_table,
                to_regclass('public.pragma_role_permissions') AS role_permissions_table,
                to_regclass('public.pragma_user_roles') AS user_roles_table,
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
                (SELECT version_num FROM alembic_version) AS alembic_version,
                (SELECT email FROM pragma_users WHERE id = %s) AS preserved_email,
                (SELECT username FROM pragma_users WHERE id = %s) AS preserved_username
            """,
            (user_id, user_id),
        ).fetchone()

    assert row['users_table'] == 'pragma_users'
    assert row['permissions_table'] is None
    assert row['roles_table'] is None
    assert row['role_permissions_table'] is None
    assert row['user_roles_table'] is None
    assert row['has_password_changed_at'] is False
    assert row['has_force_password_change'] is False
    assert row['alembic_version'] == '20260427_0006'
    assert row['preserved_email'] == 'downgrade-user@example.com'
    assert row['preserved_username'] == 'downgrade-user'
