# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Media-library queries for the Pragma backend.

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
from psycopg.types.json import Jsonb

_MEDIA_ORDER_BY = {
    'created_at': 'created_at DESC, id DESC',
    'updated_at': 'updated_at DESC, id DESC',
    'original_filename': 'original_filename ASC, id ASC',
    'size_bytes': 'size_bytes DESC, id DESC',
}


def create_media(
    connection: Connection,
    media_id: UUID,
    original_filename: str,
    storage_key: str,
    mime_type: str,
    size_bytes: int,
    width: int | None,
    height: int | None,
    alt_text: str | None,
    caption: str | None,
    description: str | None,
    variants: dict[str, str],
    uploader_user_id: UUID,
    created_at: datetime,
) -> dict[str, Any]:
    """Insert a new media record and return the created row.

    Args:
        connection: Open PostgreSQL connection.
        media_id: Media asset identifier to insert.
        original_filename: Client-visible filename.
        storage_key: Relative backend storage key.
        mime_type: Validated MIME type.
        size_bytes: Stored file size in bytes.
        width: Optional image width.
        height: Optional image height.
        alt_text: Optional alt text.
        caption: Optional caption.
        description: Optional description.
        variants: Stored derivative metadata.
        uploader_user_id: Authenticated uploader identifier.
        created_at: Timestamp for creation and update columns.

    Returns:
        dict[str, Any]: Created media row.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        INSERT INTO pragma_media_assets (
            id,
            original_filename,
            storage_key,
            mime_type,
            size_bytes,
            width,
            height,
            alt_text,
            caption,
            description,
            variants,
            uploader_user_id,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            id,
            original_filename,
            storage_key,
            mime_type,
            size_bytes,
            width,
            height,
            alt_text,
            caption,
            description,
            variants,
            uploader_user_id,
            created_at,
            updated_at
        """,
        (
            media_id,
            original_filename,
            storage_key,
            mime_type,
            size_bytes,
            width,
            height,
            alt_text,
            caption,
            description,
            Jsonb(variants),
            uploader_user_id,
            created_at,
            created_at,
        ),
    ).fetchone()


def count_media(connection: Connection, mime_type: str | None) -> int:
    """Return the number of media assets that match the supplied filters.

    Args:
        connection: Open PostgreSQL connection.
        mime_type: Optional MIME-type filter.

    Returns:
        int: Number of matching media assets.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    where_sql = ''
    params: tuple[Any, ...] = ()
    if mime_type is not None:
        where_sql = 'WHERE mime_type = %s'
        params = (mime_type,)

    row = connection.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM pragma_media_assets
        {where_sql}
        """,
        params,
    ).fetchone()
    return int(row['total'])


def list_media(
    connection: Connection,
    limit: int,
    offset: int,
    order_by: str,
    mime_type: str | None,
) -> list[dict[str, Any]]:
    """List media assets with pagination and optional filtering.

    Args:
        connection: Open PostgreSQL connection.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip before returning results.
        order_by: Safe order-by key selected by the service layer.
        mime_type: Optional MIME-type filter.

    Returns:
        list[dict[str, Any]]: Media rows for the current page.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    ordering = _MEDIA_ORDER_BY[order_by]
    where_sql = ''
    params: list[Any] = []
    if mime_type is not None:
        where_sql = 'WHERE mime_type = %s'
        params.append(mime_type)
    params.extend([limit, offset])

    return connection.execute(
        f"""
        SELECT
            id,
            original_filename,
            storage_key,
            mime_type,
            size_bytes,
            width,
            height,
            alt_text,
            caption,
            description,
            variants,
            uploader_user_id,
            created_at,
            updated_at
        FROM pragma_media_assets
        {where_sql}
        ORDER BY {ordering}
        LIMIT %s
        OFFSET %s
        """,
        tuple(params),
    ).fetchall()


def get_media_by_id(connection: Connection, media_id: UUID) -> dict[str, Any] | None:
    """Return a media asset by identifier.

    Args:
        connection: Open PostgreSQL connection.
        media_id: Media asset identifier.

    Returns:
        dict[str, Any] | None: Media row when found, otherwise None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            id,
            original_filename,
            storage_key,
            mime_type,
            size_bytes,
            width,
            height,
            alt_text,
            caption,
            description,
            variants,
            uploader_user_id,
            created_at,
            updated_at
        FROM pragma_media_assets
        WHERE id = %s
        LIMIT 1
        """,
        (media_id,),
    ).fetchone()


def delete_media(connection: Connection, media_id: UUID) -> None:
    """Delete a media asset by identifier.

    Args:
        connection: Open PostgreSQL connection.
        media_id: Media asset identifier to delete.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        DELETE FROM pragma_media_assets
        WHERE id = %s
        """,
        (media_id,),
    )
