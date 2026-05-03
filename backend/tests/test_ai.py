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

import socket
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

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


def _update_ai_settings(
    client: TestClient,
    headers: dict[str, str],
    *,
    embedding_dimensions: int = 2,
) -> dict[str, object]:
    """Persist a reusable AI provider configuration and return its response payload.

    Args:
        client: FastAPI test client.
        headers: Authenticated request headers.
        embedding_dimensions: Configured provider embedding vector dimensions.

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
            'embedding_dimensions': embedding_dimensions,
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
    """Verify M9+ AI migrations create provider settings and embedding schema.

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
                ) AS has_embedding_updated_at,
                EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'pragma_ai_provider_settings'
                      AND column_name = 'embedding_dimensions'
                ) AS has_embedding_dimensions,
                EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'ck_pragma_ai_provider_settings_embedding_dimensions'
                ) AS has_embedding_dimensions_check
            """
        ).fetchone()

    assert row[0] == 'pragma_ai_provider_settings'
    assert row[1] == 'ix_pragma_search_documents_embedding_metadata'
    assert row[2] is True
    assert row[3] is True
    assert row[4] is True
    assert row[5] is True
    assert row[6] is True


class _EmbeddingResponse:
    """Minimal context-manager response for provider HTTP tests."""

    def __init__(self, body: bytes, *, content_length: str | None = None) -> None:
        self._body = body
        self._offset = 0
        self._content_length = content_length
        self.read_sizes: list[int] = []

    def __enter__(self) -> _EmbeddingResponse:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def getheader(self, name: str) -> str | None:
        if name.lower() == 'content-length':
            return self._content_length
        return None

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


def _public_getaddrinfo(
    _host: str,
    port: int,
    *args: object,
    **kwargs: object,
) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    """Return a deterministic public TCP resolution for provider tests.

    Args:
        _host: Ignored hostname under test.
        port: Destination port under test.
        *args: Ignored positional resolution arguments.
        **kwargs: Ignored keyword resolution arguments.

    Returns:
        list[tuple[int, int, int, str, tuple[str, int]]]: Public TCP socket targets.

    Raises:
        None.
    """

    del args, kwargs
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('8.8.8.8', port))]


def test_request_embedding_reads_successful_response_incrementally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify provider responses are read in bounded chunks before parsing."""

    import pragma.ai.providers as ai_providers
    from pragma.ai.models import AIProvider
    from pragma.ai.providers import EmbeddingProviderConfig, request_embedding

    response = _EmbeddingResponse(b'{"data":[{"embedding":[0.1,0.2]}]}')

    def _open_embedding_request(*_args: object, **_kwargs: object) -> _EmbeddingResponse:
        return response

    monkeypatch.setattr(ai_providers, '_EMBEDDING_RESPONSE_READ_CHUNK_BYTES', 8)
    monkeypatch.setattr(ai_providers.socket, 'getaddrinfo', _public_getaddrinfo)
    monkeypatch.setattr(ai_providers, '_open_embedding_request', _open_embedding_request)

    embedding = request_embedding(
        EmbeddingProviderConfig(
            provider=AIProvider.VOYAGE,
            base_url='https://api.voyageai.com/v1',
            api_key='test-ai-key',
            embedding_model='voyage-3.5-lite',
            embedding_dimensions=2,
            request_timeout_seconds=1,
        ),
        'bounded query',
        input_type='query',
    )

    assert embedding == [0.1, 0.2]
    assert response.read_sizes[0] == 8


