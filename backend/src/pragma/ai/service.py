# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Service logic for AI-provider settings and embedding workflows.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Mapping
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from psycopg import Connection
from psycopg import Error as PsycopgError

from pragma.ai.models import (
    AIProvider,
    AIProviderSettingsResponse,
    AIProviderSettingsUpdateRequest,
    AIProviderTestRequest,
    AIProviderTestResponse,
    AISearchEmbeddingRebuildRequest,
    AISearchEmbeddingRebuildResponse,
)
from pragma.ai.providers import EmbeddingProviderConfig, request_embedding
from pragma.errors import AuthError, ConfigError, SearchError, StorageError
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.ai import get_ai_provider_settings, upsert_ai_provider_settings
from pragma.storage.queries.capabilities import get_extension_capabilities
from pragma.storage.queries.search import (
    list_search_documents_for_embedding_rebuild,
    search_embedding_column_exists,
    update_search_document_embedding,
)

_MULTI_HYPHEN_PATTERN = re.compile(r'-{2,}')


def _require_user_id(current_user: Mapping[str, object]) -> UUID:
    """Return a validated UUID for the authenticated user context.

    Args:
        current_user: Authenticated user dictionary.

    Returns:
        UUID: User identifier.

    Raises:
        AuthError: If the user context does not expose a valid identifier.
    """

    raw_value = current_user.get('id')
    if isinstance(raw_value, UUID):
        return raw_value
    if isinstance(raw_value, str):
        try:
            return UUID(raw_value)
        except ValueError as exc:
            raise AuthError(
                detail='Authenticated user identifier is invalid',
                code='AUTH_USER_INVALID',
            ) from exc
    raise AuthError(detail='Authenticated user identifier is missing', code='AUTH_USER_INVALID')


