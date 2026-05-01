# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Search query helpers for the Pragma backend.

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
from uuid import UUID

from psycopg import Connection

_DEFAULT_TRIGRAM_THRESHOLD = 0.2
_RRF_K = 60


def update_search_document_embedding(
    connection: Connection,
    *,
    entry_id: UUID,
    embedding_literal: str,
    embedding_provider: str,
    embedding_model: str,
    embedded_at: datetime,
) -> None:
    """Persist embedding values and metadata for one search document.

    Args:
        connection: Open PostgreSQL connection.
        entry_id: Search-document entry identifier.
        embedding_literal: pgvector literal to persist.
        embedding_provider: Provider key used to generate the embedding.
        embedding_model: Provider model used to generate the embedding.
        embedded_at: Timestamp associated with embedding generation.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        UPDATE pragma_search_documents
        SET
            embedding = %s::vector,
            embedding_provider = %s,
            embedding_model = %s,
            embedding_updated_at = %s
        WHERE entry_id = %s
        """,
        (embedding_literal, embedding_provider, embedding_model, embedded_at, entry_id),
    )


def list_search_documents_for_embedding_rebuild(
    connection: Connection,
    *,
    provider: str,
    embedding_model: str,
    expected_embedding_dimensions: int | None,
    content_type_slug: str | None,
    limit: int,
    offset: int = 0,
    stale_only: bool = True,
) -> list[dict[str, Any]]:
    """Return search documents eligible for embedding generation.

    Args:
        connection: Open PostgreSQL connection.
        provider: Provider key expected in embedding metadata.
        embedding_model: Model key expected in embedding metadata.
        expected_embedding_dimensions: Optional vector dimension count expected for the model.
        content_type_slug: Optional content-type slug filter.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip before returning rows.
        stale_only: Whether to restrict rows to stale or missing embeddings.

    Returns:
        list[dict[str, Any]]: Search-document rows eligible for embedding generation.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    sql = """
        SELECT
            entry_id,
            title_text,
            body_text,
            updated_at
        FROM pragma_search_documents
        WHERE (%s::text IS NULL OR content_type_slug = %s::text)
    """
    params: list[Any] = [content_type_slug, content_type_slug]

    if stale_only:
        sql += """
            AND (
                embedding IS NULL
                OR embedding_updated_at IS NULL
                OR embedding_updated_at < updated_at
                OR embedding_provider IS DISTINCT FROM %s
                OR embedding_model IS DISTINCT FROM %s
                OR (
                    %s::integer IS NOT NULL
                    AND embedding IS NOT NULL
                    AND vector_dims(embedding) IS DISTINCT FROM %s::integer
                )
            )
        """
        params.extend([
            provider,
            embedding_model,
            expected_embedding_dimensions,
            expected_embedding_dimensions,
        ])

    sql += """
        ORDER BY updated_at DESC, entry_id DESC
        LIMIT %s
        OFFSET %s
    """
    params.extend([limit, offset])
    return connection.execute(sql, tuple(params)).fetchall()


def count_search_embedding_contract_mismatches(
    connection: Connection,
    *,
    embedding_dimensions: int,
    embedding_provider: str | None,
    embedding_model: str | None,
    content_type_slug: str | None,
) -> int:
    """Return count of stored vectors outside the active semantic contract.

    Args:
        connection: Open PostgreSQL connection.
        embedding_dimensions: Expected query/provider embedding dimension count.
        embedding_provider: Optional expected embedding provider key.
        embedding_model: Optional expected embedding model key.
        content_type_slug: Optional content-type slug filter.

    Returns:
        int: Number of indexed documents requiring embedding rebuild for this contract.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    row = connection.execute(
        """
        SELECT COUNT(*) AS mismatch_count
        FROM pragma_search_documents
        WHERE embedding IS NOT NULL
          AND (%s::text IS NULL OR content_type_slug = %s::text)
          AND (
              vector_dims(embedding) IS DISTINCT FROM %s::integer
              OR (
                  %s::text IS NOT NULL
                  AND embedding_provider IS DISTINCT FROM %s::text
              )
              OR (
                  %s::text IS NOT NULL
                  AND embedding_model IS DISTINCT FROM %s::text
              )
          )
        """,
        (
            content_type_slug,
            content_type_slug,
            embedding_dimensions,
            embedding_provider,
            embedding_provider,
            embedding_model,
            embedding_model,
        ),
    ).fetchone()
    return int(row['mismatch_count'])


