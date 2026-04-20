# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Content-engine integration tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Any

import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from tests.helpers import build_database_dsn


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Create the first super-admin for content-flow tests.

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
    """Log in the bootstrapped admin and return auth headers.

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


def _content_type_payload() -> dict[str, Any]:
    """Return a reusable content-type payload for integration tests.

    Args:
        None.

    Returns:
        dict[str, Any]: Content-type request payload.

    Raises:
        None.
    """

    return {
        'name': 'Blog Posts',
        'description': 'Structured blog content',
        'field_definitions': [
            {
                'name': 'title',
                'label': 'Title',
                'kind': 'text',
                'required': True,
                'min_length': 3,
                'max_length': 120,
            },
            {
                'name': 'body',
                'label': 'Body',
                'kind': 'rich_text',
                'required': True,
                'min_length': 1,
            },
            {
                'name': 'views',
                'label': 'Views',
                'kind': 'integer',
                'required': True,
                'minimum': 0,
            },
        ],
    }


def _create_content_type(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    """Create a reusable content type and return the response payload.

    Args:
        client: FastAPI test client.
        headers: Bearer authentication headers.

    Returns:
        dict[str, Any]: Parsed content-type response payload.

    Raises:
        AssertionError: If creation fails unexpectedly.
    """

    response = client.post('/api/v1/content/types', headers=headers, json=_content_type_payload())
    assert response.status_code == 201
    return response.json()


def test_migrations_create_content_schema(migrated_database: dict[str, str]) -> None:
    """Verify the Alembic chain creates the expected M2 tables and indexes.

    Args:
        migrated_database: Environment values for the migrated test database.

    Returns:
        None.

    Raises:
        None.
    """

    dsn = build_database_dsn(migrated_database, migrated_database['PRAGMA_DATABASE_NAME'])
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        row = connection.execute(
            """
            SELECT
                to_regclass('public.pragma_content_types') AS content_types_table,
                to_regclass('public.pragma_content_fields') AS content_fields_table,
                to_regclass('public.pragma_content_entries') AS content_entries_table,
                to_regclass('public.ix_pragma_content_types_slug') AS content_types_slug_index,
                to_regclass(
                    'public.ix_pragma_content_entries_payload'
                ) AS content_entries_payload_index
            """
        ).fetchone()

    assert row['content_types_table'] == 'pragma_content_types'
    assert row['content_fields_table'] == 'pragma_content_fields'
    assert row['content_entries_table'] == 'pragma_content_entries'
    assert row['content_types_slug_index'] == 'ix_pragma_content_types_slug'
    assert row['content_entries_payload_index'] == 'ix_pragma_content_entries_payload'


def test_content_routes_require_auth(client: TestClient) -> None:
    """Verify content routes reject unauthenticated access.

    Args:
        client: FastAPI test client.

    Returns:
        None.

    Raises:
        None.
    """

    response = client.get('/api/v1/content/types')

    assert response.status_code == 401
    assert response.json() == {
        'detail': 'Authentication required',
        'code': 'AUTH_REQUIRED',
    }


def test_content_type_crud_flow(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify content types can be created, listed, updated, and deleted.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    create_response = client.post(
        '/api/v1/content/types',
        headers=headers,
        json=_content_type_payload(),
    )

    assert create_response.status_code == 201
    content_type = create_response.json()
    assert content_type['slug'] == 'blog-posts'
    assert len(content_type['field_definitions']) == 3

    list_response = client.get('/api/v1/content/types', headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()['total'] == 1

    get_response = client.get(
        f"/api/v1/content/types/{content_type['id']}",
        headers=headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()['name'] == 'Blog Posts'

    update_payload = {
        'name': 'Articles',
        'slug': 'articles',
        'description': 'Updated content type',
        'field_definitions': [
            {
                'name': 'title',
                'label': 'Title',
                'kind': 'text',
                'required': True,
                'min_length': 3,
                'max_length': 120,
            },
            {
                'name': 'summary',
                'label': 'Summary',
                'kind': 'text',
                'required': False,
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
    update_response = client.put(
        f"/api/v1/content/types/{content_type['id']}",
        headers=headers,
        json=update_payload,
    )

    assert update_response.status_code == 200
    updated_type = update_response.json()
    assert updated_type['slug'] == 'articles'
    assert len(updated_type['field_definitions']) == 3

    delete_response = client.delete(
        f"/api/v1/content/types/{content_type['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    final_list_response = client.get('/api/v1/content/types', headers=headers)
    assert final_list_response.status_code == 200
    assert final_list_response.json()['total'] == 0


def test_content_type_create_rejects_blank_name(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify content-type creation rejects whitespace-only names.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    payload = _content_type_payload()
    payload['name'] = '   '
    payload['slug'] = 'articles'

    response = client.post(
        '/api/v1/content/types',
        headers=headers,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {
        'detail': 'Request validation failed',
        'code': 'VALIDATION_ERROR',
    }


def test_content_type_update_rejects_blank_name(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify content-type updates reject whitespace-only names.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    content_type = _create_content_type(client, headers)
    payload = _content_type_payload()
    payload['name'] = '   '
    payload['slug'] = 'articles'

    response = client.put(
        f"/api/v1/content/types/{content_type['id']}",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {
        'detail': 'Request validation failed',
        'code': 'VALIDATION_ERROR',
    }


def test_entry_crud_flow_and_publish_state(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify entries support CRUD plus publish-state transitions.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    content_type = _create_content_type(client, headers)

    create_entry_response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type['id'],
            'status': 'published',
            'payload': {
                'title': 'Hello World',
                'body': '<p>Hello</p>',
                'views': 1,
            },
        },
    )

    assert create_entry_response.status_code == 201
    entry = create_entry_response.json()
    assert entry['slug'] == 'hello-world'
    assert entry['status'] == 'published'
    assert entry['published_at'] is not None

    list_response = client.get(
        f"/api/v1/content/entries?content_type_id={content_type['id']}&status=published",
        headers=headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()['total'] == 1

    get_response = client.get(
        f"/api/v1/content/entries/{entry['id']}",
        headers=headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()['content_type_slug'] == 'blog-posts'

    archive_response = client.put(
        f"/api/v1/content/entries/{entry['id']}",
        headers=headers,
        json={
            'status': 'archived',
            'payload': {
                'title': 'Hello World',
                'body': '<p>Hello</p>',
                'views': 2,
            },
        },
    )
    assert archive_response.status_code == 200
    archived_entry = archive_response.json()
    assert archived_entry['status'] == 'archived'
    assert archived_entry['published_at'] == entry['published_at']

    draft_response = client.put(
        f"/api/v1/content/entries/{entry['id']}",
        headers=headers,
        json={
            'status': 'draft',
            'payload': {
                'title': 'Hello World',
                'body': '<p>Hello</p>',
                'views': 3,
            },
        },
    )
    assert draft_response.status_code == 200
    assert draft_response.json()['published_at'] is None

    delete_response = client.delete(
        f"/api/v1/content/entries/{entry['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    final_list_response = client.get('/api/v1/content/entries', headers=headers)
    assert final_list_response.status_code == 200
    assert final_list_response.json()['total'] == 0


def test_entry_validation_rejects_invalid_payload(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify unknown entry fields are rejected explicitly.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    content_type = _create_content_type(client, headers)

    response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type['id'],
            'status': 'draft',
            'payload': {
                'title': 'Hello World',
                'body': '<p>Hello</p>',
                'views': 1,
                'extra': 'unexpected',
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        'detail': 'Unknown field(s) for this content type: extra',
        'code': 'ENTRY_FIELD_UNKNOWN',
    }


def test_entry_validation_rejects_missing_required_field(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify entry validation rejects missing required fields explicitly.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    content_type = _create_content_type(client, headers)

    response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type['id'],
            'status': 'draft',
            'payload': {
                'body': '<p>Hello</p>',
                'views': 1,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        'detail': "Field 'title' is required",
        'code': 'ENTRY_FIELD_REQUIRED',
    }


def test_entry_validation_rejects_invalid_field_type(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify entry validation rejects field values of the wrong type.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    content_type = _create_content_type(client, headers)

    response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type['id'],
            'status': 'draft',
            'payload': {
                'title': 'Hello World',
                'body': '<p>Hello</p>',
                'views': 'many',
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        'detail': "Field 'views' must be an integer",
        'code': 'ENTRY_FIELD_INVALID',
    }


def test_entry_slug_conflict_returns_structured_error(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify explicit duplicate entry slugs are rejected deterministically.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    content_type = _create_content_type(client, headers)

    first_response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type['id'],
            'slug': 'duplicate-slug',
            'status': 'draft',
            'payload': {
                'title': 'First Entry',
                'body': '<p>One</p>',
                'views': 1,
            },
        },
    )
    second_response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type['id'],
            'slug': 'duplicate-slug',
            'status': 'draft',
            'payload': {
                'title': 'Second Entry',
                'body': '<p>Two</p>',
                'views': 2,
            },
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        'detail': 'An entry with this slug already exists for the content type',
        'code': 'ENTRY_SLUG_CONFLICT',
    }


def test_content_type_delete_rejects_types_with_entries(
    client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify content types cannot be deleted while entries still exist.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = _auth_headers(client, bootstrap_payload)
    content_type = _create_content_type(client, headers)
    entry_response = client.post(
        '/api/v1/content/entries',
        headers=headers,
        json={
            'content_type_id': content_type['id'],
            'status': 'draft',
            'payload': {
                'title': 'Keep Me',
                'body': '<p>Bound</p>',
                'views': 1,
            },
        },
    )

    assert entry_response.status_code == 201

    delete_response = client.delete(
        f"/api/v1/content/types/{content_type['id']}",
        headers=headers,
    )

    assert delete_response.status_code == 409
    assert delete_response.json() == {
        'detail': 'Content type has existing entries and cannot be deleted',
        'code': 'CONTENT_TYPE_IN_USE',
    }
