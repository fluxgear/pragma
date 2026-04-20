# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Refresh-token session queries for the Pragma backend.

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


def create_refresh_session(
    connection: Connection,
    session_id: UUID,
    user_id: UUID,
    token_hash: str,
    expires_at: datetime,
    rotated_from_id: UUID | None,
    issued_at: datetime,
) -> dict[str, Any]:
    """Insert a refresh-token session row.

    Args:
        connection: Open PostgreSQL connection.
        session_id: Refresh-session identifier.
        user_id: Authenticated user identifier.
        token_hash: SHA-256 hash of the raw refresh token.
        expires_at: Refresh token expiry timestamp.
        rotated_from_id: Prior refresh-session identifier when rotating tokens.
        issued_at: Refresh token issue timestamp.

    Returns:
        dict[str, Any]: Created session row.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        INSERT INTO pragma_refresh_tokens (
            id,
            user_id,
            token_hash,
            expires_at,
            rotated_from_id,
            issued_at
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING
            id,
            user_id,
            token_hash,
            expires_at,
            rotated_from_id,
            issued_at,
            revoked_at,
            last_used_at
        """,
        (session_id, user_id, token_hash, expires_at, rotated_from_id, issued_at),
    ).fetchone()


def get_active_refresh_session(
    connection: Connection, session_id: UUID, token_hash: str
) -> dict[str, Any] | None:
    """Return an active refresh-token session by identifier and hash.

    Args:
        connection: Open PostgreSQL connection.
        session_id: Refresh-session identifier.
        token_hash: SHA-256 hash of the raw refresh token.

    Returns:
        dict[str, Any] | None: Session row when active, otherwise None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            id,
            user_id,
            token_hash,
            expires_at,
            rotated_from_id,
            issued_at,
            revoked_at,
            last_used_at
        FROM pragma_refresh_tokens
        WHERE id = %s
          AND token_hash = %s
          AND revoked_at IS NULL
          AND expires_at > CURRENT_TIMESTAMP
        LIMIT 1
        """,
        (session_id, token_hash),
    ).fetchone()


def revoke_refresh_session(connection: Connection, session_id: UUID, revoked_at: datetime) -> None:
    """Revoke a refresh-token session.

    Args:
        connection: Open PostgreSQL connection.
        session_id: Refresh-session identifier.
        revoked_at: Revocation timestamp.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        UPDATE pragma_refresh_tokens
        SET revoked_at = %s, last_used_at = COALESCE(last_used_at, %s)
        WHERE id = %s
        """,
        (revoked_at, revoked_at, session_id),
    )
