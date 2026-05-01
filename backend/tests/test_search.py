# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
'''Backend integration tests for Pragma search.

Args:
    None.

Returns:
    None.

Raises:
    None.
'''

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from pragma.app import create_app
from pragma.config import clear_settings_cache
from pragma.errors import SearchError
from pragma.search.models import SearchMode, SearchQueryParams
from pragma.search.service import search_public_entries
from tests.helpers import BACKEND_ROOT, build_database_dsn


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    '''Bootstrap the first administrator account for a test app.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        AssertionError: If bootstrap fails unexpectedly.
    '''

    response = client.post('/api/v1/install/bootstrap', json=bootstrap_payload)
    assert response.status_code == 201


def _auth_headers(client: TestClient, bootstrap_payload: dict[str, str]) -> dict[str, str]:
    '''Log in the bootstrapped admin and return auth headers.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        dict[str, str]: Bearer authentication headers.

    Raises:
        AssertionError: If login fails unexpectedly.
    '''

    _bootstrap_admin(client, bootstrap_payload)
    response = client.post(
        '/api/v1/auth/login',
        json={
            'identity': bootstrap_payload['email'],
            'password': bootstrap_payload['password'],
        },
    )
    assert response.status_code == 200
    access_token = response.json()['access_token']
    return {'Authorization': f'Bearer {access_token}'}


def _content_type_payload(name: str = 'Blog Posts', slug: str = 'blog-posts') -> dict[str, object]:
    '''Return a reusable content-type payload for search tests.

    Args:
        name: Content-type name.
        slug: Content-type slug.

    Returns:
        dict[str, object]: Content-type payload.

    Raises:
        None.
    '''

    return {
        'name': name,
        'slug': slug,
        'field_definitions': [
            {
                'name': 'title',
                'label': 'Title',
                'kind': 'text',
                'required': True,
                'min_length': 1,
                'max_length': 200,
            },
            {
                'name': 'body',
                'label': 'Body',
                'kind': 'rich_text',
                'required': True,
                'min_length': 1,
            },
        ],
    }


def _create_content_type(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = 'Blog Posts',
    slug: str = 'blog-posts',
) -> dict[str, object]:
    '''Create a search-test content type and return the response payload.

    Args:
        client: FastAPI test client.
        headers: Authenticated request headers.
        name: Content-type name.
        slug: Content-type slug.

    Returns:
        dict[str, object]: Serialized content-type response.

    Raises:
        AssertionError: If content-type creation fails unexpectedly.
    '''

    response = client.post(
        '/api/v1/content/types',
        headers=headers,
        json=_content_type_payload(name=name, slug=slug),
    )
    assert response.status_code == 201
    return response.json()


def _create_entry(
    client: TestClient,
    headers: dict[str, str],
    content_type_id: str,
    *,
    title: str,
    body: str,
    status: str = 'published',
) -> dict[str, object]:
    '''Create a content entry for search tests.

    Args:
        client: FastAPI test client.
        headers: Authenticated request headers.
        content_type_id: Owning content-type identifier.
        title: Entry title.
        body: Entry rich-text body.
        status: Requested content status.

    Returns:
        dict[str, object]: Serialized content-entry response.

    Raises:
        AssertionError: If entry creation fails unexpectedly.
    '''

    response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type_id,
            'status': status,
            'payload': {'title': title, 'body': body},
        },
    )
    assert response.status_code == 201
    return response.json()


def _vector_literal(values: list[float]) -> str:
    '''Build a pgvector literal string for test seeding.

    Args:
        values: Vector values.

    Returns:
        str: pgvector literal string.

    Raises:
        None.
    '''

    return '[' + ','.join(format(value, 'g') for value in values) + ']'


def _seed_search_embedding(
    env_values: dict[str, str], entry_id: str, embedding: list[float]
) -> None:
    '''Update the derived search document embedding for a test entry.

    Args:
        env_values: Runtime database environment values.
        entry_id: Search-document entry identifier.
        embedding: Vector values to persist.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL cannot update the search document.
    '''

    database_dsn = build_database_dsn(env_values, env_values['PRAGMA_DATABASE_NAME'])
    with psycopg.connect(database_dsn) as connection, connection.transaction():
        connection.execute(
            '''
            UPDATE pragma_search_documents
            SET embedding = %s::vector
            WHERE entry_id = %s
            ''',
            (_vector_literal(embedding), entry_id),
        )


