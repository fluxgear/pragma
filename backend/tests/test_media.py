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

import logging
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from pydantic import ValidationError

from pragma.app import create_app
from pragma.auth.security import utc_now
from pragma.config import Settings
from pragma.errors import StorageError
from tests.helpers import build_database_dsn, build_runtime_env

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


@pytest.fixture()
def small_upload_limit_media_client(
    migrated_database: dict[str, str],
    apply_runtime_env,
    media_root: Path,
) -> Iterator[TestClient]:
    """Return a media test client with a small upload limit.

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
            'PRAGMA_MEDIA_MAX_UPLOAD_BYTES': '16',
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
                to_regclass('public.ix_pragma_media_assets_updated_at') AS updated_at_index,
                to_regclass(
                    'public.ix_pragma_media_assets_mime_type_updated_at'
                ) AS mime_type_updated_at_index
            """
        ).fetchone()

    assert row['media_table'] == 'pragma_media_assets'
    assert row['storage_key_index'] == 'ix_pragma_media_assets_storage_key'
    assert row['updated_at_index'] == 'ix_pragma_media_assets_updated_at'
    assert row['mime_type_updated_at_index'] == 'ix_pragma_media_assets_mime_type_updated_at'


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


def test_settings_require_secure_cookie_when_samesite_none(
    example_env_values: dict[str, str],
) -> None:
    """Verify SameSite=None requires a secure refresh-cookie configuration.

    Args:
        example_env_values: Parsed environment values from ``backend/.env.example``.

    Returns:
        None.

    Raises:
        None.
    """

    runtime_env = build_runtime_env(example_env_values, 'pragma_cookie_policy_test')

    with pytest.raises(ValidationError):
        Settings(
            database_host=runtime_env['PRAGMA_DATABASE_HOST'],
            database_port=int(runtime_env['PRAGMA_DATABASE_PORT']),
            database_name=runtime_env['PRAGMA_DATABASE_NAME'],
            database_user=runtime_env['PRAGMA_DATABASE_USER'],
            database_password=runtime_env['PRAGMA_DATABASE_PASSWORD'],
            jwt_secret_key=runtime_env['PRAGMA_JWT_SECRET_KEY'],
            base_url=runtime_env['PRAGMA_BASE_URL'],
            refresh_cookie_samesite='none',
            refresh_cookie_secure=False,
        )


def test_media_openapi_documents_structured_error_responses(media_client: TestClient) -> None:
    """Verify media endpoints publish structured error schemas in OpenAPI.

    Args:
        media_client: FastAPI test client configured for media tests.

    Returns:
        None.

    Raises:
        None.
    """

    response = media_client.get('/openapi.json')

    assert response.status_code == 200
    schema = response.json()
    upload_responses = schema['paths']['/api/v1/media/assets']['post']['responses']
    upload_error_schema = upload_responses['415']['content']['application/json']['schema']
    assert set(upload_error_schema['required']) == {'detail', 'code'}
    assert set(upload_error_schema['properties']) == {'detail', 'code'}

    delete_responses = schema['paths']['/api/v1/media/assets/{media_id}']['delete']['responses']
    assert '404' in delete_responses
    assert '503' in delete_responses


def test_media_upload_rejects_disallowed_mime_type(
    migrated_database: dict[str, str],
    apply_runtime_env,
    bootstrap_payload: dict[str, str],
    tmp_path: Path,
) -> None:
    """Verify uploads fail when the sniffed MIME type is not allowed by settings.

    Args:
        migrated_database: Environment values for the migrated test database.
        apply_runtime_env: Runtime environment helper fixture.
        bootstrap_payload: Bootstrap request payload.
        tmp_path: Pytest temporary directory fixture.

    Returns:
        None.

    Raises:
        None.
    """

    _ = migrated_database
    media_root = tmp_path / 'media-root-disallowed'
    apply_runtime_env(
        {
            'PRAGMA_MEDIA_ROOT': str(media_root),
            'PRAGMA_MEDIA_MAX_UPLOAD_BYTES': '1048576',
            'PRAGMA_MEDIA_ALLOWED_MIME_TYPES': 'image/jpeg',
        }
    )

    with TestClient(create_app()) as client:
        headers = {**_auth_headers(client, bootstrap_payload), 'Content-Type': 'image/png'}
        response = client.post(
            '/api/v1/media/assets?filename=hero-image.png',
            headers=headers,
            content=_PNG_1X1,
        )

    assert response.status_code == 415
    assert response.json() == {
        'detail': 'Uploaded media type is not allowed by configuration',
        'code': 'MEDIA_TYPE_DISALLOWED',
    }


