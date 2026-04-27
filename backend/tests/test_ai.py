# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Integration tests for M9 AI provider settings and embeddings.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import psycopg
import pytest
from fastapi.testclient import TestClient

from pragma.app import create_app
from pragma.errors import SearchError
from tests.helpers import build_database_dsn


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Bootstrap the first administrator account for AI integration tests.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        AssertionError: If bootstrap fails unexpectedly.
    """

    response = client.post('/api/v1/install/bootstrap', json=bootstrap_payload)
    assert response.status_code == 201


def _auth_headers(client: TestClient, bootstrap_payload: dict[str, str]) -> dict[str, str]:
    """Log in the bootstrapped admin and return bearer-auth headers.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        dict[str, str]: Bearer authentication headers.

    Raises:
        AssertionError: If login fails unexpectedly.
    """

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


def _content_type_payload(
    name: str = 'AI Articles',
    slug: str = 'ai-articles',
) -> dict[str, object]:
    """Return a reusable content-type payload for AI integration tests.

    Args:
        name: Content-type name.
        slug: Content-type slug.

    Returns:
        dict[str, object]: Content-type payload.

    Raises:
        None.
    """

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


def _create_content_type(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    """Create a content type and return the serialized response payload.

    Args:
        client: FastAPI test client.
        headers: Authenticated request headers.

    Returns:
        dict[str, object]: Serialized content-type response.

    Raises:
        AssertionError: If content-type creation fails unexpectedly.
    """

    response = client.post(
        '/api/v1/content/types',
        headers=headers,
        json=_content_type_payload(),
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
) -> dict[str, object]:
    """Create a published content entry for AI integration tests.

    Args:
        client: FastAPI test client.
        headers: Authenticated request headers.
        content_type_id: Owning content-type identifier.
        title: Entry title.
        body: Entry rich-text body.

    Returns:
        dict[str, object]: Serialized content-entry response.

    Raises:
        AssertionError: If entry creation fails unexpectedly.
    """

    response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type_id,
            'status': 'published',
            'payload': {'title': title, 'body': body},
        },
    )
    assert response.status_code == 201
    return response.json()


def _update_ai_settings(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    """Persist a reusable AI provider configuration and return its response payload.

    Args:
        client: FastAPI test client.
        headers: Authenticated request headers.

    Returns:
        dict[str, object]: Serialized provider-settings response.

    Raises:
        AssertionError: If settings update fails unexpectedly.
    """

    response = client.put(
        '/api/v1/ai/settings',
        headers=headers,
        json={
            'enabled': True,
            'provider': 'voyage',
            'base_url': 'https://api.voyageai.com/v1',
            'embedding_model': 'voyage-3.5-lite',
            'request_timeout_seconds': 5,
            'api_key': 'test-ai-key',
        },
    )
    assert response.status_code == 200
    return response.json()


def _seed_search_embedding(
    env_values: dict[str, str],
    entry_id: str,
    embedding: list[float],
    *,
    provider: str,
    embedding_model: str,
) -> None:
    """Seed a stored search embedding and metadata directly for test setup.

    Args:
        env_values: Runtime database environment values.
        entry_id: Search-document entry identifier.
        embedding: Vector values to persist.
        provider: Stored provider metadata value.
        embedding_model: Stored embedding-model metadata value.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL cannot update the search document.
    """

    database_dsn = build_database_dsn(env_values, env_values['PRAGMA_DATABASE_NAME'])
    with psycopg.connect(database_dsn) as connection, connection.transaction():
        connection.execute(
            """
            UPDATE pragma_search_documents
            SET
                embedding = %s::vector,
                embedding_provider = %s,
                embedding_model = %s,
                embedding_updated_at = CURRENT_TIMESTAMP
            WHERE entry_id = %s
            """,
            (
                '[' + ','.join(format(value, 'g') for value in embedding) + ']',
                provider,
                embedding_model,
                entry_id,
            ),
        )


@contextmanager
def _ai_client(
    apply_runtime_env: Callable[[dict[str, str]], None],
    env_values: dict[str, str],
    *,
    search_enable_semantic: bool = True,
) -> Iterator[TestClient]:
    """Create a test client configured for AI and semantic-search flows.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        env_values: Runtime database environment values.
        search_enable_semantic: Whether semantic search should be enabled.

    Returns:
        Iterator[TestClient]: Active FastAPI test client.

    Raises:
        None.
    """

    runtime_values = dict(env_values)
    runtime_values['PRAGMA_SEARCH_ENABLE_SEMANTIC'] = (
        'true' if search_enable_semantic else 'false'
    )
    apply_runtime_env(runtime_values)
    with TestClient(create_app()) as client:
        yield client


def test_ai_migration_creates_provider_settings_and_embedding_metadata(
    migrated_database: dict[str, str]
) -> None:
    """Verify M9 migration creates provider settings and embedding metadata schema.

    Args:
        migrated_database: Environment values for the migrated test database.

    Returns:
        None.

    Raises:
        None.
    """

    database_dsn = build_database_dsn(
        migrated_database, migrated_database['PRAGMA_DATABASE_NAME']
    )
    with psycopg.connect(database_dsn) as connection:
        row = connection.execute(
            """
            SELECT
                to_regclass('public.pragma_ai_provider_settings') AS provider_settings_table,
                to_regclass('public.ix_pragma_search_documents_embedding_metadata')
                    AS embedding_metadata_index,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'pragma_search_documents'
                      AND column_name = 'embedding_provider'
                ) AS has_embedding_provider,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'pragma_search_documents'
                      AND column_name = 'embedding_model'
                ) AS has_embedding_model,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'pragma_search_documents'
                      AND column_name = 'embedding_updated_at'
                ) AS has_embedding_updated_at
            """
        ).fetchone()

    assert row[0] == 'pragma_ai_provider_settings'
    assert row[1] == 'ix_pragma_search_documents_embedding_metadata'
    assert row[2] is True
    assert row[3] is True
    assert row[4] is True


def test_request_embedding_translates_provider_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify low-level provider timeouts are exposed as search-domain failures.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.providers as ai_providers
    from pragma.ai.models import AIProvider
    from pragma.ai.providers import EmbeddingProviderConfig, request_embedding

    def _raise_timeout(*_args: object, **_kwargs: object) -> None:
        raise TimeoutError('provider timed out')

    monkeypatch.setattr(ai_providers.request, 'urlopen', _raise_timeout)

    with pytest.raises(SearchError) as exc_info:
        request_embedding(
            EmbeddingProviderConfig(
                provider=AIProvider.VOYAGE,
                base_url='https://api.voyageai.com/v1',
                api_key='test-ai-key',
                embedding_model='voyage-3.5-lite',
                request_timeout_seconds=1,
            ),
            'timeout query',
            input_type='query',
        )

    assert exc_info.value.code == 'SEARCH_EMBEDDING_PROVIDER_UNAVAILABLE'
    assert exc_info.value.status_code == 503


def test_ai_routes_require_authentication(client: TestClient) -> None:
    """Verify authenticated AI routes reject anonymous requests.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.get('/api/v1/ai/settings')

    assert response.status_code == 401
    assert response.json() == {
        'detail': 'Authentication required',
        'code': 'AUTH_REQUIRED',
    }