def test_request_embedding_rejects_declared_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify oversized Content-Length is rejected before body reads."""

    import pragma.ai.providers as ai_providers
    from pragma.ai.models import AIProvider
    from pragma.ai.providers import EmbeddingProviderConfig, request_embedding

    response = _EmbeddingResponse(
        b'', content_length=str(ai_providers._MAX_EMBEDDING_RESPONSE_BYTES + 1)
    )

    def _open_embedding_request(*_args: object, **_kwargs: object) -> _EmbeddingResponse:
        return response

    monkeypatch.setattr(ai_providers.socket, 'getaddrinfo', _public_getaddrinfo)
    monkeypatch.setattr(ai_providers, '_open_embedding_request', _open_embedding_request)

    with pytest.raises(SearchError) as exc_info:
        request_embedding(
            EmbeddingProviderConfig(
                provider=AIProvider.VOYAGE,
                base_url='https://api.voyageai.com/v1',
                api_key='test-ai-key',
                embedding_model='voyage-3.5-lite',
                embedding_dimensions=2,
                request_timeout_seconds=1,
            ),
            'oversized query',
            input_type='query',
        )

    assert exc_info.value.code == 'SEARCH_EMBEDDING_PROVIDER_INVALID'
    assert response.read_sizes == []


def test_request_embedding_rejects_streamed_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify chunked provider bodies are capped without Content-Length."""

    import pragma.ai.providers as ai_providers
    from pragma.ai.models import AIProvider
    from pragma.ai.providers import EmbeddingProviderConfig, request_embedding

    response = _EmbeddingResponse(b'012345678')

    def _open_embedding_request(*_args: object, **_kwargs: object) -> _EmbeddingResponse:
        return response

    monkeypatch.setattr(ai_providers, '_MAX_EMBEDDING_RESPONSE_BYTES', 8)
    monkeypatch.setattr(ai_providers, '_EMBEDDING_RESPONSE_READ_CHUNK_BYTES', 4)
    monkeypatch.setattr(ai_providers.socket, 'getaddrinfo', _public_getaddrinfo)
    monkeypatch.setattr(ai_providers, '_open_embedding_request', _open_embedding_request)

    with pytest.raises(SearchError) as exc_info:
        request_embedding(
            EmbeddingProviderConfig(
                provider=AIProvider.VOYAGE,
                base_url='https://api.voyageai.com/v1',
                api_key='test-ai-key',
                embedding_model='voyage-3.5-lite',
                embedding_dimensions=2,
                request_timeout_seconds=1,
            ),
            'oversized query',
            input_type='query',
        )

    assert exc_info.value.code == 'SEARCH_EMBEDDING_PROVIDER_INVALID'
    assert response.read_sizes == [4, 4, 1]


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

    monkeypatch.setattr(ai_providers.socket, 'getaddrinfo', _public_getaddrinfo)
    monkeypatch.setattr(ai_providers, '_open_embedding_request', _raise_timeout)

    with pytest.raises(SearchError) as exc_info:
        request_embedding(
            EmbeddingProviderConfig(
                provider=AIProvider.VOYAGE,
                base_url='https://api.voyageai.com/v1',
                api_key='test-ai-key',
                embedding_model='voyage-3.5-lite',
                embedding_dimensions=2,
                request_timeout_seconds=1,
            ),
            'timeout query',
            input_type='query',
        )

    assert exc_info.value.code == 'SEARCH_EMBEDDING_PROVIDER_UNAVAILABLE'
    assert exc_info.value.status_code == 503


def test_request_embedding_rejects_hostnames_resolving_to_private_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify runtime DNS resolution rejects private or local provider targets.

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

    def _private_getaddrinfo(
        _host: str,
        port: int,
        *args: object,
        **kwargs: object,
    ) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        del args, kwargs
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('127.0.0.1', port))
        ]

    monkeypatch.setattr(ai_providers.socket, 'getaddrinfo', _private_getaddrinfo)

    with pytest.raises(SearchError) as exc_info:
        request_embedding(
            EmbeddingProviderConfig(
                provider=AIProvider.VOYAGE,
                base_url='https://api.example.com/v1',
                api_key='test-ai-key',
                embedding_model='voyage-3.5-lite',
                embedding_dimensions=2,
                request_timeout_seconds=1,
            ),
            'private target query',
            input_type='query',
        )

    assert exc_info.value.code == 'SEARCH_EMBEDDING_PROVIDER_INVALID'


