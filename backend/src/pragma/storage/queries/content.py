# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Content-engine queries for the Pragma backend.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

_CONTENT_TYPE_ORDER_BY = {
    "created_at": "created_at DESC, id DESC",
    "updated_at": "updated_at DESC, id DESC",
    "name": "name ASC, id ASC",
    "slug": "slug ASC, id ASC",
}

_ENTRY_ORDER_BY = {
    "created_at": "e.created_at DESC, e.id DESC",
    "updated_at": "e.updated_at DESC, e.id DESC",
    "published_at": "e.published_at DESC NULLS LAST, e.id DESC",
    "slug": "e.slug ASC, e.id ASC",
}


def create_content_type(
    connection: Connection,
    content_type_id: UUID,
    name: str,
    slug: str,
    description: str | None,
    user_id: UUID,
    created_at: datetime,
) -> dict[str, Any]:
    """Insert a new content type and return the created record.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier to insert.
        name: Human-readable content-type name.
        slug: Normalized content-type slug.
        description: Optional content-type description.
        user_id: Authenticated user creating the content type.
        created_at: Timestamp for creation and update columns.

    Returns:
        dict[str, Any]: Created content-type row.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        INSERT INTO pragma_content_types (
            id,
            name,
            slug,
            description,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            id,
            name,
            slug,
            description,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        """,
        (
            content_type_id,
            name,
            slug,
            description,
            user_id,
            user_id,
            created_at,
            created_at,
        ),
    ).fetchone()


def update_content_type(
    connection: Connection,
    content_type_id: UUID,
    name: str,
    slug: str,
    description: str | None,
    user_id: UUID,
    updated_at: datetime,
) -> dict[str, Any]:
    """Update an existing content type and return the updated record.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier to update.
        name: Human-readable content-type name.
        slug: Normalized content-type slug.
        description: Optional content-type description.
        user_id: Authenticated user updating the content type.
        updated_at: Timestamp for the update.

    Returns:
        dict[str, Any]: Updated content-type row.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        UPDATE pragma_content_types
        SET
            name = %s,
            slug = %s,
            description = %s,
            updated_by_user_id = %s,
            updated_at = %s
        WHERE id = %s
        RETURNING
            id,
            name,
            slug,
            description,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        """,
        (name, slug, description, user_id, updated_at, content_type_id),
    ).fetchone()


def get_content_type_by_id(connection: Connection, content_type_id: UUID) -> dict[str, Any] | None:
    """Return a content type by identifier.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier.

    Returns:
        dict[str, Any] | None: Content-type row when found, otherwise None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            id,
            name,
            slug,
            description,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        FROM pragma_content_types
        WHERE id = %s
        LIMIT 1
        """,
        (content_type_id,),
    ).fetchone()


def get_content_type_by_slug(connection: Connection, slug: str) -> dict[str, Any] | None:
    """Return a content type by slug.

    Args:
        connection: Open PostgreSQL connection.
        slug: Normalized content-type slug.

    Returns:
        dict[str, Any] | None: Content-type row when found, otherwise None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            id,
            name,
            slug,
            description,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        FROM pragma_content_types
        WHERE slug = %s
        LIMIT 1
        """,
        (slug,),
    ).fetchone()


def count_content_types(connection: Connection) -> int:
    """Return the total number of content types.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        int: Number of stored content types.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    row = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM pragma_content_types
        """
    ).fetchone()
    return int(row["total"])


def list_content_types(
    connection: Connection,
    limit: int,
    offset: int,
    order_by: str,
) -> list[dict[str, Any]]:
    """List content types with pagination.

    Args:
        connection: Open PostgreSQL connection.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip before returning results.
        order_by: Safe order-by key selected by the service layer.

    Returns:
        list[dict[str, Any]]: Content-type rows for the current page.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    ordering = _CONTENT_TYPE_ORDER_BY[order_by]
    return connection.execute(
        f"""
        SELECT
            id,
            name,
            slug,
            description,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        FROM pragma_content_types
        ORDER BY {ordering}
        LIMIT %s
        OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


def delete_content_type(connection: Connection, content_type_id: UUID) -> None:
    """Delete a content type by identifier.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier to delete.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        DELETE FROM pragma_content_types
        WHERE id = %s
        """,
        (content_type_id,),
    )