def search_embedding_column_exists(connection: Connection) -> bool:
    """Return whether the search table exposes an embedding column.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        bool: True when ``pragma_search_documents.embedding`` exists.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    row = connection.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'pragma_search_documents'
              AND column_name = 'embedding'
        ) AS exists
        """
    ).fetchone()
    return bool(row['exists'])


def upsert_search_document(
    connection: Connection,
    *,
    entry_id: UUID,
    content_type_id: UUID,
    content_type_slug: str,
    entry_slug: str,
    title_text: str,
    body_text: str,
    search_text_normalized: str,
    searchable_field_names: Sequence[str],
    published_at: datetime,
    updated_at: datetime,
    clear_embedding: bool,
) -> None:
    """Insert or update a derived search document.

    Args:
        connection: Open PostgreSQL connection.
        entry_id: Content-entry identifier.
        content_type_id: Owning content-type identifier.
        content_type_slug: Owning content-type slug.
        entry_slug: Content-entry slug.
        title_text: Derived title text.
        body_text: Derived body text.
        search_text_normalized: Normalized fuzzy-search text.
        searchable_field_names: Searchable field names included in the document.
        published_at: Entry publish timestamp.
        updated_at: Entry update timestamp.
        clear_embedding: Whether embedding fields should be cleared.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    update_embedding_sql = (
        (
            ",\n            embedding = NULL"
            ",\n            embedding_provider = NULL"
            ",\n            embedding_model = NULL"
            ",\n            embedding_updated_at = NULL"
        )
        if clear_embedding
        else ""
    )
    connection.execute(
        f"""
        INSERT INTO pragma_search_documents (
            entry_id,
            content_type_id,
            content_type_slug,
            entry_slug,
            title_text,
            body_text,
            search_text_normalized,
            searchable_field_names,
            search_tsv,
            published_at,
            updated_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            setweight(to_tsvector('simple', %s), 'A')
                || setweight(to_tsvector('simple', %s), 'B'),
            %s,
            %s
        )
        ON CONFLICT (entry_id) DO UPDATE
        SET
            content_type_id = EXCLUDED.content_type_id,
            content_type_slug = EXCLUDED.content_type_slug,
            entry_slug = EXCLUDED.entry_slug,
            title_text = EXCLUDED.title_text,
            body_text = EXCLUDED.body_text,
            search_text_normalized = EXCLUDED.search_text_normalized,
            searchable_field_names = EXCLUDED.searchable_field_names,
            search_tsv = EXCLUDED.search_tsv,
            published_at = EXCLUDED.published_at,
            updated_at = EXCLUDED.updated_at{update_embedding_sql}
        """,
        (
            entry_id,
            content_type_id,
            content_type_slug,
            entry_slug,
            title_text,
            body_text,
            search_text_normalized,
            list(searchable_field_names),
            title_text,
            body_text,
            published_at,
            updated_at,
        ),
    )


def delete_search_document(connection: Connection, entry_id: UUID) -> None:
    """Delete a derived search document by entry identifier.

    Args:
        connection: Open PostgreSQL connection.
        entry_id: Content-entry identifier.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        DELETE FROM pragma_search_documents
        WHERE entry_id = %s
        """,
        (entry_id,),
    )


def delete_search_documents_for_content_type(
    connection: Connection, content_type_id: UUID
) -> None:
    """Delete all derived search documents for a content type.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute(
        """
        DELETE FROM pragma_search_documents
        WHERE content_type_id = %s
        """,
        (content_type_id,),
    )


def list_search_source_entries_for_content_type(
    connection: Connection, content_type_id: UUID
) -> list[dict[str, Any]]:
    """Return entry rows needed to rebuild search documents.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier whose entries should be loaded.

    Returns:
        list[dict[str, Any]]: Entry rows for search synchronization.

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
            e.updated_at
        FROM pragma_content_entries AS e
        JOIN pragma_content_types AS ct ON ct.id = e.content_type_id
        WHERE e.content_type_id = %s
        ORDER BY e.updated_at DESC, e.id DESC
        """,
        (content_type_id,),
    ).fetchall()


