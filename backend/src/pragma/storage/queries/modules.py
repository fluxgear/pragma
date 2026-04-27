# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Storage queries for persisted module enable/disable state.

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


def list_module_states(connection: Connection) -> list[dict[str, Any]]:
    """Return persisted module state rows ordered by module identifier.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        list[dict[str, Any]]: Persisted module-state rows.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            module_id,
            enabled,
            updated_by_user_id,
            created_at,
            updated_at
        FROM pragma_modules
        ORDER BY module_id
        """
    ).fetchall()


def upsert_module_state(
    connection: Connection,
    *,
    module_id: str,
    enabled: bool,
    updated_by_user_id: UUID,
    updated_at: datetime,
) -> dict[str, Any]:
    """Insert or update persisted module enable/disable state.

    Args:
        connection: Open PostgreSQL connection.
        module_id: Module identifier key.
        enabled: Desired enabled flag for runtime loading.
        updated_by_user_id: User identifier applying the state change.
        updated_at: Current update timestamp.

    Returns:
        dict[str, Any]: Persisted module-state row after update.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        INSERT INTO pragma_modules (
            module_id,
            enabled,
            updated_by_user_id,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (module_id) DO UPDATE
        SET
            enabled = EXCLUDED.enabled,
            updated_by_user_id = EXCLUDED.updated_by_user_id,
            updated_at = EXCLUDED.updated_at
        RETURNING
            module_id,
            enabled,
            updated_by_user_id,
            created_at,
            updated_at
        """,
        (
            module_id,
            enabled,
            updated_by_user_id,
            updated_at,
            updated_at,
        ),
    ).fetchone()
