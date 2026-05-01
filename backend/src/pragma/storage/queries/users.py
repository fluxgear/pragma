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
            u.id,
            u.email,
            u.username,
            u.full_name,
            u.password_hash,
            u.is_active,
            u.is_superuser,
            u.last_login_at,
            u.password_changed_at,
            u.force_password_change,
            u.created_at,
            u.updated_at,
            COALESCE(
                (
                    SELECT ARRAY_AGG(ur.role_key ORDER BY ur.role_key)
                    FROM pragma_user_roles AS ur
                    WHERE ur.user_id = u.id
                ),
                ARRAY[]::text[]
            ) AS roles,
            COALESCE(
                (
                    SELECT ARRAY_AGG(DISTINCT rp.permission_key ORDER BY rp.permission_key)
                    FROM pragma_user_roles AS ur
                    JOIN pragma_role_permissions AS rp ON rp.role_key = ur.role_key
                    WHERE ur.user_id = u.id
                ),
                ARRAY[]::text[]
            ) AS permissions
        FROM pragma_users AS u
        WHERE u.email = %s OR u.username = %s
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
            u.id,
            u.email,
            u.username,
            u.full_name,
            u.password_hash,
            u.is_active,
            u.is_superuser,
            u.last_login_at,
            u.password_changed_at,
            u.force_password_change,
            u.created_at,
            u.updated_at,
            COALESCE(
                (
                    SELECT ARRAY_AGG(ur.role_key ORDER BY ur.role_key)
                    FROM pragma_user_roles AS ur
                    WHERE ur.user_id = u.id
                ),
                ARRAY[]::text[]
            ) AS roles,
            COALESCE(
                (
                    SELECT ARRAY_AGG(DISTINCT rp.permission_key ORDER BY rp.permission_key)
                    FROM pragma_user_roles AS ur
                    JOIN pragma_role_permissions AS rp ON rp.role_key = ur.role_key
                    WHERE ur.user_id = u.id
                ),
                ARRAY[]::text[]
            ) AS permissions
        FROM pragma_users AS u
        WHERE u.id = %s
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
    is_active: bool,
    force_password_change: bool,
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
        is_active: Whether the user is active for authentication.
        force_password_change: Whether the user must change their password before normal use.
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
            password_changed_at,
            force_password_change,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
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
            updated_at,
            ARRAY[]::text[] AS roles,
            ARRAY[]::text[] AS permissions
        """,
        (
            user_id,
            email,
            username,
            full_name,
            password_hash,
            is_active,
            is_superuser,
            created_at,
            force_password_change,
            created_at,
            created_at,
        ),
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


def count_users(connection: Connection) -> int:
    """Return the total number of user accounts.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        int: Number of stored user accounts.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    row = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM pragma_users
        """
    ).fetchone()
    return int(row["total"])


def list_users(connection: Connection, limit: int, offset: int) -> list[dict[str, Any]]:
    """Return paginated users with aggregated roles and permissions.

    Args:
        connection: Open PostgreSQL connection.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip before returning results.

    Returns:
        list[dict[str, Any]]: Ordered user rows with RBAC metadata.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            u.id,
            u.email,
            u.username,
            u.full_name,
            u.is_active,
            u.is_superuser,
            u.last_login_at,
            u.password_changed_at,
            u.force_password_change,
            u.created_at,
            u.updated_at,
            COALESCE(
                (
                    SELECT ARRAY_AGG(ur.role_key ORDER BY ur.role_key)
                    FROM pragma_user_roles AS ur
                    WHERE ur.user_id = u.id
                ),
                ARRAY[]::text[]
            ) AS roles,
            COALESCE(
                (
                    SELECT ARRAY_AGG(DISTINCT rp.permission_key ORDER BY rp.permission_key)
                    FROM pragma_user_roles AS ur
                    JOIN pragma_role_permissions AS rp ON rp.role_key = ur.role_key
                    WHERE ur.user_id = u.id
                ),
                ARRAY[]::text[]
            ) AS permissions
        FROM pragma_users AS u
        ORDER BY u.is_superuser DESC, u.username ASC
        LIMIT %s
        OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


def update_user_profile(
    connection: Connection,
    *,
    user_id: UUID,
    email: str | None,
    username: str | None,
    full_name: str | None,
    is_active: bool | None,
    updated_at: datetime,
) -> dict[str, Any] | None:
    """Update mutable user profile and lifecycle fields.

    Args:
        connection: Open PostgreSQL connection.
        user_id: Target user identifier.
        email: Optional normalized email address override.
        username: Optional normalized username override.
        full_name: Optional display name override.
        is_active: Optional active-state override.
        updated_at: Profile update timestamp.

    Returns:
        dict[str, Any] | None: Updated user row when found.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        UPDATE pragma_users
        SET
            email = COALESCE(%s, email),
            username = COALESCE(%s, username),
            full_name = COALESCE(%s, full_name),
            is_active = COALESCE(%s, is_active),
            updated_at = %s
        WHERE id = %s
        RETURNING
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
            updated_at,
            COALESCE(
                (
                    SELECT ARRAY_AGG(ur.role_key ORDER BY ur.role_key)
                    FROM pragma_user_roles AS ur
                    WHERE ur.user_id = pragma_users.id
                ),
                ARRAY[]::text[]
            ) AS roles,
            COALESCE(
                (
                    SELECT ARRAY_AGG(DISTINCT rp.permission_key ORDER BY rp.permission_key)
                    FROM pragma_user_roles AS ur
                    JOIN pragma_role_permissions AS rp ON rp.role_key = ur.role_key
                    WHERE ur.user_id = pragma_users.id
                ),
                ARRAY[]::text[]
            ) AS permissions
        """,
        (email, username, full_name, is_active, updated_at, user_id),
    ).fetchone()


def set_user_password(
    connection: Connection,
    *,
    user_id: UUID,
    password_hash: str,
    password_changed_at: datetime,
    updated_at: datetime,
) -> None:
    """Persist a new password hash for a user account.

    Args:
        connection: Open PostgreSQL connection.
        user_id: Target user identifier.
        password_hash: Replacement password hash string.
        password_changed_at: Password-change timestamp.
        updated_at: General update timestamp.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """


    connection.execute(
        """
        UPDATE pragma_users
        SET
            password_hash = %s,
            password_changed_at = %s,
            updated_at = %s
        WHERE id = %s
        """,
        (password_hash, password_changed_at, updated_at, user_id),
    )


def set_user_force_password_change(
    connection: Connection,
    user_id: UUID,
    force_password_change: bool,
    updated_at: datetime,
) -> None:
    """Persist forced-password-change state for a user account.

    Args:
        connection: Open PostgreSQL connection.
        user_id: Target user identifier.
        force_password_change: Desired forced-password-change flag.
        updated_at: General update timestamp.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        UPDATE pragma_users
        SET
            force_password_change = %s,
            updated_at = %s
        WHERE id = %s
        """,
        (force_password_change, updated_at, user_id),
    )