@contextmanager
def _search_client(
    apply_runtime_env: Callable[[dict[str, str]], None],
    env_values: dict[str, str],
    *,
    search_enable_semantic: bool = False,
) -> Iterator[TestClient]:
    '''Create a test client with optional semantic-search enablement.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        env_values: Runtime database environment values.
        search_enable_semantic: Whether semantic search should be enabled.

    Returns:
        Iterator[TestClient]: Active FastAPI test client.

    Raises:
        None.
    '''

    runtime_values = dict(env_values)
    runtime_values['PRAGMA_SEARCH_ENABLE_SEMANTIC'] = (
        'true' if search_enable_semantic else 'false'
    )
    apply_runtime_env(runtime_values)
    with TestClient(create_app()) as client:
        yield client


def _run_migrations_to(revision: str) -> None:
    '''Apply Alembic migrations to a specific revision for migration tests.

    Args:
        revision: Alembic revision target.

    Returns:
        None.

    Raises:
        CommandError: If Alembic cannot apply the migration chain.
    '''

    clear_settings_cache()
    config = Config(str(BACKEND_ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND_ROOT / 'alembic'))
    command.upgrade(config, revision)


def test_search_migration_creates_schema(migrated_database: dict[str, str]) -> None:
    '''Verify the M8 migration creates the search schema and indexes.

    Args:
        migrated_database: Environment values for the migrated test database.

    Returns:
        None.

    Raises:
        None.
    '''

    database_dsn = build_database_dsn(
        migrated_database, migrated_database['PRAGMA_DATABASE_NAME']
    )
    with psycopg.connect(database_dsn) as connection:
        row = connection.execute(
            '''
            SELECT
                to_regclass('public.pragma_search_documents') AS search_documents_table,
                to_regclass('public.ix_pragma_search_documents_published_at')
                    AS published_at_index,
                to_regclass('public.ix_pragma_search_documents_content_type_slug_published_at')
                    AS content_type_published_index,
                to_regclass('public.ix_pragma_search_documents_search_tsv') AS search_tsv_index,
                to_regclass('public.ix_pragma_search_documents_search_text_trgm')
                    AS search_trgm_index,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'pragma_search_documents'
                      AND column_name = 'embedding'
                ) AS has_embedding
            '''
        ).fetchone()

    assert row[0] == 'pragma_search_documents'
    assert row[1] == 'ix_pragma_search_documents_published_at'
    assert row[2] == 'ix_pragma_search_documents_content_type_slug_published_at'
    assert row[3] == 'ix_pragma_search_documents_search_tsv'
    assert row[4] == 'ix_pragma_search_documents_search_text_trgm'
    assert row[5] is True