def _normalize_content_type_slug(value: str) -> str:
    """Normalize a content-type slug used by embedding rebuild filters.

    Args:
        value: Raw content-type slug filter.

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


def _provider_config_from_row(
    settings_row: dict[str, object] | None,
    *,
    require_enabled: bool,
) -> EmbeddingProviderConfig | None:
    """Build provider runtime configuration from the persisted settings row.

    Args:
        settings_row: Persisted singleton settings row.
        require_enabled: Whether disabled configuration should raise.

    Returns:
        EmbeddingProviderConfig | None: Provider config when enabled and valid.

    Raises:
        ConfigError: If enabled settings are incomplete or invalid.
    """

    if settings_row is None or not bool(settings_row['enabled']):
        if require_enabled:
            raise ConfigError(
                detail='AI provider is disabled',
                code='AI_SETTINGS_DISABLED',
                status_code=HTTPStatus.BAD_REQUEST,
            )
        return None

    provider_value = str(settings_row['provider'] or '').strip()
    base_url = str(settings_row['base_url'] or '').strip()
    api_key = str(settings_row['api_key'] or '').strip()
    embedding_model = str(settings_row['embedding_model'] or '').strip()
    timeout_value = settings_row['request_timeout_seconds']

    if not provider_value or not base_url or not api_key or not embedding_model:
        raise ConfigError(
            detail='AI provider settings are incomplete',
            code='AI_SETTINGS_INVALID',
            status_code=HTTPStatus.BAD_REQUEST,
        )

    try:
        provider = AIProvider(provider_value)
    except ValueError as exc:
        raise ConfigError(
            detail='AI provider setting is invalid',
            code='AI_SETTINGS_INVALID',
            status_code=HTTPStatus.BAD_REQUEST,
        ) from exc

    timeout_seconds = int(timeout_value) if timeout_value is not None else 15
    if timeout_seconds < 1:
        raise ConfigError(
            detail='AI provider timeout must be at least one second',
            code='AI_SETTINGS_INVALID',
            status_code=HTTPStatus.BAD_REQUEST,
        )

    return EmbeddingProviderConfig(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        embedding_model=embedding_model,
        request_timeout_seconds=timeout_seconds,
    )


def _vector_literal(values: list[float]) -> str:
    """Build a pgvector literal from Python float values.

    Args:
        values: Embedding vector values.

    Returns:
        str: pgvector literal string.

    Raises:
        None.
    """

    return '[' + ','.join(format(value, 'g') for value in values) + ']'


def _embedding_source_text(title_text: str, body_text: str) -> str:
    """Build embedding-source text for one search document.

    Args:
        title_text: Derived search-document title text.
        body_text: Derived search-document body text.

    Returns:
        str: Normalized source text for provider embedding requests.

    Raises:
        None.
    """

    return re.sub(r'\s+', ' ', f'{title_text} {body_text}').strip()


def get_ai_provider_settings_snapshot(storage: DatabasePool) -> AIProviderSettingsResponse:
    """Return the current AI-provider settings snapshot.

    Args:
        storage: Initialized database pool manager.

    Returns:
        AIProviderSettingsResponse: Serialized provider settings snapshot.

    Raises:
        StorageError: If PostgreSQL access fails.
        ConfigError: If persisted provider values are invalid.
    """

    try:
        with storage.connection() as connection:
            row = get_ai_provider_settings(connection)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load AI provider settings',
            code='AI_SETTINGS_LOAD_FAILED',
        ) from exc

    try:
        return AIProviderSettingsResponse.from_record(row)
    except ValueError as exc:
        raise ConfigError(
            detail='Stored AI provider settings are invalid',
            code='AI_SETTINGS_INVALID',
            status_code=HTTPStatus.BAD_REQUEST,
        ) from exc


def update_ai_provider_settings_snapshot(
    storage: DatabasePool,
    payload: AIProviderSettingsUpdateRequest,
    current_user: Mapping[str, object],
) -> AIProviderSettingsResponse:
    """Persist updated AI-provider settings and return the new snapshot.

    Args:
        storage: Initialized database pool manager.
        payload: Provider settings update payload.
        current_user: Authenticated user context.

    Returns:
        AIProviderSettingsResponse: Updated provider settings snapshot.

    Raises:
        ConfigError: If the requested settings are invalid.
        StorageError: If PostgreSQL access fails.
        AuthError: If the authenticated user context is invalid.
    """

    timestamp = datetime.now(UTC)
    user_id = _require_user_id(current_user)

    try:
        with storage.connection() as connection, connection.transaction():
            existing_row = get_ai_provider_settings(connection)
            api_key = payload.api_key.strip() if payload.api_key is not None else None
            if (
                api_key is None
                and payload.retain_existing_api_key
                and existing_row is not None
                and existing_row['api_key'] is not None
            ):
                api_key = str(existing_row['api_key'])

            if payload.enabled and not api_key:
                raise ConfigError(
                    detail='Enabled AI provider settings require an API key',
                    code='AI_SETTINGS_API_KEY_REQUIRED',
                    status_code=HTTPStatus.BAD_REQUEST,
                )

            row = upsert_ai_provider_settings(
                connection,
                enabled=payload.enabled,
                provider=payload.provider.value,
                base_url=payload.base_url,
                api_key=api_key,
                embedding_model=payload.embedding_model,
                request_timeout_seconds=payload.request_timeout_seconds,
                updated_by_user_id=user_id,
                updated_at=timestamp,
            )
            if search_embedding_column_exists(connection):
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
    except ConfigError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to update AI provider settings',
            code='AI_SETTINGS_UPDATE_FAILED',
        ) from exc

    return AIProviderSettingsResponse.from_record(row)


def generate_query_embedding_for_search(
    connection: Connection,
    *,
    query: str,
) -> list[float] | None:
    """Generate a query embedding for vector/hybrid search execution.

    Args:
        connection: Open PostgreSQL connection.
        query: Normalized search-query text.

    Returns:
        list[float] | None: Embedding values when provider settings are enabled.

    Raises:
        ConfigError: If enabled provider settings are invalid.
        SearchError: If the provider request fails.
    """

    settings_row = get_ai_provider_settings(connection)
    provider_config = _provider_config_from_row(settings_row, require_enabled=False)
    if provider_config is None:
        return None
    return request_embedding(provider_config, query, input_type='query')


def test_ai_provider_connection(
    storage: DatabasePool, payload: AIProviderTestRequest
) -> AIProviderTestResponse:
    """Validate provider reachability with the currently persisted settings.

    Args:
        storage: Initialized database pool manager.
        payload: Connectivity-test payload.

    Returns:
        AIProviderTestResponse: Provider test result payload.

    Raises:
        ConfigError: If provider settings are disabled or invalid.
        SearchError: If provider request fails.
        StorageError: If PostgreSQL access fails.
    """

    try:
        with storage.connection() as connection:
            settings_row = get_ai_provider_settings(connection)
            provider_config = _provider_config_from_row(settings_row, require_enabled=True)
            embedding = request_embedding(
                provider_config, payload.query_text, input_type='query'
            )
    except ConfigError:
        raise
    except SearchError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to test AI provider settings',
            code='AI_SETTINGS_TEST_FAILED',
        ) from exc

    return AIProviderTestResponse(
        provider=provider_config.provider,
        embedding_model=provider_config.embedding_model,
        embedding_dimensions=len(embedding),
    )


def rebuild_search_embeddings(
    storage: DatabasePool,
    payload: AISearchEmbeddingRebuildRequest,
) -> AISearchEmbeddingRebuildResponse:
    """Rebuild stored search embeddings using the configured provider.

    Args:
        storage: Initialized database pool manager.
        payload: Rebuild request payload.

    Returns:
        AISearchEmbeddingRebuildResponse: Rebuild result payload.

    Raises:
        ConfigError: If provider settings are disabled or invalid.
        SearchError: If semantic embeddings are unavailable in storage.
        StorageError: If PostgreSQL access fails.
    """

    attempted = 0
    embedded = 0
    failed = 0
    failed_entry_ids: list[str] = []

    try:
        with storage.connection() as connection, connection.transaction():
            capabilities = get_extension_capabilities(connection)
            if not capabilities['pgvector']['installed'] or not search_embedding_column_exists(
                connection
            ):
                raise SearchError(
                    detail='Semantic embeddings are unavailable for this database',
                    code='SEARCH_EMBEDDING_UNAVAILABLE',
                    status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                )

            settings_row = get_ai_provider_settings(connection)
            provider_config = _provider_config_from_row(settings_row, require_enabled=True)
            remaining = payload.max_documents
            offset = 0
            content_type_slug = (
                _normalize_content_type_slug(payload.content_type_slug)
                if payload.content_type_slug is not None
                else None
            )

            while remaining > 0:
                batch_limit = min(payload.batch_size, remaining)
                rows = list_search_documents_for_embedding_rebuild(
                    connection,
                    provider=provider_config.provider.value,
                    embedding_model=provider_config.embedding_model,
                    content_type_slug=content_type_slug,
                    limit=batch_limit,
                    offset=offset if payload.force else 0,
                    stale_only=not payload.force,
                )
                if not rows:
                    break
                if payload.force:
                    offset += len(rows)

                for row in rows:
                    attempted += 1
                    remaining -= 1
                    source_text = _embedding_source_text(
                        str(row['title_text']),
                        str(row['body_text']),
                    )
                    try:
                        embedding = request_embedding(
                            provider_config,
                            source_text,
                            input_type='document',
                        )
                        update_search_document_embedding(
                            connection,
                            entry_id=row['entry_id'],
                            embedding_literal=_vector_literal(embedding),
                            embedding_provider=provider_config.provider.value,
                            embedding_model=provider_config.embedding_model,
                            embedded_at=datetime.now(UTC),
                        )
                        embedded += 1
                    except SearchError as exc:
                        failed += 1
                        failed_entry_ids.append(str(row['entry_id']))
                        logging.getLogger(__name__).warning(
                            'Search embedding rebuild failed for entry',
                            extra={
                                'entry_id': str(row['entry_id']),
                                'search_code': exc.code,
                            },
                        )
    except ConfigError:
        raise
    except SearchError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to rebuild search embeddings',
            code='SEARCH_EMBEDDING_REBUILD_FAILED',
        ) from exc

    return AISearchEmbeddingRebuildResponse(
        attempted=attempted,
        embedded=embedded,
        failed=failed,
        failed_entry_ids=failed_entry_ids,
    )
