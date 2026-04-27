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
    assert superuser_row['permission_count'] == 12
    assert superuser_row['role_count'] == 4
    assert superuser_row['role_permission_count'] == 29

    regular_user_row = rows_by_id[regular_user_id]
    assert regular_user_row['password_changed_at'] == created_at
    assert regular_user_row['force_password_change'] is False
    assert regular_user_row['has_administrator_role'] is False
    assert regular_user_row['has_users_manage_permission'] is True
    assert regular_user_row['permission_count'] == 12
    assert regular_user_row['role_count'] == 4
    assert regular_user_row['role_permission_count'] == 29


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
