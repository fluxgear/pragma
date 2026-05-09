# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Storage queries for theme administration settings."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


def get_theme_settings(connection: Connection) -> dict[str, Any] | None:
    """Return the persisted theme-settings singleton row."""

    return connection.execute(
        """
        SELECT
            id, active_theme_id, design_settings, updated_by_user_id, created_at, updated_at
        FROM pragma_theme_settings
        WHERE id = 1
        """
    ).fetchone()


def upsert_theme_settings(
    connection: Connection,
    *,
    active_theme_id: str | None,
    design_settings: dict[str, Any],
    updated_by_user_id: UUID,
    updated_at: datetime,
) -> dict[str, Any]:
    """Insert or update the theme-settings singleton row."""

    return connection.execute(
        """
        INSERT INTO pragma_theme_settings (
            id, active_theme_id, design_settings, updated_by_user_id, created_at, updated_at
        )
        VALUES (1, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET
            active_theme_id = EXCLUDED.active_theme_id,
            design_settings = EXCLUDED.design_settings,
            updated_by_user_id = EXCLUDED.updated_by_user_id,
            updated_at = EXCLUDED.updated_at
        RETURNING
            id, active_theme_id, design_settings, updated_by_user_id, created_at, updated_at
        """,
        (
            active_theme_id,
            Jsonb(design_settings),
            updated_by_user_id,
            updated_at,
            updated_at,
        ),
    ).fetchone()


def delete_theme_settings(connection: Connection) -> None:
    """Delete the theme-settings singleton row to restore environment defaults."""

    connection.execute('DELETE FROM pragma_theme_settings WHERE id = 1')
