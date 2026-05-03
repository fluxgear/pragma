# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Install-state queries for the Pragma backend.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection


def get_schema_status(connection: Connection) -> dict[str, bool]:
    """Return whether the bootstrap-ready schema objects and seeds exist.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        dict[str, bool]: Presence flags for required tables, columns, seed data,
            and overall schema readiness.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    row = connection.execute(
        """
        SELECT
            to_regclass('public.pragma_install_state') IS NOT NULL AS has_install_state,
            to_regclass('public.pragma_users') IS NOT NULL AS has_users,
            to_regclass('public.pragma_refresh_tokens') IS NOT NULL AS has_refresh_tokens,
            to_regclass('public.pragma_roles') IS NOT NULL AS has_roles,
            to_regclass('public.pragma_role_permissions') IS NOT NULL AS has_role_permissions,
            to_regclass('public.pragma_user_roles') IS NOT NULL AS has_user_roles
        """
    ).fetchone()
    has_install_state = bool(row["has_install_state"])
    has_users = bool(row["has_users"])
    has_refresh_tokens = bool(row["has_refresh_tokens"])
    has_roles = bool(row["has_roles"])
    has_role_permissions = bool(row["has_role_permissions"])
    has_user_roles = bool(row["has_user_roles"])

    column_rows = connection.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name IN (
              'pragma_install_state',
              'pragma_users',
              'pragma_roles',
              'pragma_role_permissions',
              'pragma_user_roles'
          )
        """
    ).fetchall()
    columns_by_table: dict[str, set[str]] = {}
    for column_row in column_rows:
        columns_by_table.setdefault(column_row["table_name"], set()).add(
            column_row["column_name"]
        )

    has_install_state_columns = {
        'id',
        'is_installed',
        'installed_at',
        'installed_by_user_id',
    } <= columns_by_table.get('pragma_install_state', set())
    has_user_bootstrap_columns = {
        'id',
        'email',
        'username',
        'full_name',
        'password_hash',
        'is_active',
        'is_superuser',
        'last_login_at',
        'password_changed_at',
        'force_password_change',
        'created_at',
        'updated_at',
    } <= columns_by_table.get('pragma_users', set())
    has_rbac_columns = (
        {'role_key', 'is_system'} <= columns_by_table.get('pragma_roles', set())
        and {'role_key', 'permission_key'}
        <= columns_by_table.get('pragma_role_permissions', set())
        and {'user_id', 'role_key', 'assigned_by_user_id', 'created_at'}
        <= columns_by_table.get('pragma_user_roles', set())
    )

    has_bootstrap_dependencies = (
        has_install_state
        and has_install_state_columns
        and has_users
        and has_user_bootstrap_columns
        and has_refresh_tokens
        and has_roles
        and has_role_permissions
        and has_user_roles
        and has_rbac_columns
    )
    has_administrator_role = False
    has_administrator_permissions = False
    if has_bootstrap_dependencies:
        seed_row = connection.execute(
            """
            SELECT
                EXISTS (
                    SELECT 1
                    FROM pragma_roles
                    WHERE role_key = 'administrator' AND is_system = TRUE
                ) AS has_administrator_role,
                EXISTS (
                    SELECT 1
                    FROM pragma_role_permissions
                    WHERE role_key = 'administrator'
                ) AS has_administrator_permissions
            """
        ).fetchone()
        has_administrator_role = bool(seed_row["has_administrator_role"])
        has_administrator_permissions = bool(
            seed_row["has_administrator_permissions"]
        )

    return {
        "has_install_state": has_install_state,
        "has_users": has_users,
        "has_refresh_tokens": has_refresh_tokens,
        "has_roles": has_roles,
        "has_role_permissions": has_role_permissions,
        "has_user_roles": has_user_roles,
        "has_install_state_columns": has_install_state_columns,
        "has_user_bootstrap_columns": has_user_bootstrap_columns,
        "has_rbac_columns": has_rbac_columns,
        "has_administrator_role": has_administrator_role,
        "has_administrator_permissions": has_administrator_permissions,
        "schema_ready": has_bootstrap_dependencies
        and has_administrator_role
        and has_administrator_permissions,
    }


def get_install_state(connection: Connection) -> dict[str, Any] | None:
    """Return the current install-state row if the schema is ready.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        dict[str, Any] | None: Install-state row, or None if no row exists yet.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT id, is_installed, installed_at, installed_by_user_id
        FROM pragma_install_state
        WHERE id = 1
        """
    ).fetchone()


def acquire_bootstrap_lock(connection: Connection) -> None:
    """Acquire the transaction-scoped bootstrap serialization lock.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute("SELECT pg_advisory_xact_lock(814_743_389)")


def mark_installed(
    connection: Connection,
    installed_by_user_id: UUID,
    installed_at: datetime,
) -> None:
    """Upsert the singleton install-state row.

    Args:
        connection: Open PostgreSQL connection.
        installed_by_user_id: User identifier for the installing super-admin.
        installed_at: Timestamp of bootstrap completion.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        INSERT INTO pragma_install_state (id, is_installed, installed_at, installed_by_user_id)
        VALUES (1, TRUE, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET
            is_installed = EXCLUDED.is_installed,
            installed_at = EXCLUDED.installed_at,
            installed_by_user_id = EXCLUDED.installed_by_user_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (installed_at, installed_by_user_id),
    )
