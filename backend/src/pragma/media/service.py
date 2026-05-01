# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Service layer for the Pragma media library.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from psycopg import IntegrityError
from psycopg.errors import Error as PsycopgError

from pragma.auth.security import utc_now
from pragma.config import Settings
from pragma.errors import MediaError, StorageError
from pragma.media.models import MediaAssetListParams, MediaAssetListResponse, MediaAssetResponse
from pragma.media.storage import StorageBackend, StoredMedia, build_storage_backend
from pragma.storage.pool import DatabasePool
from pragma.storage.queries import media as media_queries

logger = logging.getLogger(__name__)
_JPEG_SOF_MARKERS = frozenset({
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
})


def create_media_asset(
    storage: DatabasePool,
    settings: Settings,
    data: bytes,
    declared_content_type: str | None,
    filename: str,
    alt_text: str | None,
    caption: str | None,
    description: str | None,
    current_user: dict[str, Any],
) -> MediaAssetResponse:
    """Persist a new media asset and return its API representation.

    Args:
        storage: Initialized database pool manager.
        settings: Application settings.
        data: Raw upload bytes from the request body.
        declared_content_type: Request Content-Type header value.
        filename: Client-supplied filename query parameter.
        alt_text: Optional alt text supplied by the client.
        caption: Optional caption supplied by the client.
        description: Optional description supplied by the client.
        current_user: Authenticated user context.

    Returns:
        MediaAssetResponse: Created media-asset response.

    Raises:
        MediaError: If upload validation fails.
        StorageError: If storage or metadata persistence fails.
    """

    original_filename = _validate_original_filename(filename)
    _validate_upload_bytes(data, settings)
    mime_type = _sniff_media_type(data, declared_content_type)
    if mime_type not in settings.media_allowed_mime_type_set:
        raise MediaError(
            detail='Uploaded media type is not allowed by configuration',
            code='MEDIA_TYPE_DISALLOWED',
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        )

    width, height = _extract_dimensions(data, mime_type)
    media_id = uuid4()
    created_at = utc_now()
    backend = build_storage_backend(settings)
    stored_media = backend.store(media_id, original_filename, data, mime_type, created_at)

    try:
        variants = _build_media_variants(stored_media, mime_type)
    except (MediaError, OSError, RuntimeError, ValueError):
        logger.warning(
            'Derivative generation failed; preserving original upload',
            extra={'media_id': str(media_id), 'mime_type': mime_type},
        )
        variants = {}

    try:
        with storage.connection() as connection, connection.transaction():
            record = media_queries.create_media(
                connection=connection,
                media_id=media_id,
                original_filename=original_filename,
                storage_key=stored_media.storage_key,
                mime_type=mime_type,
                size_bytes=len(data),
                width=width,
                height=height,
                alt_text=_normalize_optional_text(alt_text),
                caption=_normalize_optional_text(caption),
                description=_normalize_optional_text(description),
                variants=variants,
                uploader_user_id=current_user['id'],
                created_at=created_at,
            )
    except IntegrityError as exc:
        _cleanup_stored_media(backend, stored_media)
        raise MediaError(
            detail='A conflicting media record already exists',
            code='MEDIA_CONFLICT',
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        _cleanup_stored_media(backend, stored_media)
        raise StorageError(
            detail='Unable to store media metadata',
            code='MEDIA_CREATE_FAILED',
        ) from exc

    return MediaAssetResponse.from_record(record, _build_content_url(media_id))


def list_media_assets(
    storage: DatabasePool,
    params: MediaAssetListParams,
) -> MediaAssetListResponse:
    """Return a paginated list of media assets.

    Args:
        storage: Initialized database pool manager.
        params: Media-list query parameters.

    Returns:
        MediaAssetListResponse: Paginated media response.

    Raises:
        StorageError: If metadata lookup fails.
    """

    try:
        with storage.connection() as connection:
            total = media_queries.count_media(connection, params.mime_type)
            rows = media_queries.list_media(
                connection=connection,
                limit=params.limit,
                offset=params.offset,
                order_by=params.order_by,
                mime_type=params.mime_type,
            )
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to list media assets',
            code='MEDIA_LIST_FAILED',
        ) from exc

    return MediaAssetListResponse(
        items=[MediaAssetResponse.from_record(row, _build_content_url(row['id'])) for row in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


def get_media_asset(storage: DatabasePool, media_id: UUID) -> MediaAssetResponse:
    """Return a single media asset by identifier.

    Args:
        storage: Initialized database pool manager.
        media_id: Media asset identifier.

    Returns:
        MediaAssetResponse: Serialized media response.

    Raises:
        MediaError: If the media asset does not exist.
        StorageError: If metadata lookup fails.
    """

    try:
        with storage.connection() as connection:
            row = _get_media_row(connection=connection, media_id=media_id)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load the requested media asset',
            code='MEDIA_LOOKUP_FAILED',
        ) from exc

    return MediaAssetResponse.from_record(row, _build_content_url(media_id))


def delete_media_asset(storage: DatabasePool, settings: Settings, media_id: UUID) -> None:
    """Delete a media asset metadata record, then clean up stored bytes.

    Args:
        storage: Initialized database pool manager.
        settings: Application settings.
        media_id: Media asset identifier to delete.

    Returns:
        None.

    Raises:
        MediaError: If the media asset does not exist.
        StorageError: If metadata lookup or deletion fails.
    """

    backend = build_storage_backend(settings)

    try:
        with storage.connection() as connection, connection.transaction():
            row = _get_media_row(connection=connection, media_id=media_id)
            storage_key = str(row['storage_key'])
            media_queries.delete_media(connection, media_id)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to delete the requested media asset',
            code='MEDIA_DELETE_FAILED',
        ) from exc

    try:
        backend.delete(storage_key)
    except StorageError:
        logger.warning(
            'Failed to clean up deleted media bytes',
            extra={'media_id': str(media_id), 'storage_key': storage_key},
        )