def test_media_upload_rejects_empty_body(
    media_client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify media uploads reject empty request bodies.

    Args:
        media_client: FastAPI test client configured for media tests.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = {**_auth_headers(media_client, bootstrap_payload), 'Content-Type': 'image/png'}

    response = media_client.post(
        '/api/v1/media/assets?filename=empty.png',
        headers=headers,
        content=b'',
    )

    assert response.status_code == 400
    assert response.json() == {
        'detail': 'Upload body is empty',
        'code': 'MEDIA_UPLOAD_EMPTY',
    }


def test_media_upload_rejects_payload_too_large(
    media_client: TestClient,
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify media uploads enforce the configured payload-size limit.

    Args:
        media_client: FastAPI test client configured for media tests.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    headers = {**_auth_headers(media_client, bootstrap_payload), 'Content-Type': 'image/png'}

    response = media_client.post(
        '/api/v1/media/assets?filename=too-large.png',
        headers=headers,
        content=b'0' * 1_048_577,
    )

    assert response.status_code == 413
    assert response.json() == {
        'detail': 'Upload exceeds the configured size limit',
        'code': 'MEDIA_UPLOAD_TOO_LARGE',
    }


def test_media_upload_rejects_oversized_content_length_before_service(
    small_upload_limit_media_client: TestClient,
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify oversized Content-Length is rejected before media service work.

    Args:
        small_upload_limit_media_client: FastAPI test client with a small media limit.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    headers = {
        **_auth_headers(small_upload_limit_media_client, bootstrap_payload),
        'Content-Type': 'image/png',
        'Content-Length': '17',
    }
    create_calls: list[object] = []

    def _record_create_media_asset(**kwargs) -> object:
        create_calls.append(kwargs)
        raise AssertionError('create_media_asset must not run for oversized uploads')

    monkeypatch.setattr('pragma.media.router.create_media_asset', _record_create_media_asset)

    response = small_upload_limit_media_client.post(
        '/api/v1/media/assets?filename=declared-too-large.png',
        headers=headers,
        content=b'',
    )

    assert response.status_code == 413
    assert response.json() == {
        'detail': 'Upload exceeds the configured size limit',
        'code': 'MEDIA_UPLOAD_TOO_LARGE',
    }
    assert create_calls == []


def test_media_upload_rejects_streaming_oversize_before_service(
    small_upload_limit_media_client: TestClient,
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify streamed oversized uploads are rejected before media service work.

    Args:
        small_upload_limit_media_client: FastAPI test client with a small media limit.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    headers = {
        **_auth_headers(small_upload_limit_media_client, bootstrap_payload),
        'Content-Type': 'image/png',
    }
    create_calls: list[object] = []

    def _record_create_media_asset(**kwargs) -> object:
        create_calls.append(kwargs)
        raise AssertionError('create_media_asset must not run for oversized uploads')

    def _oversized_body() -> Iterator[bytes]:
        yield b'0' * 8
        yield b'1' * 8
        yield b'2'

    monkeypatch.setattr('pragma.media.router.create_media_asset', _record_create_media_asset)

    response = small_upload_limit_media_client.post(
        '/api/v1/media/assets?filename=stream-too-large.png',
        headers=headers,
        content=_oversized_body(),
    )

    assert response.status_code == 413
    assert response.json() == {
        'detail': 'Upload exceeds the configured size limit',
        'code': 'MEDIA_UPLOAD_TOO_LARGE',
    }
    assert create_calls == []


def test_media_content_returns_not_found_when_file_missing(
    media_client: TestClient,
    bootstrap_payload: dict[str, str],
    media_root: Path,
) -> None:
    """Verify content reads fail with MEDIA_FILE_MISSING when bytes are absent.

    Args:
        media_client: FastAPI test client configured for media tests.
        bootstrap_payload: Bootstrap request payload.
        media_root: Isolated local media root.

    Returns:
        None.

    Raises:
        None.
    """

    headers = {**_auth_headers(media_client, bootstrap_payload), 'Content-Type': 'image/png'}
    upload_response = media_client.post(
        '/api/v1/media/assets?filename=missing-bytes.png',
        headers=headers,
        content=_PNG_1X1,
    )
    assert upload_response.status_code == 201

    uploaded = upload_response.json()
    stored_path = media_root / uploaded['storage_key']
    stored_path.unlink()

    response = media_client.get(
        f"/api/v1/media/assets/{uploaded['id']}/content",
        headers={'Authorization': headers['Authorization']},
    )

    assert response.status_code == 404
    assert response.json() == {
        'detail': 'Stored media bytes are missing',
        'code': 'MEDIA_FILE_MISSING',
    }


def test_media_upload_rejects_symlink_escape_attempt(
    media_client: TestClient,
    bootstrap_payload: dict[str, str],
    media_root: Path,
) -> None:
    """Verify local storage rejects upload paths that escape the media root.

    Args:
        media_client: FastAPI test client configured for media tests.
        bootstrap_payload: Bootstrap request payload.
        media_root: Isolated local media root.

    Returns:
        None.

    Raises:
        None.
    """

    media_root.mkdir(parents=True, exist_ok=True)
    outside_root = media_root.parent / 'outside-root'
    outside_root.mkdir()
    year_partition = media_root / f'{utc_now():%Y}'

    try:
        year_partition.symlink_to(outside_root, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('Symlink creation is not supported on this test platform')

    headers = {**_auth_headers(media_client, bootstrap_payload), 'Content-Type': 'image/png'}
    response = media_client.post(
        '/api/v1/media/assets?filename=symlink-escape.png',
        headers=headers,
        content=_PNG_1X1,
    )

    assert response.status_code == 503
    assert response.json() == {
        'detail': 'Resolved media path escaped the configured storage root',
        'code': 'MEDIA_STORAGE_PATH_INVALID',
    }
    assert list(outside_root.iterdir()) == []


def test_media_delete_metadata_failure_does_not_delete_storage(
    media_client: TestClient,
    bootstrap_payload: dict[str, str],
    media_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify metadata delete failures do not remove stored media bytes.

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

    headers = {**_auth_headers(media_client, bootstrap_payload), 'Content-Type': 'image/png'}
    upload_response = media_client.post(
        '/api/v1/media/assets?filename=metadata-delete-failure.png',
        headers=headers,
        content=_PNG_1X1,
    )
    assert upload_response.status_code == 201

    uploaded = upload_response.json()
    stored_path = media_root / uploaded['storage_key']
    delete_calls: list[str] = []

    def _record_delete(self, storage_key: str) -> None:
        _ = self
        delete_calls.append(storage_key)

    def _fail_metadata_delete(connection, media_id) -> None:
        _ = connection, media_id
        raise psycopg.OperationalError('metadata delete failed')

    monkeypatch.setattr(
        'pragma.media.storage.LocalFilesystemStorageBackend.delete',
        _record_delete,
    )
    monkeypatch.setattr(
        'pragma.media.service.media_queries.delete_media',
        _fail_metadata_delete,
    )

    delete_response = media_client.delete(
        f"/api/v1/media/assets/{uploaded['id']}",
        headers={'Authorization': headers['Authorization']},
    )

    assert delete_response.status_code == 503
    assert delete_response.json() == {
        'detail': 'Unable to delete the requested media asset',
        'code': 'MEDIA_DELETE_FAILED',
    }
    assert delete_calls == []
    assert stored_path.exists()

    detail_response = media_client.get(
        f"/api/v1/media/assets/{uploaded['id']}",
        headers={'Authorization': headers['Authorization']},
    )
    assert detail_response.status_code == 200


def test_media_delete_logs_storage_cleanup_failures_after_metadata_delete(
    media_client: TestClient,
    bootstrap_payload: dict[str, str],
    media_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify cleanup failures do not restore deleted metadata.

    Args:
        media_client: FastAPI test client configured for media tests.
        bootstrap_payload: Bootstrap request payload.
        media_root: Isolated local media root.
        monkeypatch: Pytest monkeypatch fixture.
        caplog: Pytest log capture fixture.

    Returns:
        None.

    Raises:
        None.
    """

    headers = {**_auth_headers(media_client, bootstrap_payload), 'Content-Type': 'image/png'}
    upload_response = media_client.post(
        '/api/v1/media/assets?filename=cleanup-failure.png',
        headers=headers,
        content=_PNG_1X1,
    )
    assert upload_response.status_code == 201

    uploaded = upload_response.json()
    stored_path = media_root / uploaded['storage_key']
    delete_calls: list[str] = []

    def _fail_delete(self, storage_key: str) -> None:
        _ = self
        delete_calls.append(storage_key)
        raise StorageError(
            detail='Unable to delete media bytes from local storage',
            code='MEDIA_STORAGE_DELETE_FAILED',
        )

    monkeypatch.setattr(
        'pragma.media.storage.LocalFilesystemStorageBackend.delete',
        _fail_delete,
    )
    service_logger = logging.getLogger('pragma.media.service')
    monkeypatch.setattr(service_logger, 'disabled', False)

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger='pragma.media.service'):
        delete_response = media_client.delete(
            f"/api/v1/media/assets/{uploaded['id']}",
            headers={'Authorization': headers['Authorization']},
        )

    assert delete_response.status_code == 204
    assert delete_calls == [uploaded['storage_key']]
    assert stored_path.exists()
    assert any(
        record.name == 'pragma.media.service'
        and record.levelno == logging.WARNING
        and record.getMessage() == 'Failed to clean up deleted media bytes'
        for record in caplog.records
    )

    detail_response = media_client.get(
        f"/api/v1/media/assets/{uploaded['id']}",
        headers={'Authorization': headers['Authorization']},
    )
    assert detail_response.status_code == 404
    assert detail_response.json() == {
        'detail': 'Media asset not found',
        'code': 'MEDIA_NOT_FOUND',
    }
