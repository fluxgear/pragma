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
    """Return the persisted AI-provider settings singleton row."""

    return connection.execute(
        """
        SELECT
            settings.id,
            settings.enabled,
            settings.provider,
            settings.display_name,
            settings.api_mode,
            settings.auth_mode,
            settings.base_url,
            COALESCE(NULLIF(BTRIM(secrets.api_key), ''), settings.api_key) AS api_key,
            settings.embedding_model,
            settings.embedding_dimensions,
            settings.generation_model,
            settings.text_generation_enabled,
            settings.editor_assist_enabled,
            settings.seo_assist_enabled,
            settings.request_timeout_seconds,
            settings.last_test_status,
            settings.last_tested_at,
            settings.updated_by_user_id,
            settings.created_at,
            settings.updated_at
        FROM pragma_ai_provider_settings AS settings
        LEFT JOIN pragma_ai_provider_secrets AS secrets
            ON secrets.settings_id = settings.id
        WHERE settings.id = 1
        """
    ).fetchone()


def upsert_ai_provider_settings(
    connection: Connection,
    *,
    enabled: bool,
    provider: str | None,
    display_name: str | None,
    api_mode: str,
    auth_mode: str,
    base_url: str | None,
    api_key: str | None,
    embedding_model: str | None,
    embedding_dimensions: int | None,
    generation_model: str | None,
    text_generation_enabled: bool,
    editor_assist_enabled: bool,
    seo_assist_enabled: bool,
    request_timeout_seconds: int,
    updated_by_user_id: UUID,
    updated_at: datetime,
    last_test_status: str | None = None,
    last_tested_at: datetime | None = None,
) -> dict[str, Any]:
    """Insert or update the AI-provider settings singleton row."""

    connection.execute(
        """
        INSERT INTO pragma_ai_provider_settings (
            id, enabled, provider, display_name, api_mode, auth_mode, base_url,
            api_key, embedding_model, embedding_dimensions, generation_model,
            text_generation_enabled, editor_assist_enabled, seo_assist_enabled,
            request_timeout_seconds, last_test_status, last_tested_at,
            updated_by_user_id, created_at, updated_at
        )
        VALUES (1, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET
            enabled = EXCLUDED.enabled,
            provider = EXCLUDED.provider,
            display_name = EXCLUDED.display_name,
            api_mode = EXCLUDED.api_mode,
            auth_mode = EXCLUDED.auth_mode,
            base_url = EXCLUDED.base_url,
            api_key = NULL,
            embedding_model = EXCLUDED.embedding_model,
            embedding_dimensions = EXCLUDED.embedding_dimensions,
            generation_model = EXCLUDED.generation_model,
            text_generation_enabled = EXCLUDED.text_generation_enabled,
            editor_assist_enabled = EXCLUDED.editor_assist_enabled,
            seo_assist_enabled = EXCLUDED.seo_assist_enabled,
            request_timeout_seconds = EXCLUDED.request_timeout_seconds,
            last_test_status = EXCLUDED.last_test_status,
            last_tested_at = EXCLUDED.last_tested_at,
            updated_by_user_id = EXCLUDED.updated_by_user_id,
            updated_at = EXCLUDED.updated_at
        """,
        (
            enabled,
            provider,
            display_name,
            api_mode,
            auth_mode,
            base_url,
            embedding_model,
            embedding_dimensions,
            generation_model,
            text_generation_enabled,
            editor_assist_enabled,
            seo_assist_enabled,
            request_timeout_seconds,
            last_test_status,
            last_tested_at,
            updated_by_user_id,
            updated_at,
            updated_at,
        ),
    )

    normalized_api_key = api_key.strip() if api_key is not None else None
    if normalized_api_key:
        connection.execute(
            """
            INSERT INTO pragma_ai_provider_secrets (
                settings_id,
                api_key,
                created_at,
                updated_at
            )
            VALUES (1, %s, %s, %s)
            ON CONFLICT (settings_id) DO UPDATE
            SET
                api_key = EXCLUDED.api_key,
                updated_at = EXCLUDED.updated_at
            """,
            (normalized_api_key, updated_at, updated_at),
        )
    else:
        connection.execute(
            """
            DELETE FROM pragma_ai_provider_secrets
            WHERE settings_id = 1
            """
        )

    row = get_ai_provider_settings(connection)
    if row is None:
        raise RuntimeError('AI provider settings singleton row missing after upsert')
    return row


def clear_search_document_embeddings(connection: Connection) -> None:
    """Clear stored semantic embeddings after provider settings change.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        UPDATE pragma_search_documents
        SET
            embedding = NULL,
            embedding_provider = NULL,
            embedding_model = NULL,
            embedding_updated_at = NULL
        WHERE embedding IS NOT NULL
           OR embedding_provider IS NOT NULL
           OR embedding_model IS NOT NULL
           OR embedding_updated_at IS NOT NULL
        """
    )
