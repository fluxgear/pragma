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
    """Return whether the M1 schema objects exist.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        dict[str, bool]: Presence flags for the required M1 tables and overall schema readiness.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    row = connection.execute(
        """
        SELECT
            to_regclass('public.pragma_install_state') IS NOT NULL AS has_install_state,
            to_regclass('public.pragma_users') IS NOT NULL AS has_users,
            to_regclass('public.pragma_refresh_tokens') IS NOT NULL AS has_refresh_tokens
        """
    ).fetchone()
    has_install_state = bool(row["has_install_state"])
    has_users = bool(row["has_users"])
    has_refresh_tokens = bool(row["has_refresh_tokens"])
    return {
        "has_install_state": has_install_state,
        "has_users": has_users,
        "has_refresh_tokens": has_refresh_tokens,
        "schema_ready": has_install_state and has_users and has_refresh_tokens,
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