def resolve_media_content(
    storage: DatabasePool,
    settings: Settings,
    media_id: UUID,
) -> tuple[Path, str, str]:
    """Resolve stored media bytes for authenticated download or preview.

    Args:
        storage: Initialized database pool manager.
        settings: Application settings.
        media_id: Media asset identifier.

    Returns:
        tuple[Path, str, str]: Absolute path, MIME type, and original filename.

    Raises:
        MediaError: If the media asset does not exist or bytes are missing.
        StorageError: If metadata lookup fails.
    """

    backend = build_storage_backend(settings)

    try:
        with storage.connection() as connection:
            row = _get_media_row(connection=connection, media_id=media_id)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load media bytes',
            code='MEDIA_CONTENT_LOOKUP_FAILED',
        ) from exc

    path = backend.resolve(str(row['storage_key']))
    if not path.exists():
        raise MediaError(
            detail='Stored media bytes are missing',
            code='MEDIA_FILE_MISSING',
            status_code=HTTPStatus.NOT_FOUND,
        )

    return path, str(row['mime_type']), str(row['original_filename'])


def _validate_original_filename(value: str) -> str:
    """Validate and sanitize the client-supplied original filename.

    Args:
        value: Raw filename query parameter.

    Returns:
        str: Sanitized basename suitable for metadata storage.

    Raises:
        MediaError: If the filename is blank or invalid.
    """

    candidate = Path(value).name.strip()
    if candidate in {'', '.', '..'}:
        raise MediaError(detail='Filename is required', code='MEDIA_FILENAME_INVALID')
    if len(candidate) > 255:
        raise MediaError(detail='Filename is too long', code='MEDIA_FILENAME_INVALID')
    return candidate


def _validate_upload_bytes(data: bytes, settings: Settings) -> None:
    """Validate raw upload bytes against size and emptiness rules.

    Args:
        data: Raw upload bytes.
        settings: Application settings.

    Returns:
        None.

    Raises:
        MediaError: If the upload body is empty or too large.
    """

    if not data:
        raise MediaError(detail='Upload body is empty', code='MEDIA_UPLOAD_EMPTY')
    if len(data) > settings.media_max_upload_bytes:
        raise MediaError(
            detail='Upload exceeds the configured size limit',
            code='MEDIA_UPLOAD_TOO_LARGE',
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        )


