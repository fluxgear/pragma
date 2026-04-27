# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Role and permission queries for the Pragma backend.

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


def list_roles(connection: Connection) -> list[dict[str, Any]]:
    """Return role catalog rows with aggregated permission assignments.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        list[dict[str, Any]]: Role rows ordered by role identifier.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            r.role_key,
            r.name,
            r.description,
            r.is_system,
            COALESCE(
                ARRAY_AGG(rp.permission_key ORDER BY rp.permission_key)
                FILTER (WHERE rp.permission_key IS NOT NULL),
                ARRAY[]::text[]
            ) AS permission_keys
        FROM pragma_roles AS r
        LEFT JOIN pragma_role_permissions AS rp ON rp.role_key = r.role_key
        GROUP BY r.role_key, r.name, r.description, r.is_system
        ORDER BY r.role_key
        """
    ).fetchall()


def replace_user_roles(
    connection: Connection,
    *,
    user_id: UUID,
    role_keys: list[str],
    assigned_by_user_id: UUID,
    assigned_at: datetime,
) -> None:
    """Replace all user-role assignments for a user.

    Args:
        connection: Open PostgreSQL connection.
        user_id: Target user identifier.
        role_keys: Complete set of desired role identifiers.
        assigned_by_user_id: User applying the role assignment.
        assigned_at: Assignment timestamp.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        DELETE FROM pragma_user_roles
        WHERE user_id = %s
        """,
        (user_id,),
    )

    if not role_keys:
        return

    for role_key in role_keys:
        connection.execute(
            """
            INSERT INTO pragma_user_roles (
                user_id,
                role_key,
                assigned_by_user_id,
                created_at
            )
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, role_key, assigned_by_user_id, assigned_at),
        )