def search_documents(
    connection: Connection,
    *,
    query: str,
    normalized_query: str,
    limit: int,
    offset: int,
    content_type_slug: str | None,
    strategies: Sequence[str],
    query_embedding: str | None = None,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    trigram_threshold: float = _DEFAULT_TRIGRAM_THRESHOLD,
) -> list[dict[str, Any]]:
    """Return public search results for the active strategy set.

    Args:
        connection: Open PostgreSQL connection.
        query: Search query text.
        normalized_query: Normalized search query used for fuzzy matching.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip before returning results.
        content_type_slug: Optional content-type slug filter.
        strategies: Active ranking strategies to execute.
        query_embedding: Optional pgvector literal for semantic search.
        embedding_provider: Optional provider key required for vector candidates.
        embedding_model: Optional model key required for vector candidates.
        trigram_threshold: Minimum trigram similarity score to keep a row.

    Returns:
        list[dict[str, Any]]: Search-result rows with repeated ``total_count`` metadata.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
        ValueError: If vector search is requested without an embedding literal.
    """

    if not strategies:
        return []

    ctes: list[str] = []
    ranked_sources: list[str] = []
    params: list[Any] = []

    if 'keyword' in strategies:
        ctes.append(
            """
            keyword_ranked AS (
                SELECT
                    entry_id,
                    ROW_NUMBER() OVER (
                        ORDER BY
                            ts_rank_cd(search_tsv, websearch_to_tsquery('simple', %s)) DESC,
                            published_at DESC,
                            entry_id DESC
                    ) AS rank_position
                FROM pragma_search_documents
                WHERE search_tsv @@ websearch_to_tsquery('simple', %s)
                  AND (%s::text IS NULL OR content_type_slug = %s::text)
            )
            """
        )
        params.extend([query, query, content_type_slug, content_type_slug])
        ranked_sources.append('SELECT entry_id, rank_position FROM keyword_ranked')

    if 'fuzzy' in strategies:
        ctes.append(
            """
            fuzzy_ranked AS (
                SELECT
                    entry_id,
                    ROW_NUMBER() OVER (
                        ORDER BY
                            similarity(search_text_normalized, %s) DESC,
                            published_at DESC,
                            entry_id DESC
                    ) AS rank_position
                FROM pragma_search_documents
                WHERE similarity(search_text_normalized, %s) >= %s
                  AND (%s::text IS NULL OR content_type_slug = %s::text)
            )
            """
        )
        params.extend(
            [
                normalized_query,
                normalized_query,
                trigram_threshold,
                content_type_slug,
                content_type_slug,
            ]
        )
        ranked_sources.append('SELECT entry_id, rank_position FROM fuzzy_ranked')

    if 'vector' in strategies:
        if query_embedding is None:
            raise ValueError('query_embedding is required when vector search is active')
        ctes.append(
            """
            vector_ranked AS (
                SELECT
                    d.entry_id,
                    ROW_NUMBER() OVER (
                        ORDER BY
                            d.embedding <=> q.query_embedding ASC,
                            d.published_at DESC,
                            d.entry_id DESC
                    ) AS rank_position
                FROM pragma_search_documents AS d
                CROSS JOIN (SELECT %s::vector AS query_embedding) AS q
                WHERE d.embedding IS NOT NULL
                  AND vector_dims(d.embedding) = vector_dims(q.query_embedding)
                  AND (%s::text IS NULL OR d.embedding_provider = %s::text)
                  AND (%s::text IS NULL OR d.embedding_model = %s::text)
                  AND (%s::text IS NULL OR d.content_type_slug = %s::text)
            )
            """
        )
        params.extend([
            query_embedding,
            embedding_provider,
            embedding_provider,
            embedding_model,
            embedding_model,
            content_type_slug,
            content_type_slug,
        ])
        ranked_sources.append('SELECT entry_id, rank_position FROM vector_ranked')

    union_sql = '\n                    UNION ALL\n                    '.join(ranked_sources)
    sql = f"""
        WITH
            {','.join(ctes)},
            fused AS (
                SELECT
                    entry_id,
                    SUM(1.0 / ({_RRF_K} + rank_position)) AS fused_score
                FROM (
                    {union_sql}
                ) AS ranked
                GROUP BY entry_id
            )
        SELECT
            d.entry_id AS id,
            d.content_type_slug,
            d.entry_slug AS slug,
            d.title_text AS title,
            d.body_text,
            d.published_at,
            COUNT(*) OVER () AS total_count
        FROM fused
        JOIN pragma_search_documents AS d ON d.entry_id = fused.entry_id
        ORDER BY fused.fused_score DESC, d.published_at DESC, d.entry_id DESC
        LIMIT %s
        OFFSET %s
    """
    params.extend([limit, offset])
    return connection.execute(sql, tuple(params)).fetchall()