def _normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional upload metadata text values.

    Args:
        value: Optional text value supplied by the client.

    Returns:
        str | None: Trimmed text or None when blank.

    Raises:
        None.
    """

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _sniff_media_type(data: bytes, declared_content_type: str | None) -> str:
    """Determine the real media MIME type from the uploaded bytes.

    Args:
        data: Raw upload bytes.
        declared_content_type: Request Content-Type header value.

    Returns:
        str: Validated MIME type derived from the file signature.

    Raises:
        MediaError: If the bytes do not match a supported media type.
    """

    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data[:6] in {b'GIF87a', b'GIF89a'}:
        return 'image/gif'
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'

    detail = 'Uploaded bytes do not match a supported image format'
    if declared_content_type:
        detail = f'Uploaded bytes do not match a supported image format for {declared_content_type}'
    raise MediaError(
        detail=detail,
        code='MEDIA_TYPE_UNSUPPORTED',
        status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    )


def _extract_dimensions(data: bytes, mime_type: str) -> tuple[int | None, int | None]:
    """Extract image dimensions from a validated media payload.

    Args:
        data: Raw upload bytes.
        mime_type: Validated MIME type.

    Returns:
        tuple[int | None, int | None]: Image width and height when available.

    Raises:
        None.
    """

    if mime_type == 'image/png' and len(data) >= 24:
        return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
    if mime_type == 'image/gif' and len(data) >= 10:
        return int.from_bytes(data[6:8], 'little'), int.from_bytes(data[8:10], 'little')
    if mime_type == 'image/jpeg':
        return _extract_jpeg_dimensions(data)
    if mime_type == 'image/webp':
        return _extract_webp_dimensions(data)
    return None, None


def _extract_jpeg_dimensions(data: bytes) -> tuple[int | None, int | None]:
    """Extract JPEG dimensions from Start Of Frame markers.

    Args:
        data: Raw JPEG bytes.

    Returns:
        tuple[int | None, int | None]: JPEG width and height when readable.

    Raises:
        None.
    """

    index = 2
    while index < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break

        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9, 0x01}:
            continue
        if index + 2 > len(data):
            break

        segment_length = int.from_bytes(data[index:index + 2], 'big')
        if segment_length < 2 or index + segment_length > len(data):
            break
        if marker in _JPEG_SOF_MARKERS and segment_length >= 7:
            start = index + 2
            height = int.from_bytes(data[start + 1:start + 3], 'big')
            width = int.from_bytes(data[start + 3:start + 5], 'big')
            return width, height
        index += segment_length

    return None, None


def _extract_webp_dimensions(data: bytes) -> tuple[int | None, int | None]:
    """Extract WebP dimensions from supported RIFF chunk layouts.

    Args:
        data: Raw WebP bytes.

    Returns:
        tuple[int | None, int | None]: WebP width and height when readable.

    Raises:
        None.
    """

    if len(data) < 30:
        return None, None

    chunk_type = data[12:16]
    if chunk_type == b'VP8X' and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], 'little')
        height = 1 + int.from_bytes(data[27:30], 'little')
        return width, height
    if chunk_type == b'VP8L' and len(data) >= 25:
        bits = int.from_bytes(data[21:25], 'little')
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    if chunk_type == b'VP8 ' and len(data) >= 30:
        width = int.from_bytes(data[26:28], 'little') & 0x3FFF
        height = int.from_bytes(data[28:30], 'little') & 0x3FFF
        return width, height
    return None, None


def _build_media_variants(stored_media: StoredMedia, mime_type: str) -> dict[str, str]:
    """Build derivative metadata for an uploaded media asset.

    Args:
        stored_media: Saved media storage details.
        mime_type: Validated MIME type.

    Returns:
        dict[str, str]: Stored derivative metadata.

    Raises:
        RuntimeError: If derivative generation fails unexpectedly.
    """

    if not mime_type.startswith('image/'):
        return {}
    return {}


def _cleanup_stored_media(backend: StorageBackend, stored_media: StoredMedia) -> None:
    """Best-effort cleanup for orphaned stored media bytes.

    Args:
        backend: Active storage backend.
        stored_media: Stored media details to remove.

    Returns:
        None.

    Raises:
        None.
    """

    try:
        backend.delete(stored_media.storage_key)
    except StorageError:
        logger.warning(
            'Failed to clean up orphaned stored media bytes',
            extra={'storage_key': stored_media.storage_key},
        )


def _get_media_row(connection: Any, media_id: UUID) -> dict[str, Any]:
    """Load a media row or raise a structured not-found error.

    Args:
        connection: Open PostgreSQL connection.
        media_id: Media asset identifier.

    Returns:
        dict[str, Any]: Stored media row.

    Raises:
        MediaError: If the media asset does not exist.
    """

    row = media_queries.get_media_by_id(connection, media_id)
    if row is None:
        raise MediaError(
            detail='Media asset not found',
            code='MEDIA_NOT_FOUND',
            status_code=HTTPStatus.NOT_FOUND,
        )
    return row


def _build_content_url(media_id: UUID) -> str:
    """Build the authenticated API URL for stored media bytes.

    Args:
        media_id: Media asset identifier.

    Returns:
        str: Relative API URL for media content.

    Raises:
        None.
    """

    return f'/api/v1/media/assets/{media_id}/content'