def test_search_migration_backfill_matches_runtime_field_order(
    runtime_database: dict[str, str]
) -> None:
    '''Verify M8 upgrade backfill matches runtime field-order semantics.

    Args:
        runtime_database: Environment values for an unmigrated test database.

    Returns:
        None.

    Raises:
        None.
    '''

    _run_migrations_to('20260421_0003')
    database_dsn = build_database_dsn(
        runtime_database, runtime_database['PRAGMA_DATABASE_NAME']
    )
    content_type_id = uuid4()
    first_entry_id = uuid4()
    preferred_entry_id = uuid4()
    timestamp = datetime.now(UTC)
    long_first_value = 'Z' * 180

    with psycopg.connect(database_dsn) as connection, connection.transaction():
        connection.execute(
            '''
            INSERT INTO pragma_content_types (
                id, name, slug, description, created_at, updated_at
            )
            VALUES (%s, 'Search Backfill', 'search-backfill', NULL, %s, %s)
            ''',
            (content_type_id, timestamp, timestamp),
        )
        for position, name in enumerate(('summary', 'body', 'title', 'name')):
            connection.execute(
                '''
                INSERT INTO pragma_content_fields (
                    id, content_type_id, name, label, field_type, is_required,
                    position, config, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, 'text', false, %s, '{}'::jsonb, %s, %s)
                ''',
                (
                    uuid4(),
                    content_type_id,
                    name,
                    name.title(),
                    position,
                    timestamp,
                    timestamp,
                ),
            )
        connection.execute(
            '''
            INSERT INTO pragma_content_entries (
                id, content_type_id, slug, status, payload, published_at,
                created_at, updated_at
            )
            VALUES (%s, %s, 'first-field', 'published', %s::jsonb, %s, %s, %s)
            ''',
            (
                first_entry_id,
                content_type_id,
                json.dumps({'summary': long_first_value, 'body': 'Alpha Later'}),
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            '''
            INSERT INTO pragma_content_entries (
                id, content_type_id, slug, status, payload, published_at,
                created_at, updated_at
            )
            VALUES (%s, %s, 'preferred-fields', 'published', %s::jsonb, %s, %s, %s)
            ''',
            (
                preferred_entry_id,
                content_type_id,
                json.dumps({'title': 'Zulu Title', 'name': 'Alpha Name'}),
                timestamp,
                timestamp,
                timestamp,
            ),
        )

    _run_migrations_to('head')

    with psycopg.connect(database_dsn) as connection:
        rows = connection.execute(
            '''
            SELECT entry_id, title_text, body_text, searchable_field_names
            FROM pragma_search_documents
            WHERE entry_id IN (%s, %s)
            ORDER BY entry_slug
            ''',
            (first_entry_id, preferred_entry_id),
        ).fetchall()

    documents = {str(row[0]): row for row in rows}
    first_document = documents[str(first_entry_id)]
    preferred_document = documents[str(preferred_entry_id)]
    assert first_document[1] == long_first_value[:160]
    assert first_document[2] == f'{long_first_value} Alpha Later'
    assert first_document[3] == ['summary', 'body']
    assert preferred_document[1] == 'Zulu Title'
    assert preferred_document[2] == 'Zulu Title'
    assert preferred_document[3] == ['title', 'name']


def test_search_returns_only_published_entries(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify public search excludes draft and archived content.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(apply_runtime_env, migrated_database) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        published_entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Nebula Update',
            body='<p>Visible nebula content</p>',
        )
        _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Nebula Draft',
            body='<p>Draft nebula content</p>',
            status='draft',
        )
        archived_entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Nebula Archive',
            body='<p>Archived nebula content</p>',
        )
        archive_response = client.put(
            f"/api/v1/content/entries/{archived_entry['id']}",
            headers=headers,
            json={
                'status': 'archived',
                'payload': {
                    'title': 'Nebula Archive',
                    'body': '<p>Archived nebula content</p>',
                },
            },
        )
        assert archive_response.status_code == 200

        response = client.get('/api/v1/search/entries', params={'query': 'nebula'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'hybrid'
    assert payload['applied_strategies'] == ['keyword', 'fuzzy']
    assert payload['total'] == 1
    assert [item['id'] for item in payload['items']] == [published_entry['id']]


def test_search_rich_text_excerpt_strips_markup(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify rich-text matches return plain-text excerpts.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(apply_runtime_env, migrated_database) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Markup Story',
            body='<p>Hello <strong>World</strong> and <em>friends</em>.</p>',
        )

        response = client.get('/api/v1/search/entries', params={'query': 'world'})

    assert response.status_code == 200
    excerpt = response.json()['items'][0]['excerpt']
    assert 'Hello World and friends.' in excerpt
    assert '<' not in excerpt


def test_search_fuzzy_mode_works_when_pg_trgm_available(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify fuzzy mode uses trigram similarity when available.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(apply_runtime_env, migrated_database) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Hello World',
            body='<p>Fuzzy greeting body</p>',
        )

        response = client.get(
            '/api/v1/search/entries',
            params={'query': 'helo world', 'mode': 'fuzzy'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_requested'] == 'fuzzy'
    assert payload['mode_applied'] == 'fuzzy'
    assert payload['applied_strategies'] == ['fuzzy']
    assert payload['items'][0]['id'] == entry['id']


def test_search_vector_mode_works_when_available(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify vector mode ranks by embedding similarity when enabled.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(
        apply_runtime_env, migrated_database, search_enable_semantic=True
    ) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        alpha = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Vector Alpha',
            body='<p>Alpha vector body</p>',
        )
        beta = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Vector Beta',
            body='<p>Beta vector body</p>',
        )
        _seed_search_embedding(migrated_database, alpha['id'], [1.0, 0.0, 0.0])
        _seed_search_embedding(migrated_database, beta['id'], [0.0, 1.0, 0.0])

        response = client.get(
            '/api/v1/search/entries',
            params={
                'query': 'vector',
                'mode': 'vector',
                'query_embedding': [1.0, 0.0, 0.0],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'vector'
    assert payload['applied_strategies'] == ['vector']
    assert [item['id'] for item in payload['items']] == [alpha['id'], beta['id']]


def test_search_vector_mode_surfaces_mismatched_embedding_dimensions(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify vector mode diagnoses stored embeddings with incompatible dimensions.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(
        apply_runtime_env, migrated_database, search_enable_semantic=True
    ) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        compatible = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Vector Compatible',
            body='<p>Compatible vector body</p>',
        )
        mismatched = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Vector Mismatched',
            body='<p>Mismatched vector body</p>',
        )
        _seed_search_embedding(migrated_database, compatible['id'], [1.0, 0.0, 0.0])
        _seed_search_embedding(migrated_database, mismatched['id'], [1.0, 0.0])

        response = client.get(
            '/api/v1/search/entries',
            params={
                'query': 'vector',
                'mode': 'vector',
                'query_embedding': [1.0, 0.0, 0.0],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'vector'
    assert payload['applied_strategies'] == ['vector']
    assert payload['total'] == 1
    assert [item['id'] for item in payload['items']] == [compatible['id']]
    assert payload['semantic_diagnostics'] == [
        '1 search document embedding(s) require rebuild for the active semantic contract'
    ]


def test_search_hybrid_mode_merges_available_strategies(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify hybrid mode merges keyword, fuzzy, and vector candidates.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(
        apply_runtime_env, migrated_database, search_enable_semantic=True
    ) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        exact_match = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Exact Hybrid Match',
            body='<p>Hybrid keyword winner</p>',
        )
        semantic_match = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Semantic Candidate',
            body='<p>Hybrid semantic candidate</p>',
        )
        _seed_search_embedding(migrated_database, exact_match['id'], [0.0, 1.0, 0.0])
        _seed_search_embedding(migrated_database, semantic_match['id'], [1.0, 0.0, 0.0])

        response = client.get(
            '/api/v1/search/entries',
            params={
                'query': 'exact hybrid match',
                'mode': 'hybrid',
                'query_embedding': [1.0, 0.0, 0.0],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'hybrid'
    assert payload['applied_strategies'] == ['keyword', 'fuzzy', 'vector']
    assert payload['total'] == 2
    assert payload['items'][0]['id'] == exact_match['id']
    assert {item['id'] for item in payload['items']} == {
        exact_match['id'],
        semantic_match['id'],
    }


def test_search_auto_embedding_does_not_hold_storage_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    '''Verify provider I/O runs outside active search storage connections.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    '''

    import pragma.ai.service as ai_service
    import pragma.search.service as search_service

    result_id = uuid4()
    provider_connection_counts: list[int] = []
    search_connection_counts: list[int] = []

    class _GuardedStorage:
        def __init__(self) -> None:
            self.active_connections = 0
            self.scope_count = 0

        @contextmanager
        def connection(self) -> Iterator[object]:
            self.scope_count += 1
            self.active_connections += 1
            try:
                yield object()
            finally:
                self.active_connections -= 1

    class _SearchSettings:
        search_enable_semantic = True

    storage = _GuardedStorage()

    def _mock_get_extension_capabilities(
        _connection: object,
    ) -> dict[str, dict[str, bool]]:
        return {
            'pgvector': {'installed': True},
            'pg_trgm': {'installed': True},
        }

    def _mock_get_ai_provider_settings(_connection: object) -> dict[str, object]:
        return {
            'enabled': True,
            'provider': 'voyage',
            'base_url': 'https://api.voyageai.com/v1',
            'api_key': 'test-ai-key',
            'embedding_model': 'voyage-3.5-lite',
            'request_timeout_seconds': 5,
        }

    def _mock_request_embedding(
        _config: object,
        text: str,
        *,
        input_type: str,
    ) -> list[float]:
        provider_connection_counts.append(storage.active_connections)
        assert text == 'semantic guard'
        assert input_type == 'query'
        return [1.0, 0.0]

    def _mock_search_documents(
        _connection: object,
        *,
        query: str,
        normalized_query: str,
        limit: int,
        offset: int,
        content_type_slug: str | None,
        strategies: list[str],
        query_embedding: str | None = None,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
    ) -> list[dict[str, object]]:
        search_connection_counts.append(storage.active_connections)
        assert query == 'semantic guard'
        assert normalized_query == 'semantic guard'
        assert limit == 20
        assert offset == 0
        assert content_type_slug is None
        assert strategies == ['vector']
        assert query_embedding == '[1,0]'
        assert embedding_provider == 'voyage'
        assert embedding_model == 'voyage-3.5-lite'
        return [
            {
                'id': result_id,
                'content_type_slug': 'articles',
                'slug': 'semantic-guard',
                'title': 'Semantic Guard',
                'body_text': 'Semantic provider pool guard',
                'published_at': datetime.now(UTC),
                'total_count': 1,
            }
        ]

    monkeypatch.setattr(
        search_service, 'get_extension_capabilities', _mock_get_extension_capabilities
    )
    monkeypatch.setattr(search_service, 'search_embedding_column_exists', lambda _: True)
    monkeypatch.setattr(
        search_service, 'count_search_embedding_contract_mismatches', lambda *_args, **_kwargs: 0
    )
    monkeypatch.setattr(ai_service, 'get_ai_provider_settings', _mock_get_ai_provider_settings)
    monkeypatch.setattr(ai_service, 'request_embedding', _mock_request_embedding)
    monkeypatch.setattr(search_service, 'search_documents', _mock_search_documents)

    params = SearchQueryParams.model_construct(
        query='semantic guard',
        limit=20,
        offset=0,
        content_type_slug=None,
        mode=SearchMode.VECTOR,
        query_embedding=None,
    )

    response = search_public_entries(storage, _SearchSettings(), params)

    assert provider_connection_counts == [0]
    assert search_connection_counts == [1]
    assert storage.scope_count == 2
    assert storage.active_connections == 0
    assert response.mode_applied == SearchMode.VECTOR
    assert response.applied_strategies == ['vector']
    assert [item.id for item in response.items] == [result_id]


def test_search_degrades_cleanly_without_pg_trgm(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database_without_pg_trgm: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify fuzzy requests degrade to keyword search without pg_trgm.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database_without_pg_trgm: Migrated test DB without ``pg_trgm``.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(apply_runtime_env, migrated_database_without_pg_trgm) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Fallback Keyword Result',
            body='<p>Keyword survives fuzzy degradation</p>',
        )

        response = client.get(
            '/api/v1/search/entries',
            params={'query': 'keyword', 'mode': 'fuzzy'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'keyword'
    assert payload['applied_strategies'] == ['keyword']
    assert payload['items'][0]['id'] == entry['id']


def test_search_degrades_cleanly_without_pgvector(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database_without_pgvector: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify vector requests degrade to keyword search without pgvector.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database_without_pgvector: Migrated test DB without ``pgvector``.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(
        apply_runtime_env, migrated_database_without_pgvector, search_enable_semantic=True
    ) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Vector Fallback Result',
            body='<p>Keyword survives vector degradation</p>',
        )

        response = client.get(
            '/api/v1/search/entries',
            params={
                'query': 'vector fallback',
                'mode': 'vector',
                'query_embedding': [1.0, 0.0, 0.0],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'keyword'
    assert payload['applied_strategies'] == ['keyword']
    assert payload['items'][0]['id'] == entry['id']


def test_search_degrades_to_keyword_only_without_optional_extensions(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database_without_search_extensions: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify auto mode falls back to keyword search without optional extensions.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database_without_search_extensions: Migrated test DB without search extensions.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(apply_runtime_env, migrated_database_without_search_extensions) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Keyword Only Result',
            body='<p>No optional extension support</p>',
        )

        response = client.get('/api/v1/search/entries', params={'query': 'keyword'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'keyword'
    assert payload['applied_strategies'] == ['keyword']
    assert payload['items'][0]['id'] == entry['id']


def test_search_write_path_refreshes_documents(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify create, update, archive, and delete keep search state in sync.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(apply_runtime_env, migrated_database) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Original Search Title',
            body='<p>Original body</p>',
        )

        initial_response = client.get(
            '/api/v1/search/entries', params={'query': 'original search'}
        )
        assert initial_response.status_code == 200
        assert initial_response.json()['total'] == 1

        update_response = client.put(
            f"/api/v1/content/entries/{entry['id']}",
            headers=headers,
            json={
                'status': 'published',
                'payload': {
                    'title': 'Updated Search Title',
                    'body': '<p>Updated body</p>',
                },
            },
        )
        assert update_response.status_code == 200

        old_search = client.get('/api/v1/search/entries', params={'query': 'original'})
        new_search = client.get('/api/v1/search/entries', params={'query': 'updated'})
        assert old_search.status_code == 200
        assert old_search.json()['total'] == 0
        assert new_search.status_code == 200
        assert new_search.json()['total'] == 1

        archive_response = client.put(
            f"/api/v1/content/entries/{entry['id']}",
            headers=headers,
            json={
                'status': 'archived',
                'payload': {
                    'title': 'Updated Search Title',
                    'body': '<p>Updated body</p>',
                },
            },
        )
        assert archive_response.status_code == 200

        archived_search = client.get('/api/v1/search/entries', params={'query': 'updated'})
        assert archived_search.status_code == 200
        assert archived_search.json()['total'] == 0

        delete_response = client.delete(
            f"/api/v1/content/entries/{entry['id']}",
            headers=headers,
        )
        assert delete_response.status_code == 204

        final_search = client.get('/api/v1/search/entries', params={'query': 'updated'})

    assert final_search.status_code == 200
    assert final_search.json()['total'] == 0


def test_search_content_type_update_rebuilds_documents(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify content-type updates rebuild derived search documents.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(apply_runtime_env, migrated_database) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Slug Rebuild Story',
            body='<p>Content-type rebuild body</p>',
        )

        old_filter = client.get(
            '/api/v1/search/entries',
            params={'query': 'slug rebuild', 'content_type_slug': 'blog-posts'},
        )
        assert old_filter.status_code == 200
        assert old_filter.json()['total'] == 1

        update_response = client.put(
            f"/api/v1/content/types/{content_type['id']}",
            headers=headers,
            json=_content_type_payload(name='Blog Posts', slug='news-posts'),
        )
        assert update_response.status_code == 200

        missing_old_filter = client.get(
            '/api/v1/search/entries',
            params={'query': 'slug rebuild', 'content_type_slug': 'blog-posts'},
        )
        new_filter = client.get(
            '/api/v1/search/entries',
            params={'query': 'slug rebuild', 'content_type_slug': 'news-posts'},
        )

    assert missing_old_filter.status_code == 200
    assert missing_old_filter.json()['total'] == 0
    assert new_filter.status_code == 200
    assert new_filter.json()['total'] == 1


def test_search_openapi_documents_structured_error_responses(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
) -> None:
    '''Verify search endpoints publish structured error schemas in OpenAPI.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(apply_runtime_env, migrated_database) as client:
        response = client.get('/openapi.json')

    assert response.status_code == 200
    schema = response.json()
    search_responses = schema['paths']['/api/v1/search/entries']['get']['responses']
    error_schema = search_responses['400']['content']['application/json']['schema']
    assert set(error_schema['required']) == {'detail', 'code'}
    assert set(error_schema['properties']) == {'detail', 'code'}
    assert '422' in search_responses
    assert '503' in search_responses


def test_search_service_rejects_blank_queries() -> None:
    '''Verify service-level blank-query protection returns a search-domain error.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    '''

    params = SearchQueryParams.model_construct(
        query='   ',
        limit=20,
        offset=0,
        content_type_slug=None,
        mode=SearchMode.AUTO,
        query_embedding=None,
    )

    with pytest.raises(SearchError) as exc_info:
        search_public_entries(None, None, params)

    assert exc_info.value.code == 'SEARCH_QUERY_INVALID'
    assert exc_info.value.detail == 'Search query must not be blank'


def test_search_route_returns_validation_error_for_invalid_params(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
) -> None:
    '''Verify invalid public-search parameters return structured validation errors.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(apply_runtime_env, migrated_database) as client:
        response = client.get(
            '/api/v1/search/entries',
            params={'query': 'valid', 'limit': 0},
        )

    assert response.status_code == 422
    assert response.json() == {
        'detail': 'Request validation failed',
        'code': 'VALIDATION_ERROR',
    }


def test_search_route_returns_structured_error_for_query_failures(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    '''Verify backend search failures return the documented structured 503 error.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    '''

    with _search_client(apply_runtime_env, migrated_database) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)
        _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Failure Branch',
            body='<p>Failure branch body</p>',
        )
        database_dsn = build_database_dsn(
            migrated_database, migrated_database['PRAGMA_DATABASE_NAME']
        )
        with psycopg.connect(database_dsn) as connection, connection.transaction():
            connection.execute('DROP TABLE pragma_search_documents')

        response = client.get(
            '/api/v1/search/entries',
            params={'query': 'failure branch'},
        )

    assert response.status_code == 503
    assert response.json() == {
        'detail': 'Unable to execute search query',
        'code': 'SEARCH_QUERY_FAILED',
    }
