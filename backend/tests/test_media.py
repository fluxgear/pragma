# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Media-library integration tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from pragma.app import create_app
from tests.helpers import build_database_dsn

_PNG_1X1 = (
    b'\x89PNG\r\n\x1a\n'
    b'\x00\x00\x00\rIHDR'
    b'\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde'
    b'\x00\x00\x00\x0bIDATx\x9cc```\x00\x00\x00\x04\x00\x01'
    b'\x0b\x0e-\xb4'
    b'\x00\x00\x00\x00IEND\xaeB`\x82'
)


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Create the first super-admin for media-flow tests.

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


@pytest.fixture()
def media_root(tmp_path: Path) -> Path:
    """Return an isolated local media root for a test.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        Path: Isolated local media root.

    Raises:
        None.
    """

    return tmp_path / 'media-root'


@pytest.fixture()
def media_client(
    migrated_database: dict[str, str],
    apply_runtime_env,
    media_root: Path,
) -> Iterator[TestClient]:
    """Return a FastAPI client configured for local media-library tests.

    Args:
        migrated_database: Environment values for the migrated test database.
        apply_runtime_env: Runtime environment helper fixture.
        media_root: Isolated local media root.

    Returns:
        Iterator[TestClient]: Active FastAPI test client.

    Raises:
        StorageError: If application startup cannot connect to PostgreSQL.
    """

    apply_runtime_env(
        {
            'PRAGMA_MEDIA_ROOT': str(media_root),
            'PRAGMA_MEDIA_MAX_UPLOAD_BYTES': '1048576',
        }
    )
    with TestClient(create_app()) as client:
        yield client


def test_migrations_create_media_schema(migrated_database: dict[str, str]) -> None:
    """Verify the Alembic chain creates the expected M5 media tables and indexes.

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
                to_regclass('public.pragma_media_assets') AS media_table,
                to_regclass('public.ix_pragma_media_assets_storage_key') AS storage_key_index,
                to_regclass(
                    'public.ix_pragma_media_assets_mime_type_created_at'
                ) AS mime_type_created_at_index
            """
        ).fetchone()

    assert row['media_table'] == 'pragma_media_assets'
    assert row['storage_key_index'] == 'ix_pragma_media_assets_storage_key'
    assert row['mime_type_created_at_index'] == 'ix_pragma_media_assets_mime_type_created_at'


def test_media_routes_require_auth(media_client: TestClient) -> None:
    """Verify media routes reject unauthenticated access.

    Args:
        media_client: FastAPI test client configured for media tests.

    Returns:
        None.

    Raises:
        None.
    """

    response = media_client.get('/api/v1/media/assets')

    assert response.status_code == 401
    assert response.json() == {
        'detail': 'Authentication required',
        'code': 'AUTH_REQUIRED',
    }


def test_media_upload_list_detail_content_and_delete_flow(
    media_client: TestClient,
    bootstrap_payload: dict[str, str],
    media_root: Path,
) -> None:
    """Verify media uploads work end to end across API and local storage.

    Args:
        media_client: FastAPI test client configured for media tests.
        bootstrap_payload: Bootstrap request payload.
        media_root: Isolated local media root.

    Returns:
        None.

    Raises:
        None.
    """

    auth_headers = _auth_headers(media_client, bootstrap_payload)
    upload_headers = {**auth_headers, 'Content-Type': 'image/png'}

    upload_response = media_client.post(
        '/api/v1/media/assets?filename=hero-image.png&alt_text=Hero%20image&caption=Homepage',
        headers=upload_headers,
        content=_PNG_1X1,
    )

    assert upload_response.status_code == 201
    uploaded = upload_response.json()
    assert uploaded['original_filename'] == 'hero-image.png'
    assert uploaded['mime_type'] == 'image/png'
    assert uploaded['size_bytes'] == len(_PNG_1X1)
    assert uploaded['width'] == 1
    assert uploaded['height'] == 1
    assert uploaded['alt_text'] == 'Hero image'
    assert uploaded['caption'] == 'Homepage'
    stored_path = media_root / uploaded['storage_key']
    assert stored_path.exists()

    list_response = media_client.get('/api/v1/media/assets', headers=auth_headers)
    assert list_response.status_code == 200
    assert list_response.json()['total'] == 1

    detail_response = media_client.get(
        f'/api/v1/media/assets/{uploaded["id"]}',
        headers=auth_headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()['selection']['content_url'].endswith('/content')

    content_response = media_client.get(
        f'/api/v1/media/assets/{uploaded["id"]}/content',
        headers=auth_headers,
    )
    assert content_response.status_code == 200
    assert content_response.content == _PNG_1X1
    assert content_response.headers['content-type'].startswith('image/png')

    delete_response = media_client.delete(
        f'/api/v1/media/assets/{uploaded["id"]}',
        headers=auth_headers,
    )
    assert delete_response.status_code == 204
    assert not stored_path.exists()

    final_list_response = media_client.get('/api/v1/media/assets', headers=auth_headers)
    assert final_list_response.status_code == 200
    assert final_list_response.json()['total'] == 0


def test_media_upload_rejects_invalid_file(
    media_client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify unsupported uploads are rejected with structured errors.

    Args:
        media_client: FastAPI test client configured for media tests.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = {**_auth_headers(media_client, bootstrap_payload), 'Content-Type': 'text/plain'}

    response = media_client.post(
        '/api/v1/media/assets?filename=notes.txt',
        headers=headers,
        content=b'not an image',
    )

    assert response.status_code == 415
    assert response.json() == {
        'detail': 'Uploaded bytes do not match a supported image format for text/plain',
        'code': 'MEDIA_TYPE_UNSUPPORTED',
    }


def test_media_upload_preserves_original_when_derivative_generation_fails(
    media_client: TestClient,
    bootstrap_payload: dict[str, str],
    media_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify derivative failures do not block original media persistence.

    Args:
        media_client: FastAPI test client configured for media tests.
        bootstrap_payload: Bootstrap request payload.
        media_root: Isolated local media root.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    def _explode(*args, **kwargs):
        raise RuntimeError('derivative failure')

    monkeypatch.setattr('pragma.media.service._build_media_variants', _explode)
    headers = {**_auth_headers(media_client, bootstrap_payload), 'Content-Type': 'image/png'}

    response = media_client.post(
        '/api/v1/media/assets?filename=fallback.png',
        headers=headers,
        content=_PNG_1X1,
    )

    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded['variants'] == {}
    assert (media_root / uploaded['storage_key']).exists()
