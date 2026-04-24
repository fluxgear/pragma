# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Service-layer logic for Pragma search.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from html.parser import HTMLParser
from http import HTTPStatus
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg import Error as PsycopgError

from pragma.config import Settings
from pragma.content.models import (
    ContentStatus,
    FieldDefinitionModel,
    TextFieldDefinition,
    parse_field_definition,
)
from pragma.errors import SearchError
from pragma.search.models import (
    SearchEntryResponse,
    SearchMode,
    SearchQueryParams,
    SearchQueryResponse,
)
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.capabilities import get_extension_capabilities
from pragma.storage.queries.search import (
    delete_search_document,
    delete_search_documents_for_content_type,
    list_search_source_entries_for_content_type,
    search_documents,
    search_embedding_column_exists,
    upsert_search_document,
)

_MAX_EXCERPT_LENGTH = 240
_MULTI_HYPHEN_PATTERN = re.compile(r'-{2,}')
_PREFERRED_TITLE_FIELDS = ('title', 'name')
_TEXT_FIELD_KINDS = {'text', 'long_text', 'rich_text'}


class _SearchHTMLStripper(HTMLParser):
    """Extract plain text from sanitized rich-text HTML.

    Args:
        HTMLParser: Standard-library HTML parser base class.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self) -> None:
        """Initialize the HTML text extractor.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        """Capture text nodes.

        Args:
            data: Text-node payload.

        Returns:
            None.

        Raises:
            None.
        """

        self.parts.append(data)


def _collapse_whitespace(value: str) -> str:
    """Collapse internal whitespace and trim the result.

    Args:
        value: Raw string value.

    Returns:
        str: Normalized whitespace representation.

    Raises:
        None.
    """

    return re.sub(r'\s+', ' ', value).strip()


def _normalize_search_text(value: str) -> str:
    """Normalize searchable text for fuzzy matching.

    Args:
        value: Raw searchable text.

    Returns:
        str: Case-folded searchable text with normalized whitespace.

    Raises:
        None.
    """

    return _collapse_whitespace(unicodedata.normalize('NFKC', value).casefold())


def _normalize_slug(value: str) -> str:
    """Normalize a slug candidate for search filters.

    Args:
        value: Raw slug candidate.

    Returns:
        str: Normalized slug.

    Raises:
        SearchError: If the slug does not contain a usable value.
    """

    normalized = unicodedata.normalize('NFKD', value)
    ascii_value = normalized.encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_value.lower()).strip('-')
    slug = _MULTI_HYPHEN_PATTERN.sub('-', slug)
    slug = slug[:160].strip('-')
    if not slug:
        raise SearchError(
            detail='Content-type slug filter must contain letters or numbers',
            code='SEARCH_FILTER_INVALID',
        )
    return slug


def _strip_rich_text(value: str) -> str:
    """Strip HTML markup from sanitized rich-text fragments.

    Args:
        value: Rich-text HTML fragment.

    Returns:
        str: Plain-text representation.

    Raises:
        None.
    """

    parser = _SearchHTMLStripper()
    parser.feed(value)
    parser.close()
    return _collapse_whitespace(''.join(parser.parts))


def _field_definition_from_row(row: Mapping[str, Any]) -> FieldDefinitionModel:
    """Build a typed field definition from a storage row.

    Args:
        row: Storage-layer row from ``pragma_content_fields``.

    Returns:
        FieldDefinitionModel: Parsed field-definition model.

    Raises:
        ValidationError: If the row cannot be parsed.
    """

    config = dict(row['config'] or {})
    return parse_field_definition(
        {
            'name': row['name'],
            'label': row['label'],
            'kind': row['field_type'],
            'required': row['is_required'],
            **config,
        }
    )


def _text_value_for_search(
    field_definition: FieldDefinitionModel, payload: Mapping[str, Any]
) -> str:
    """Extract normalized searchable text for one field.

    Args:
        field_definition: Parsed field definition.
        payload: Stored content payload.

    Returns:
        str: Searchable plain-text value for the field.

    Raises:
        None.
    """

    if field_definition.kind not in _TEXT_FIELD_KINDS:
        return ''
    raw_value = payload.get(field_definition.name)
    if not isinstance(raw_value, str):
        return ''
    if isinstance(field_definition, TextFieldDefinition) and field_definition.kind == 'rich_text':
        return _strip_rich_text(raw_value)
    return _collapse_whitespace(raw_value)


def _select_title(
    payload: Mapping[str, Any],
    field_definitions: Sequence[FieldDefinitionModel],
    entry_slug: str,
) -> str:
    """Derive a public-facing title for a search document.

    Args:
        payload: Stored content payload.
        field_definitions: Parsed field definitions for the content type.
        entry_slug: Fallback entry slug.

    Returns:
        str: Derived title text.

    Raises:
        None.
    """

    for field_name in _PREFERRED_TITLE_FIELDS:
        value = payload.get(field_name)
        if isinstance(value, str):
            collapsed = _collapse_whitespace(value)
            if collapsed:
                return _strip_rich_text(collapsed) if '<' in collapsed else collapsed

    for field_definition in field_definitions:
        value = _text_value_for_search(field_definition, payload)
        if value:
            return value[:160]

    return entry_slug