def replace_field_definitions(
    connection: Connection,
    content_type_id: UUID,
    field_definitions: Sequence[dict[str, Any]],
    updated_at: datetime,
) -> None:
    """Replace all field definitions for a content type.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier owning the fields.
        field_definitions: Serialized field-definition payloads.
        updated_at: Timestamp for create/update columns.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        DELETE FROM pragma_content_fields
        WHERE content_type_id = %s
        """,
        (content_type_id,),
    )

    for position, field_definition in enumerate(field_definitions, start=1):
        connection.execute(
            """
            INSERT INTO pragma_content_fields (
                id,
                content_type_id,
                name,
                label,
                field_type,
                is_required,
                position,
                config,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid4(),
                content_type_id,
                field_definition["name"],
                field_definition["label"],
                field_definition["kind"],
                field_definition["required"],
                position,
                Jsonb(field_definition["config"]),
                updated_at,
                updated_at,
            ),
        )


def get_field_definitions(connection: Connection, content_type_id: UUID) -> list[dict[str, Any]]:
    """Return all field definitions for a content type in display order.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier.

    Returns:
        list[dict[str, Any]]: Serialized field-definition rows.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            id,
            content_type_id,
            name,
            label,
            field_type,
            is_required,
            position,
            config,
            created_at,
            updated_at
        FROM pragma_content_fields
        WHERE content_type_id = %s
        ORDER BY position ASC, name ASC
        """,
        (content_type_id,),
    ).fetchall()


def list_field_definitions(
    connection: Connection, content_type_ids: Sequence[UUID]
) -> dict[UUID, list[dict[str, Any]]]:
    """Return field definitions grouped by content-type identifier.

    Args:
        connection: Open PostgreSQL connection.
        content_type_ids: Content-type identifiers to load.

    Returns:
        dict[UUID, list[dict[str, Any]]]: Field-definition rows grouped by type.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    if not content_type_ids:
        return {}

    rows = connection.execute(
        """
        SELECT
            id,
            content_type_id,
            name,
            label,
            field_type,
            is_required,
            position,
            config,
            created_at,
            updated_at
        FROM pragma_content_fields
        WHERE content_type_id = ANY(%s)
        ORDER BY content_type_id ASC, position ASC, name ASC
        """,
        (list(content_type_ids),),
    ).fetchall()

    grouped: dict[UUID, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["content_type_id"], []).append(row)
    return grouped


def count_entries_for_content_type(connection: Connection, content_type_id: UUID) -> int:
    """Return the number of entries that belong to a content type.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier.

    Returns:
        int: Number of stored entries for the content type.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    row = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM pragma_content_entries
        WHERE content_type_id = %s
        """,
        (content_type_id,),
    ).fetchone()
    return int(row["total"])


def list_entries_for_content_type_validation(
    connection: Connection, content_type_id: UUID
) -> list[dict[str, Any]]:
    """Return entry payloads for validating a content-type update.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier.

    Returns:
        list[dict[str, Any]]: Entry rows needed for validation.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            id,
            slug,
            status,
            payload,
            published_at
        FROM pragma_content_entries
        WHERE content_type_id = %s
        ORDER BY created_at ASC, id ASC
        """,
        (content_type_id,),
    ).fetchall()


def create_entry(
    connection: Connection,
    entry_id: UUID,
    content_type_id: UUID,
    slug: str,
    status: str,
    payload: dict[str, Any],
    published_at: datetime | None,
    user_id: UUID,
    created_at: datetime,
) -> dict[str, Any]:
    """Insert a new content entry and return the created record.

    Args:
        connection: Open PostgreSQL connection.
        entry_id: Entry identifier to insert.
        content_type_id: Content-type identifier that owns the entry.
        slug: Normalized entry slug.
        status: Publish-state string for the entry.
        payload: Validated JSON payload for the entry.
        published_at: Timestamp when the entry became published, if any.
        user_id: Authenticated user creating the entry.
        created_at: Timestamp for creation and update columns.

    Returns:
        dict[str, Any]: Created entry row.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        INSERT INTO pragma_content_entries (
            id,
            content_type_id,
            slug,
            status,
            payload,
            published_at,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            id,
            content_type_id,
            slug,
            status,
            payload,
            published_at,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        """,
        (
            entry_id,
            content_type_id,
            slug,
            status,
            Jsonb(payload),
            published_at,
            user_id,
            user_id,
            created_at,
            created_at,
        ),
    ).fetchone()


def update_entry(
    connection: Connection,
    entry_id: UUID,
    slug: str,
    status: str,
    payload: dict[str, Any],
    published_at: datetime | None,
    user_id: UUID,
    updated_at: datetime,
) -> dict[str, Any]:
    """Update an existing content entry and return the updated record.

    Args:
        connection: Open PostgreSQL connection.
        entry_id: Entry identifier to update.
        slug: Normalized entry slug.
        status: Publish-state string for the entry.
        payload: Validated JSON payload for the entry.
        published_at: Timestamp when the entry became published, if any.
        user_id: Authenticated user updating the entry.
        updated_at: Timestamp for the update.

    Returns:
        dict[str, Any]: Updated entry row.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        UPDATE pragma_content_entries
        SET
            slug = %s,
            status = %s,
            payload = %s,
            published_at = %s,
            updated_by_user_id = %s,
            updated_at = %s
        WHERE id = %s
        RETURNING
            id,
            content_type_id,
            slug,
            status,
            payload,
            published_at,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        """,
        (slug, status, Jsonb(payload), published_at, user_id, updated_at, entry_id),
    ).fetchone()


