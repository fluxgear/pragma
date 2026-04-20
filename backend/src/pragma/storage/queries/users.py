# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""User queries for the Pragma backend.

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


def get_user_by_identity(connection: Connection, identity: str) -> dict[str, Any] | None:
    """Return a user by normalized email or username.

    Args:
        connection: Open PostgreSQL connection.
        identity: Normalized login identity.

    Returns:
        dict[str, Any] | None: User row when found, otherwise None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
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
        FROM pragma_users
        WHERE email = %s OR username = %s
        LIMIT 1
        """,
        (identity, identity),
    ).fetchone()


def get_user_by_id(connection: Connection, user_id: UUID) -> dict[str, Any] | None:
    """Return a user by identifier.

    Args:
        connection: Open PostgreSQL connection.
        user_id: User identifier.

    Returns:
        dict[str, Any] | None: User row when found, otherwise None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
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
        FROM pragma_users
        WHERE id = %s
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()


def create_user(
    connection: Connection,
    user_id: UUID,
    email: str,
    username: str,
    password_hash: str,
    full_name: str | None,
    is_superuser: bool,
    created_at: datetime,
) -> dict[str, Any]:
    """Insert a new user row and return the created record.

    Args:
        connection: Open PostgreSQL connection.
        user_id: User identifier to insert.
        email: Normalized email address.
        username: Normalized username.
        password_hash: Password hash string.
        full_name: Optional display name.
        is_superuser: Whether the user has bootstrap super-admin privileges.
        created_at: Timestamp for creation and update columns.

    Returns:
        dict[str, Any]: Created user row.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        INSERT INTO pragma_users (
            id,
            email,
            username,
            full_name,
            password_hash,
            is_active,
            is_superuser,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s, %s)
        RETURNING
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
        """,
        (user_id, email, username, full_name, password_hash, is_superuser, created_at, created_at),
    ).fetchone()


def update_last_login(connection: Connection, user_id: UUID, last_login_at: datetime) -> None:
    """Update a user's last successful login timestamp.

    Args:
        connection: Open PostgreSQL connection.
        user_id: User identifier to update.
        last_login_at: Timestamp of successful authentication.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        UPDATE pragma_users
        SET last_login_at = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (last_login_at, user_id),
    )


def count_superusers(connection: Connection) -> int:
    """Return the number of active superusers.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        int: Number of active superuser accounts.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    row = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM pragma_users
        WHERE is_superuser = TRUE AND is_active = TRUE
        """
    ).fetchone()
    return int(row["total"])