def _build_search_document(
    *,
    entry_id: UUID,
    content_type_id: UUID,
    content_type_slug: str,
    entry_slug: str,
    payload: Mapping[str, Any],
    field_definitions: Sequence[FieldDefinitionModel],
    published_at: Any,
    updated_at: Any,
) -> dict[str, Any]:
    """Build a derived search document payload from content state.

    Args:
        entry_id: Content-entry identifier.
        content_type_id: Owning content-type identifier.
        content_type_slug: Owning content-type slug.
        entry_slug: Content-entry slug.
        payload: Stored content payload.
        field_definitions: Parsed field definitions for the content type.
        published_at: Stored publish timestamp.
        updated_at: Stored update timestamp.

    Returns:
        dict[str, Any]: Search-document payload ready for storage queries.

    Raises:
        SearchError: If published timestamps are unexpectedly missing.
    """

    if published_at is None:
        raise SearchError(
            detail='Published search documents must have a publish timestamp',
            code='SEARCH_DOCUMENT_INVALID',
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    field_entries: list[tuple[str, str]] = []
    for field_definition in field_definitions:
        value = _text_value_for_search(field_definition, payload)
        if not value:
            continue
        field_entries.append((field_definition.name, value))

    searchable_field_names = [name for name, _ in field_entries]
    title_text = _select_title(payload, field_definitions, entry_slug)
    body_segments = [
        value for name, value in field_entries if name not in _PREFERRED_TITLE_FIELDS
    ]
    if not body_segments:
        body_segments = [value for _, value in field_entries[:1]]
    body_text = _collapse_whitespace(' '.join(body_segments))
    normalized_text = _normalize_search_text(' '.join([title_text, body_text]))

    return {
        'entry_id': entry_id,
        'content_type_id': content_type_id,
        'content_type_slug': content_type_slug,
        'entry_slug': entry_slug,
        'title_text': title_text,
        'body_text': body_text,
        'search_text_normalized': normalized_text,
        'searchable_field_names': searchable_field_names,
        'published_at': published_at,
        'updated_at': updated_at,
    }


def _build_excerpt(body_text: str, title_text: str) -> str:
    """Build a bounded plain-text excerpt for API responses.

    Args:
        body_text: Stored body text from the search document.
        title_text: Stored title text from the search document.

    Returns:
        str: Plain-text excerpt bounded to a stable maximum length.

    Raises:
        None.
    """

    source_text = body_text or title_text
    if len(source_text) <= _MAX_EXCERPT_LENGTH:
        return source_text
    truncated = source_text[: _MAX_EXCERPT_LENGTH - 1].rstrip()
    return f'{truncated}…'


def _vector_literal(values: Sequence[float]) -> str:
    """Build a pgvector literal from a Python float sequence.

    Args:
        values: Query-embedding values.

    Returns:
        str: pgvector literal string.

    Raises:
        None.
    """

    return '[' + ','.join(format(value, 'g') for value in values) + ']'


def _resolve_active_strategies(
    *,
    params: SearchQueryParams,
    settings: Settings,
    pg_trgm_installed: bool,
    vector_ready: bool,
) -> tuple[list[str], SearchMode]:
    """Resolve actual strategy execution for a search request.

    Args:
        params: Requested search parameters.
        settings: Application settings.
        pg_trgm_installed: Whether ``pg_trgm`` is installed.
        vector_ready: Whether semantic search can execute now.

    Returns:
        tuple[list[str], SearchMode]: Active strategies and the applied mode.

    Raises:
        None.
    """

    fuzzy_available = pg_trgm_installed
    vector_available = settings.search_enable_semantic and vector_ready

    if params.mode is SearchMode.KEYWORD:
        strategies = ['keyword']
    elif params.mode is SearchMode.FUZZY:
        strategies = ['fuzzy'] if fuzzy_available else ['keyword']
    elif params.mode is SearchMode.VECTOR:
        strategies = ['vector'] if vector_available else ['keyword']
    else:
        strategies = ['keyword']
        if fuzzy_available:
            strategies.append('fuzzy')
        if vector_available:
            strategies.append('vector')
        if params.mode is SearchMode.HYBRID and len(strategies) == 1:
            strategies = ['keyword']

    mode_applied = SearchMode.HYBRID if len(strategies) > 1 else SearchMode(strategies[0])
    return strategies, mode_applied


def search_public_entries(
    storage: DatabasePool, settings: Settings, params: SearchQueryParams
) -> SearchQueryResponse:
    """Search published content entries for the public API.

    Args:
        storage: Initialized database pool manager.
        settings: Application settings.
        params: Search query parameters.

    Returns:
        SearchQueryResponse: Paginated public-search response.

    Raises:
        SearchError: If the supplied search request is invalid or search fails.
    """

    query = _collapse_whitespace(params.query)
    if not query:
        raise SearchError(detail='Search query must not be blank', code='SEARCH_QUERY_INVALID')

    normalized_content_type_slug = (
        _normalize_slug(params.content_type_slug)
        if params.content_type_slug is not None
        else None
    )

    try:
        with storage.connection() as connection:
            capabilities = get_extension_capabilities(connection)
            vector_ready = (
                params.query_embedding is not None
                and capabilities['pgvector']['installed']
                and search_embedding_column_exists(connection)
            )
            strategies, mode_applied = _resolve_active_strategies(
                params=params,
                settings=settings,
                pg_trgm_installed=capabilities['pg_trgm']['installed'],
                vector_ready=vector_ready,
            )
            rows = search_documents(
                connection,
                query=query,
                normalized_query=_normalize_search_text(query),
                limit=params.limit,
                offset=params.offset,
                content_type_slug=normalized_content_type_slug,
                strategies=strategies,
                query_embedding=(
                    _vector_literal(params.query_embedding)
                    if 'vector' in strategies and params.query_embedding is not None
                    else None
                ),
            )
    except SearchError:
        raise
    except PsycopgError as exc:
        raise SearchError(
            detail='Unable to execute search query',
            code='SEARCH_QUERY_FAILED',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        ) from exc

    items = [
        SearchEntryResponse.from_record(
            row, excerpt=_build_excerpt(str(row['body_text']), str(row['title']))
        )
        for row in rows
    ]
    total = int(rows[0]['total_count']) if rows else 0
    return SearchQueryResponse(
        items=items,
        total=total,
        limit=params.limit,
        offset=params.offset,
        query=query,
        mode_requested=params.mode,
        mode_applied=mode_applied,
        applied_strategies=strategies,
    )


def sync_search_document(
    connection: Connection,
    *,
    entry_row: Mapping[str, Any],
    content_type_slug: str,
    field_definitions: Sequence[FieldDefinitionModel],
) -> None:
    """Synchronize one derived search document to the current entry state.

    Args:
        connection: Open PostgreSQL connection.
        entry_row: Content-entry storage row.
        content_type_slug: Owning content-type slug.
        field_definitions: Parsed field definitions for the content type.

    Returns:
        None.

    Raises:
        clear_embedding=search_embedding_column_exists(connection),
        psycopg.Error: If PostgreSQL query execution fails.
    """

    if entry_row['status'] != ContentStatus.PUBLISHED.value:
        delete_search_document(connection, entry_row['id'])
        return

    document = _build_search_document(
        entry_id=entry_row['id'],
        content_type_id=entry_row['content_type_id'],
        content_type_slug=content_type_slug,
        entry_slug=str(entry_row['slug']),
        payload=dict(entry_row['payload'] or {}),
        field_definitions=field_definitions,
        published_at=entry_row['published_at'],
        updated_at=entry_row['updated_at'],
    )
    upsert_search_document(
        connection,
        entry_id=document['entry_id'],
        content_type_id=document['content_type_id'],
        content_type_slug=document['content_type_slug'],
        entry_slug=document['entry_slug'],
        title_text=document['title_text'],
        body_text=document['body_text'],
        search_text_normalized=document['search_text_normalized'],
        searchable_field_names=document['searchable_field_names'],
        published_at=document['published_at'],
        updated_at=document['updated_at'],
        clear_embedding=search_embedding_column_exists(connection),
    )


def rebuild_search_documents_for_content_type(
    connection: Connection,
    *,
    content_type_id: UUID,
    field_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Rebuild all derived search documents for a content type.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier.
        field_rows: Current field-definition rows for the content type.

    Returns:
        None.

    Raises:
        SearchError: If a published entry cannot be transformed.
        psycopg.Error: If PostgreSQL query execution fails.
    """

    field_definitions = [_field_definition_from_row(row) for row in field_rows]
    clear_embedding = search_embedding_column_exists(connection)
    delete_search_documents_for_content_type(connection, content_type_id)

    for entry_row in list_search_source_entries_for_content_type(connection, content_type_id):
        if entry_row['status'] != ContentStatus.PUBLISHED.value:
            continue
        document = _build_search_document(
            entry_id=entry_row['id'],
            content_type_id=entry_row['content_type_id'],
            content_type_slug=str(entry_row['content_type_slug']),
            entry_slug=str(entry_row['slug']),
            payload=dict(entry_row['payload'] or {}),
            field_definitions=field_definitions,
            published_at=entry_row['published_at'],
            updated_at=entry_row['updated_at'],
        )
        upsert_search_document(
            connection,
            entry_id=document['entry_id'],
            content_type_id=document['content_type_id'],
            content_type_slug=document['content_type_slug'],
            entry_slug=document['entry_slug'],
            title_text=document['title_text'],
            body_text=document['body_text'],
            search_text_normalized=document['search_text_normalized'],
            searchable_field_names=document['searchable_field_names'],
            published_at=document['published_at'],
            updated_at=document['updated_at'],
            clear_embedding=clear_embedding,
        )