def test_ai_superuser_routes_require_superuser(
    client: TestClient,
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify write-oriented AI routes enforce superuser authorization.

    Args:
        client: FastAPI test client.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    database_dsn = build_database_dsn(
        migrated_database, migrated_database['PRAGMA_DATABASE_NAME']
    )
    with psycopg.connect(database_dsn) as connection, connection.transaction():
        connection.execute(
            """
            UPDATE pragma_users
            SET is_superuser = FALSE
            WHERE email = %s
            """,
            (bootstrap_payload['email'],),
        )

    response = client.put(
        '/api/v1/ai/settings',
        headers=headers,
        json={
            'enabled': True,
            'provider': 'voyage',
            'base_url': 'https://api.voyageai.com/v1',
            'embedding_model': 'voyage-3.5-lite',
            'request_timeout_seconds': 5,
            'api_key': 'test-ai-key',
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        'detail': 'Permission ai.settings.manage is required',
        'code': 'AUTH_PERMISSION_DENIED',
    }


def test_ai_settings_read_requires_superuser(
    client: TestClient,
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify AI settings reads enforce superuser authorization.

    Args:
        client: FastAPI test client.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    database_dsn = build_database_dsn(
        migrated_database, migrated_database['PRAGMA_DATABASE_NAME']
    )
    with psycopg.connect(database_dsn) as connection, connection.transaction():
        connection.execute(
            """
            UPDATE pragma_users
            SET is_superuser = FALSE
            WHERE email = %s
            """,
            (bootstrap_payload['email'],),
        )

    response = client.get('/api/v1/ai/settings', headers=headers)

    assert response.status_code == 403
    assert response.json() == {
        'detail': 'Permission ai.settings.manage is required',
        'code': 'AUTH_PERMISSION_DENIED',
    }


def test_ai_settings_round_trip_masks_api_key(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify AI settings persistence returns masked API-key state only.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    update_payload = _update_ai_settings(client, headers)

    response = client.get('/api/v1/ai/settings', headers=headers)

    assert update_payload['enabled'] is True
    assert update_payload['api_key_configured'] is True
    assert response.status_code == 200
    assert response.json()['provider'] == 'voyage'
    assert response.json()['api_key_configured'] is True
    assert 'api_key' not in response.json()


def test_disabled_ai_settings_can_clear_optional_provider_fields(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify disabled AI settings can persist without provider metadata.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)

    response = client.put(
        '/api/v1/ai/settings',
        headers=headers,
        json={
            'enabled': False,
            'provider': None,
            'base_url': None,
            'embedding_model': None,
            'request_timeout_seconds': 15,
            'retain_existing_api_key': False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        'enabled': False,
        'provider': None,
        'base_url': None,
        'embedding_model': None,
        'request_timeout_seconds': 15,
        'api_key_configured': False,
        'updated_at': response.json()['updated_at'],
    }


def test_ai_settings_test_uses_mocked_provider(
    client: TestClient,
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify provider connectivity tests succeed with mocked embeddings.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.service as ai_service

    headers = _auth_headers(client, bootstrap_payload)
    calls: list[tuple[str, str]] = []

    def _mock_request_embedding(config, text: str, *, input_type: str) -> list[float]:
        calls.append((config.provider.value, input_type))
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(ai_service, 'request_embedding', _mock_request_embedding)

    _update_ai_settings(client, headers)
    response = client.post(
        '/api/v1/ai/settings/test',
        headers=headers,
        json={'query_text': 'health check'},
    )

    assert response.status_code == 200
    assert response.json() == {
        'provider': 'voyage',
        'embedding_model': 'voyage-3.5-lite',
        'embedding_dimensions': 3,
    }
    assert calls == [('voyage', 'query')]


def test_search_auto_embedding_uses_provider_when_available(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify vector search can auto-generate a query embedding via the provider.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.service as ai_service

    def _mock_request_embedding(config, text: str, *, input_type: str) -> list[float]:
        return [1.0, 0.0]

    monkeypatch.setattr(ai_service, 'request_embedding', _mock_request_embedding)

    with _ai_client(apply_runtime_env, migrated_database, search_enable_semantic=True) as client:
        headers = _auth_headers(client, bootstrap_payload)
        _update_ai_settings(client, headers)
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
        _seed_search_embedding(
            migrated_database,
            alpha['id'],
            [1.0, 0.0],
            provider='voyage',
            embedding_model='voyage-3.5-lite',
        )
        _seed_search_embedding(
            migrated_database,
            beta['id'],
            [0.0, 1.0],
            provider='voyage',
            embedding_model='voyage-3.5-lite',
        )

        response = client.get(
            '/api/v1/search/entries',
            params={'query': 'vector', 'mode': 'vector'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'vector'
    assert payload['applied_strategies'] == ['vector']
    assert [item['id'] for item in payload['items']] == [alpha['id'], beta['id']]


def test_search_falls_back_to_keyword_when_auto_embedding_fails(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify provider failures never block baseline keyword search.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.service as ai_service

    def _failing_request_embedding(config, text: str, *, input_type: str) -> list[float]:
        raise SearchError(
            detail='Embedding provider is unavailable',
            code='SEARCH_EMBEDDING_PROVIDER_UNAVAILABLE',
            status_code=503,
        )

    monkeypatch.setattr(ai_service, 'request_embedding', _failing_request_embedding)

    with _ai_client(apply_runtime_env, migrated_database, search_enable_semantic=True) as client:
        headers = _auth_headers(client, bootstrap_payload)
        _update_ai_settings(client, headers)
        content_type = _create_content_type(client, headers)
        entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Fallback Search Result',
            body='<p>Keyword fallback should survive provider failures</p>',
        )

        response = client.get(
            '/api/v1/search/entries',
            params={'query': 'fallback search result', 'mode': 'vector'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'keyword'
    assert payload['applied_strategies'] == ['keyword']
    assert payload['items'][0]['id'] == entry['id']


def test_search_falls_back_to_keyword_when_stored_provider_url_is_invalid(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify malformed stored provider URLs never break public search fallback.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    with _ai_client(apply_runtime_env, migrated_database, search_enable_semantic=True) as client:
        headers = _auth_headers(client, bootstrap_payload)
        _update_ai_settings(client, headers)
        content_type = _create_content_type(client, headers)
        entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Stored Invalid URL Fallback',
            body='<p>Keyword fallback should survive malformed provider URLs</p>',
        )

        database_dsn = build_database_dsn(
            migrated_database, migrated_database['PRAGMA_DATABASE_NAME']
        )
        with psycopg.connect(database_dsn) as connection, connection.transaction():
            connection.execute(
                """
                UPDATE pragma_ai_provider_settings
                SET base_url = 'not-a-url'
                WHERE id = 1
                """
            )

        response = client.get(
            '/api/v1/search/entries',
            params={'query': 'stored invalid url fallback', 'mode': 'vector'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'keyword'
    assert payload['applied_strategies'] == ['keyword']
    assert payload['items'][0]['id'] == entry['id']


def test_rebuild_embeddings_route_updates_search_metadata(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify explicit rebuild stores embeddings and embedding metadata.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.service as ai_service

    def _mock_request_embedding(config, text: str, *, input_type: str) -> list[float]:
        return [0.3, 0.4]

    monkeypatch.setattr(ai_service, 'request_embedding', _mock_request_embedding)

    with _ai_client(apply_runtime_env, migrated_database, search_enable_semantic=True) as client:
        headers = _auth_headers(client, bootstrap_payload)
        _update_ai_settings(client, headers)
        content_type = _create_content_type(client, headers)
        entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Rebuild Target',
            body='<p>Rebuild me</p>',
        )

        response = client.post(
            '/api/v1/ai/search/rebuild',
            headers=headers,
            json={'batch_size': 10, 'max_documents': 10},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['attempted'] >= 1
    assert payload['embedded'] >= 1
    assert payload['failed'] == 0

    database_dsn = build_database_dsn(
        migrated_database, migrated_database['PRAGMA_DATABASE_NAME']
    )
    with psycopg.connect(database_dsn) as connection:
        row = connection.execute(
            """
            SELECT embedding_provider, embedding_model, embedding_updated_at
            FROM pragma_search_documents
            WHERE entry_id = %s
            """,
            (entry['id'],),
        ).fetchone()

    assert row[0] == 'voyage'
    assert row[1] == 'voyage-3.5-lite'
    assert row[2] is not None


def test_content_save_paths_never_call_provider(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify content save flows remain independent from provider calls.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.service as ai_service

    calls: list[str] = []

    def _tracking_request_embedding(config, text: str, *, input_type: str) -> list[float]:
        calls.append(input_type)
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(ai_service, 'request_embedding', _tracking_request_embedding)

    with _ai_client(apply_runtime_env, migrated_database, search_enable_semantic=True) as client:
        headers = _auth_headers(client, bootstrap_payload)
        _update_ai_settings(client, headers)
        content_type = _create_content_type(client, headers)
        response = client.post(
            '/api/v1/content/entries',
            headers=headers,
            json={
                'content_type_id': str(content_type['id']),
                'status': 'published',
                'payload': {
                    'title': 'Provider Isolation',
                    'body': '<p>Save paths should not invoke provider calls</p>',
                },
            },
        )

    assert response.status_code == 201
    assert calls == []