def test_request_embedding_rejects_provider_redirects() -> None:
    """Verify redirect-based provider pivots are rejected.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.providers as ai_providers

    handler = ai_providers._RejectRedirectHandler()

    with pytest.raises(SearchError) as exc_info:
        handler.redirect_request(
            ai_providers.request.Request('https://api.example.com/v1/embeddings'),
            object(),
            302,
            'Found',
            {},
            'https://internal.example/embeddings',
        )

    assert exc_info.value.code == 'SEARCH_EMBEDDING_PROVIDER_INVALID'


def test_request_embedding_allows_private_resolution_with_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify runtime private-target checks honor the explicit operator opt-in.

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

    response = _EmbeddingResponse(b'{"data":[{"embedding":[0.1,0.2]}]}')

    def _private_getaddrinfo(
        _host: str,
        port: int,
        *args: object,
        **kwargs: object,
    ) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        del args, kwargs
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('127.0.0.1', port))
        ]

    def _open_embedding_request(*_args: object, **_kwargs: object) -> _EmbeddingResponse:
        return response

    monkeypatch.setattr(ai_providers.socket, 'getaddrinfo', _private_getaddrinfo)
    monkeypatch.setattr(ai_providers, '_open_embedding_request', _open_embedding_request)

    embedding = request_embedding(
        EmbeddingProviderConfig(
            provider=AIProvider.VOYAGE,
            base_url='http://127.0.0.1:11434/v1',
            api_key='test-ai-key',
            embedding_model='voyage-3.5-lite',
            embedding_dimensions=2,
            request_timeout_seconds=1,
            allow_private_base_urls=True,
        ),
        'private opt-in query',
        input_type='query',
    )

    assert embedding == [0.1, 0.2]


def test_open_embedding_request_uses_prevalidated_socket_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify provider requests connect only to prevalidated socket targets.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.providers as ai_providers

    captured: dict[str, object] = {}

    class _FakeConnection:
        def __init__(
            self,
            host: str,
            *,
            family: int,
            sockaddr: tuple[object, ...],
            timeout: int,
        ) -> None:
            captured['host'] = host
            captured['family'] = family
            captured['sockaddr'] = sockaddr
            captured['timeout'] = timeout

        def request(
            self,
            method: str,
            path: str,
            body: object,
            headers: dict[str, str],
        ) -> None:
            captured['method'] = method
            captured['path'] = path
            captured['body'] = body
            captured['headers'] = headers

        def getresponse(self) -> _EmbeddingResponse:
            response = _EmbeddingResponse(b'{"data":[{"embedding":[0.1,0.2]}]}')
            response.status = 200
            return response

        def close(self) -> None:
            captured['closed'] = True

    monkeypatch.setattr(ai_providers, '_DirectHTTPSConnection', _FakeConnection)

    http_request = ai_providers.request.Request(
        'https://api.example.com/v1/embeddings?foo=bar',
        data=b'{"input":"x"}',
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    with ai_providers._open_embedding_request(
        http_request,
        timeout=7,
        parsed_url=ai_providers.parse.urlsplit(http_request.full_url),
        resolved_targets=((socket.AF_INET, ('93.184.216.34', 443)),),
    ) as response:
        body = ai_providers._read_limited_response_body(response)

    assert body == b'{"data":[{"embedding":[0.1,0.2]}]}'
    assert captured['host'] == 'api.example.com'
    assert captured['family'] == socket.AF_INET
    assert captured['sockaddr'] == ('93.184.216.34', 443)
    assert captured['timeout'] == 7
    assert captured['method'] == 'POST'
    assert captured['path'] == '/v1/embeddings?foo=bar'
    assert captured['closed'] is True


def test_open_embedding_request_rejects_redirect_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify provider requests reject redirect responses without following them.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.providers as ai_providers

    class _FakeConnection:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def request(
            self,
            method: str,
            path: str,
            body: object,
            headers: dict[str, str],
        ) -> None:
            del method, path, body, headers

        def getresponse(self) -> _EmbeddingResponse:
            response = _EmbeddingResponse(b'')
            response.status = 302
            return response

        def close(self) -> None:
            return None

    monkeypatch.setattr(ai_providers, '_DirectHTTPSConnection', _FakeConnection)

    http_request = ai_providers.request.Request(
        'https://api.example.com/v1/embeddings',
        data=b'{}',
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    with pytest.raises(SearchError) as exc_info:
        ai_providers._open_embedding_request(
            http_request,
            timeout=7,
            parsed_url=ai_providers.parse.urlsplit(http_request.full_url),
            resolved_targets=((socket.AF_INET, ('93.184.216.34', 443)),),
        )

    assert exc_info.value.code == 'SEARCH_EMBEDDING_PROVIDER_INVALID'


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
        connection.execute(
            """
            DELETE FROM pragma_user_roles
            WHERE user_id = (
                SELECT id
                FROM pragma_users
                WHERE email = %s
            )
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
        connection.execute(
            """
            DELETE FROM pragma_user_roles
            WHERE user_id = (
                SELECT id
                FROM pragma_users
                WHERE email = %s
            )
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
    assert update_payload['embedding_dimensions'] == 2
    assert update_payload['api_key_configured'] is True
    assert update_payload['embeddings_rebuild_required'] is True
    assert response.status_code == 200
    assert response.json()['provider'] == 'voyage'
    assert response.json()['embedding_dimensions'] == 2
    assert response.json()['api_key_configured'] is True
    assert response.json()['embeddings_rebuild_required'] is False
    assert 'api_key' not in response.json()


def test_ai_settings_reject_private_or_plain_http_base_urls_by_default(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify AI provider settings reject unsafe egress targets by default.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    with _ai_client(apply_runtime_env, migrated_database) as client:
        headers = _auth_headers(client, bootstrap_payload)

        localhost_response = client.put(
            '/api/v1/ai/settings',
            headers=headers,
            json={
                'enabled': True,
                'provider': 'openai_compatible',
                'base_url': 'https://127.0.0.1:11434/v1',
                'embedding_model': 'local-embedding',
                'request_timeout_seconds': 15,
                'api_key': 'local-key',
            },
        )
        http_response = client.put(
            '/api/v1/ai/settings',
            headers=headers,
            json={
                'enabled': True,
                'provider': 'openai_compatible',
                'base_url': 'http://api.example.com/v1',
                'embedding_model': 'remote-embedding',
                'request_timeout_seconds': 15,
                'api_key': 'remote-key',
            },
        )

    assert localhost_response.status_code == 400
    assert localhost_response.json()['code'] == 'AI_SETTINGS_INVALID'
    assert http_response.status_code == 400
    assert http_response.json()['code'] == 'AI_SETTINGS_INVALID'


def test_ai_settings_allow_private_base_url_with_explicit_runtime_flag(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify operator opt-in permits private AI provider base URLs.

    Args:
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    runtime_values = dict(migrated_database)
    runtime_values['PRAGMA_SEARCH_ENABLE_SEMANTIC'] = 'true'
    runtime_values['PRAGMA_AI_ALLOW_PRIVATE_BASE_URLS'] = 'true'
    apply_runtime_env(runtime_values)

    with TestClient(create_app()) as client:
        headers = _auth_headers(client, bootstrap_payload)
        response = client.put(
            '/api/v1/ai/settings',
            headers=headers,
            json={
                'enabled': True,
                'provider': 'openai_compatible',
                'base_url': 'http://127.0.0.1:11434/v1',
                'embedding_model': 'local-embedding',
                'embedding_dimensions': 2,
                'request_timeout_seconds': 15,
                'api_key': 'local-key',
            },
        )

    assert response.status_code == 200
    assert response.json()['base_url'] == 'http://127.0.0.1:11434/v1'
    assert response.json()['embedding_dimensions'] == 2


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
            'embedding_dimensions': None,
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
        'embedding_dimensions': None,
        'request_timeout_seconds': 15,
        'api_key_configured': False,
        'updated_at': response.json()['updated_at'],
        'embeddings_rebuild_required': False,
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
        return [0.1, 0.2]

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
        'embedding_dimensions': 2,
    }
    assert calls == [('voyage', 'query')]


def test_search_auto_embedding_uses_provider_when_available(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify authenticated vector search can auto-generate a query embedding.

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
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'vector'
    assert payload['applied_strategies'] == ['vector']
    assert [item['id'] for item in payload['items']] == [alpha['id'], beta['id']]


def test_search_auto_embedding_enforces_provider_model_contract(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify authenticated semantic search filters provider/model drift.

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
        current = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Model Contract Current',
            body='<p>Current model vector body</p>',
        )
        stale_model = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Model Contract Stale',
            body='<p>Stale model vector body</p>',
        )
        _seed_search_embedding(
            migrated_database,
            current['id'],
            [1.0, 0.0],
            provider='voyage',
            embedding_model='voyage-3.5-lite',
        )
        _seed_search_embedding(
            migrated_database,
            stale_model['id'],
            [1.0, 0.0],
            provider='voyage',
            embedding_model='voyage-old',
        )

        response = client.get(
            '/api/v1/search/entries',
            params={'query': 'model contract', 'mode': 'vector'},
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'vector'
    assert payload['applied_strategies'] == ['vector']
    assert [item['id'] for item in payload['items']] == [current['id']]
    assert payload['semantic_diagnostics'] == []


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
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] == 'keyword'
    assert payload['applied_strategies'] == ['keyword']
    assert payload['items'][0]['id'] == entry['id']
def test_public_search_auto_mode_does_not_call_provider_without_authentication(
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify unauthenticated public/API auto search never calls the provider.

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

    def _unexpected_request_embedding(config, text: str, *, input_type: str) -> list[float]:
        raise AssertionError('unauthenticated search must not call embedding provider')

    monkeypatch.setattr(ai_service, 'request_embedding', _unexpected_request_embedding)

    with _ai_client(apply_runtime_env, migrated_database, search_enable_semantic=True) as client:
        headers = _auth_headers(client, bootstrap_payload)
        _update_ai_settings(client, headers)
        content_type = _create_content_type(client, headers)
        entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Public Keyword Result',
            body='<p>Public search should stay keyword only</p>',
        )

        response = client.get(
            '/api/v1/search/entries',
            params={'query': 'public keyword result', 'mode': 'auto'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['mode_applied'] in {'keyword', 'hybrid'}
    assert 'vector' not in payload['applied_strategies']
    assert payload['items'][0]['id'] == entry['id']
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


def test_search_falls_back_to_keyword_when_provider_hostname_resolves_private(
    monkeypatch: pytest.MonkeyPatch,
    apply_runtime_env: Callable[[dict[str, str]], None],
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify vector search falls back cleanly when runtime DNS resolves private.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        apply_runtime_env: Fixture helper that applies runtime environment values.
        migrated_database: Environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.providers as ai_providers

    def _private_getaddrinfo(
        _host: str,
        port: int,
        *args: object,
        **kwargs: object,
    ) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        del args, kwargs
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('127.0.0.1', port))
        ]

    monkeypatch.setattr(ai_providers.socket, 'getaddrinfo', _private_getaddrinfo)

    with _ai_client(apply_runtime_env, migrated_database, search_enable_semantic=True) as client:
        headers = _auth_headers(client, bootstrap_payload)
        _update_ai_settings(client, headers)
        content_type = _create_content_type(client, headers)
        entry = _create_entry(
            client,
            headers,
            str(content_type['id']),
            title='Stored Private Resolution Fallback',
            body='<p>Keyword fallback should survive runtime private DNS resolution</p>',
        )

        response = client.get(
            '/api/v1/search/entries',
            params={'query': 'stored private resolution fallback', 'mode': 'vector'},
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


def test_rebuild_embeddings_does_not_hold_storage_connection_during_provider_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify rebuild releases DB resources before provider embedding requests.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    import pragma.ai.service as ai_service

    entry_id = uuid4()
    provider_connection_counts: list[int] = []
    update_connection_counts: list[int] = []

    class _FakeConnection:
        def __init__(self, storage: _GuardedStorage) -> None:
            self.storage = storage

        @contextmanager
        def transaction(self) -> Iterator[None]:
            yield

    class _GuardedStorage:
        def __init__(self) -> None:
            self.active_connections = 0
            self.scope_count = 0

        @contextmanager
        def connection(self) -> Iterator[_FakeConnection]:
            self.scope_count += 1
            self.active_connections += 1
            try:
                yield _FakeConnection(self)
            finally:
                self.active_connections -= 1

    storage = _GuardedStorage()
    batches = [
        [
            {
                'entry_id': entry_id,
                'title_text': 'Rebuild Guard',
                'body_text': 'Provider calls happen without a DB connection',
                'updated_at': datetime.now(UTC),
            }
        ],
        [],
    ]

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
            'embedding_dimensions': 2,
            'request_timeout_seconds': 5,
        }

    def _mock_list_search_documents_for_embedding_rebuild(
        _connection: object,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        return batches.pop(0)

    def _mock_request_embedding(
        _config: object,
        text: str,
        *,
        input_type: str,
    ) -> list[float]:
        provider_connection_counts.append(storage.active_connections)
        assert text == 'Rebuild Guard Provider calls happen without a DB connection'
        assert input_type == 'document'
        return [0.25, 0.75]

    def _mock_update_search_document_embedding(_connection: object, **_kwargs: object) -> None:
        update_connection_counts.append(storage.active_connections)

    monkeypatch.setattr(
        ai_service, 'get_extension_capabilities', _mock_get_extension_capabilities
    )
    monkeypatch.setattr(ai_service, 'search_embedding_column_exists', lambda _: True)
    monkeypatch.setattr(ai_service, 'get_ai_provider_settings', _mock_get_ai_provider_settings)
    monkeypatch.setattr(
        ai_service,
        'list_search_documents_for_embedding_rebuild',
        _mock_list_search_documents_for_embedding_rebuild,
    )
    monkeypatch.setattr(ai_service, 'request_embedding', _mock_request_embedding)
    monkeypatch.setattr(
        ai_service, 'update_search_document_embedding', _mock_update_search_document_embedding
    )

    response = ai_service.rebuild_search_embeddings(
        storage,
        ai_service.AISearchEmbeddingRebuildRequest(batch_size=10, max_documents=10),
    )

    assert provider_connection_counts == [0]
    assert update_connection_counts == [1]
    assert storage.scope_count == 4
    assert storage.active_connections == 0
    assert response.attempted == 1
    assert response.embedded == 1
    assert response.failed == 0
    assert response.failed_entry_ids == []


def test_force_rebuild_embeddings_uses_keyset_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify forced embedding rebuild advances with a keyset cursor."""

    import pragma.ai.service as ai_service

    first_id = uuid4()
    second_id = uuid4()
    first_updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    second_updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    calls: list[dict[str, object]] = []

    class _FakeConnection:
        @contextmanager
        def transaction(self) -> Iterator[None]:
            yield

    class _Storage:
        @contextmanager
        def connection(self) -> Iterator[_FakeConnection]:
            yield _FakeConnection()

    batches = [
        [
            {
                'entry_id': first_id,
                'title_text': 'First',
                'body_text': 'Batch',
                'updated_at': first_updated_at,
            }
        ],
        [
            {
                'entry_id': second_id,
                'title_text': 'Second',
                'body_text': 'Batch',
                'updated_at': second_updated_at,
            }
        ],
    ]

    def _mock_get_extension_capabilities(
        _connection: object,
    ) -> dict[str, dict[str, bool]]:
        return {'pgvector': {'installed': True}, 'pg_trgm': {'installed': True}}

    def _mock_get_ai_provider_settings(_connection: object) -> dict[str, object]:
        return {
            'enabled': True,
            'provider': 'voyage',
            'base_url': 'https://api.voyageai.com/v1',
            'api_key': 'test-ai-key',
            'embedding_model': 'voyage-3.5-lite',
            'embedding_dimensions': 2,
            'request_timeout_seconds': 5,
        }

    def _mock_list_search_documents_for_embedding_rebuild(
        _connection: object,
        **kwargs: object,
    ) -> list[dict[str, object]]:
        calls.append(kwargs)
        return batches.pop(0) if batches else []

    monkeypatch.setattr(
        ai_service, 'get_extension_capabilities', _mock_get_extension_capabilities
    )
    monkeypatch.setattr(ai_service, 'search_embedding_column_exists', lambda _: True)
    monkeypatch.setattr(ai_service, 'get_ai_provider_settings', _mock_get_ai_provider_settings)
    monkeypatch.setattr(
        ai_service,
        'list_search_documents_for_embedding_rebuild',
        _mock_list_search_documents_for_embedding_rebuild,
    )
    monkeypatch.setattr(
        ai_service,
        'request_embedding',
        lambda *_args, **_kwargs: [0.25, 0.75],
    )
    monkeypatch.setattr(
        ai_service,
        'update_search_document_embedding',
        lambda *_args, **_kwargs: None,
    )

    response = ai_service.rebuild_search_embeddings(
        _Storage(),
        ai_service.AISearchEmbeddingRebuildRequest(
            batch_size=1,
            force=True,
            max_documents=2,
        ),
    )

    assert response.attempted == 2
    assert response.embedded == 2
    assert [call['limit'] for call in calls] == [1, 1]
    assert [call['stale_only'] for call in calls] == [False, False]
    assert calls[0]['expected_embedding_dimensions'] == 2
    assert calls[1]['expected_embedding_dimensions'] == 2
    assert calls[0]['after_updated_at'] is None
    assert calls[0]['after_entry_id'] is None
    assert calls[1]['after_updated_at'] == first_updated_at
    assert calls[1]['after_entry_id'] == first_id
    assert all('offset' not in call for call in calls)


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
