# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Navigation menu storage queries."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

PRIMARY_MENU_KEY = 'primary'


def get_navigation_menu_by_key(connection: Connection, key: str) -> dict[str, Any] | None:
    """Return a navigation menu singleton by key."""

    return connection.execute(
        """
        SELECT
            id,
            key,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        FROM pragma_navigation_menus
        WHERE key = %s
        LIMIT 1
        """,
        (key,),
    ).fetchone()


def upsert_navigation_menu(
    connection: Connection,
    *,
    key: str,
    user_id: UUID,
    updated_at: datetime,
) -> dict[str, Any]:
    """Insert or update a navigation menu singleton."""

    return connection.execute(
        """
        INSERT INTO pragma_navigation_menus (
            id,
            key,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (key) DO UPDATE
        SET
            updated_by_user_id = EXCLUDED.updated_by_user_id,
            updated_at = EXCLUDED.updated_at
        RETURNING
            id,
            key,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        """,
        (uuid4(), key, user_id, user_id, updated_at, updated_at),
    ).fetchone()


def list_navigation_menu_items(
    connection: Connection, menu_id: UUID
) -> list[dict[str, Any]]:
    """Return menu items in display order with internal-entry metadata."""

    return connection.execute(
        """
        SELECT
            item.id,
            item.menu_id,
            item.parent_item_id,
            item.position,
            item.label,
            item.link_type,
            item.content_entry_id,
            item.custom_url,
            item.enabled,
            item.created_at,
            item.updated_at,
            entry.slug AS entry_slug,
            entry.status AS entry_status,
            content_type.slug AS content_type_slug
        FROM pragma_navigation_menu_items AS item
        LEFT JOIN pragma_content_entries AS entry ON entry.id = item.content_entry_id
        LEFT JOIN pragma_content_types AS content_type
            ON content_type.id = entry.content_type_id
        WHERE item.menu_id = %s
        ORDER BY item.parent_item_id NULLS FIRST, item.position ASC, item.id ASC
        """,
        (menu_id,),
    ).fetchall()


def replace_navigation_menu_items(
    connection: Connection,
    *,
    menu_id: UUID,
    items: Sequence[dict[str, Any]],
    updated_at: datetime,
) -> list[dict[str, Any]]:
    """Replace all items for a navigation menu and return the new rows."""

    connection.execute(
        """
        DELETE FROM pragma_navigation_menu_items
        WHERE menu_id = %s
        """,
        (menu_id,),
    )

    def insert_items(
        parent_item_id: UUID | None,
        nested_items: Sequence[dict[str, Any]],
    ) -> None:
        for item in nested_items:
            item_id = uuid4()
            connection.execute(
                """
                INSERT INTO pragma_navigation_menu_items (
                    id,
                    menu_id,
                    parent_item_id,
                    position,
                    label,
                    link_type,
                    content_entry_id,
                    custom_url,
                    enabled,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    item_id,
                    menu_id,
                    parent_item_id,
                    item['position'],
                    item['label'],
                    item['link_type'],
                    item.get('content_entry_id'),
                    item.get('custom_url'),
                    item['enabled'],
                    updated_at,
                    updated_at,
                ),
            )
            children = item.get('children')
            if isinstance(children, Sequence) and not isinstance(children, str | bytes):
                insert_items(item_id, children)

    insert_items(None, items)
    return list_navigation_menu_items(connection, menu_id)


def list_navigation_content_options(
    connection: Connection,
    *,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Return content entries available to the navigation target picker."""

    return connection.execute(
        """
        SELECT
            e.id,
            e.slug,
            e.status,
            e.payload,
            ct.slug AS content_type_slug
        FROM pragma_content_entries AS e
        JOIN pragma_content_types AS ct ON ct.id = e.content_type_id
        ORDER BY ct.slug ASC, e.updated_at DESC, e.id ASC
        LIMIT %s
        OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


def count_navigation_content_options(connection: Connection) -> int:
    """Return the total number of content entries available as menu targets."""

    row = connection.execute(
        """
        SELECT count(*) AS total
        FROM pragma_content_entries
        """
    ).fetchone()
    return int(row['total'])