def get_entry_by_id(connection: Connection, entry_id: UUID) -> dict[str, Any] | None:
    """Return a content entry by identifier.

    Args:
        connection: Open PostgreSQL connection.
        entry_id: Entry identifier.

    Returns:
        dict[str, Any] | None: Entry row when found, otherwise None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            e.id,
            e.content_type_id,
            ct.slug AS content_type_slug,
            e.slug,
            e.status,
            e.payload,
            e.published_at,
            e.created_by_user_id,
            e.updated_by_user_id,
            e.created_at,
            e.updated_at
        FROM pragma_content_entries AS e
        JOIN pragma_content_types AS ct ON ct.id = e.content_type_id
        WHERE e.id = %s
        LIMIT 1
        """,
        (entry_id,),
    ).fetchone()


def get_entry_by_slug(
    connection: Connection, content_type_id: UUID, slug: str
) -> dict[str, Any] | None:
    """Return a content entry by content type and slug.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier that scopes the slug.
        slug: Normalized entry slug.

    Returns:
        dict[str, Any] | None: Entry row when found, otherwise None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    return connection.execute(
        """
        SELECT
            id,
            content_type_id,
            slug,
            status,
            payload,
            published_at,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        FROM pragma_content_entries
        WHERE content_type_id = %s AND slug = %s
        LIMIT 1
        """,
        (content_type_id, slug),
    ).fetchone()


def count_entries(
    connection: Connection,
    content_type_id: UUID | None,
    content_type_slug: str | None,
    status: str | None,
) -> int:
    """Return the number of entries that match the supplied filters.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Optional content-type identifier filter.
        content_type_slug: Optional content-type slug filter.
        status: Optional publish-state filter.

    Returns:
        int: Number of matching entries.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    where_clauses: list[str] = []
    params: list[Any] = []

    if content_type_id is not None:
        where_clauses.append("e.content_type_id = %s")
        params.append(content_type_id)
    if content_type_slug is not None:
        where_clauses.append("ct.slug = %s")
        params.append(content_type_slug)
    if status is not None:
        where_clauses.append("e.status = %s")
        params.append(status)

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    row = connection.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM pragma_content_entries AS e
        JOIN pragma_content_types AS ct ON ct.id = e.content_type_id
        {where_sql}
        """,
        tuple(params),
    ).fetchone()
    return int(row["total"])


def list_entries(
    connection: Connection,
    limit: int,
    offset: int,
    order_by: str,
    content_type_id: UUID | None,
    content_type_slug: str | None,
    status: str | None,
) -> list[dict[str, Any]]:
    """List content entries with pagination and optional filters.

    Args:
        connection: Open PostgreSQL connection.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip before returning results.
        order_by: Safe order-by key selected by the service layer.
        content_type_id: Optional content-type identifier filter.
        content_type_slug: Optional content-type slug filter.
        status: Optional publish-state filter.

    Returns:
        list[dict[str, Any]]: Entry rows for the current page.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    where_clauses: list[str] = []
    params: list[Any] = []

    if content_type_id is not None:
        where_clauses.append("e.content_type_id = %s")
        params.append(content_type_id)
    if content_type_slug is not None:
        where_clauses.append("ct.slug = %s")
        params.append(content_type_slug)
    if status is not None:
        where_clauses.append("e.status = %s")
        params.append(status)

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    ordering = _ENTRY_ORDER_BY[order_by]
    params.extend([limit, offset])

    return connection.execute(
        f"""
        SELECT
            e.id,
            e.content_type_id,
            ct.slug AS content_type_slug,
            e.slug,
            e.status,
            e.payload,
            e.published_at,
            e.created_by_user_id,
            e.updated_by_user_id,
            e.created_at,
            e.updated_at
        FROM pragma_content_entries AS e
        JOIN pragma_content_types AS ct ON ct.id = e.content_type_id
        {where_sql}
        ORDER BY {ordering}
        LIMIT %s
        OFFSET %s
        """,
        tuple(params),
    ).fetchall()


def delete_entry(connection: Connection, entry_id: UUID) -> None:
    """Delete a content entry by identifier.

    Args:
        connection: Open PostgreSQL connection.
        entry_id: Entry identifier to delete.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        DELETE FROM pragma_content_entries
        WHERE id = %s
        """,
        (entry_id,),
    )
