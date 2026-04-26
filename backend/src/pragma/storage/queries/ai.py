# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Storage queries for AI-provider settings.

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


def get_ai_provider_settings(connection: Connection) -> dict[str, Any] | None:
    """Return the persisted AI-provider settings singleton row.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        dict[str, Any] | None: Stored settings row when present.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            id,
            enabled,
            provider,
            base_url,
            api_key,
            embedding_model,
            request_timeout_seconds,
            updated_by_user_id,
            created_at,
            updated_at
        FROM pragma_ai_provider_settings
        WHERE id = 1
        """
    ).fetchone()


def upsert_ai_provider_settings(
    connection: Connection,
    *,
    enabled: bool,
    provider: str,
    base_url: str,
    api_key: str | None,
    embedding_model: str,
    request_timeout_seconds: int,
    updated_by_user_id: UUID,
    updated_at: datetime,
) -> dict[str, Any]:
    """Insert or update the AI-provider settings singleton row.

    Args:
        connection: Open PostgreSQL connection.
        enabled: Whether provider use is enabled for semantic search.
        provider: Provider identifier key.
        base_url: Provider API base URL.
        api_key: Provider API key or ``None`` when disabled.
        embedding_model: Provider model identifier.
        request_timeout_seconds: Request timeout value in seconds.
        updated_by_user_id: User who performed the update.
        updated_at: Current update timestamp.

    Returns:
        dict[str, Any]: Persisted singleton row after update.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        INSERT INTO pragma_ai_provider_settings (
            id,
            enabled,
            provider,
            base_url,
            api_key,
            embedding_model,
            request_timeout_seconds,
            updated_by_user_id,
            created_at,
            updated_at
        )
        VALUES (
            1,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        ON CONFLICT (id) DO UPDATE
        SET
            enabled = EXCLUDED.enabled,
            provider = EXCLUDED.provider,
            base_url = EXCLUDED.base_url,
            api_key = EXCLUDED.api_key,
            embedding_model = EXCLUDED.embedding_model,
            request_timeout_seconds = EXCLUDED.request_timeout_seconds,
            updated_by_user_id = EXCLUDED.updated_by_user_id,
            updated_at = EXCLUDED.updated_at
        RETURNING
            id,
            enabled,
            provider,
            base_url,
            api_key,
            embedding_model,
            request_timeout_seconds,
            updated_by_user_id,
            created_at,
            updated_at
        """,
        (
            enabled,
            provider,
            base_url,
            api_key,
            embedding_model,
            request_timeout_seconds,
            updated_by_user_id,
            updated_at,
            updated_at,
        ),
    ).fetchone()
