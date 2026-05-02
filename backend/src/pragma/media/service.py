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
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO
from uuid import UUID, uuid4

from mutagen import File as MutagenFile
from mutagen import MutagenError
from PIL import Image, ImageOps, UnidentifiedImageError
from psycopg import IntegrityError
from psycopg.errors import Error as PsycopgError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from pragma.auth.security import utc_now
from pragma.config import Settings
from pragma.errors import MediaError, StorageError
from pragma.media.models import MediaAssetListParams, MediaAssetListResponse, MediaAssetResponse
from pragma.media.storage import StorageBackend, StoredMedia, build_storage_backend
from pragma.storage.pool import DatabasePool
from pragma.storage.queries import media as media_queries

logger = logging.getLogger(__name__)
_UPLOAD_HEADER_READ_BYTES = 30
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

_MEDIA_KIND_BY_MIME_TYPE = {
    'application/pdf': 'document',
    'audio/mpeg': 'audio',
    'audio/ogg': 'audio',
    'audio/wav': 'audio',
    'image/gif': 'image',
    'image/jpeg': 'image',
    'image/png': 'image',
    'image/webp': 'image',
    'video/mp4': 'video',
    'video/webm': 'video',
}
_THUMBNAIL_MIME_TYPE = 'image/jpeg'
_THUMBNAIL_SIZE = (320, 320)
_VARIANT_MIME_TYPES = {'thumbnail': _THUMBNAIL_MIME_TYPE}


def create_media_asset(
    storage: DatabasePool,
    settings: Settings,
    upload_source: BinaryIO,
    size_bytes: int,
    declared_content_type: str | None,
    filename: str,
    alt_text: str | None,
    caption: str | None,
    description: str | None,
    current_user: dict[str, Any],
) -> MediaAssetResponse:
    """Persist a new media asset from a readable upload source.

    Args:
        storage: Initialized database pool manager.
        settings: Runtime settings.
        upload_source: Seekable readable upload source.
        size_bytes: Observed upload size in bytes.
        declared_content_type: Client-declared Content-Type header.
        filename: Client-supplied filename.
        alt_text: Optional accessibility alt text.
        caption: Optional display caption.
        description: Optional internal description.
        current_user: Authenticated uploader record.

    Returns:
        MediaAssetResponse: Persisted media asset response.

    Raises:
        MediaError: If upload validation fails.
        StorageError: If metadata or storage persistence fails.
    """

    original_filename = _validate_original_filename(filename)
    _validate_upload_size(size_bytes, settings)
    mime_type = _sniff_media_type(upload_source, declared_content_type)
    if mime_type not in settings.media_allowed_mime_type_set:
        raise MediaError(
            detail='Uploaded media type is not allowed by configuration',
            code='MEDIA_TYPE_DISALLOWED',
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        )

    width, height = _extract_dimensions(upload_source, mime_type)
    metadata = _extract_media_metadata(upload_source, mime_type, size_bytes)
    media_id = uuid4()
    created_at = utc_now()
    backend = build_storage_backend(settings)
    _seek_upload_start(upload_source)
    stored_media = backend.store_from_stream(
        media_id,
        original_filename,
        upload_source,
        mime_type,
        created_at,
    )

    try:
        variants = _build_media_variants(backend, stored_media, media_id, mime_type, created_at)
    except (MediaError, OSError, RuntimeError, ValueError, UnidentifiedImageError):
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
                size_bytes=size_bytes,
                width=width,
                height=height,
                alt_text=_normalize_optional_text(alt_text),
                caption=_normalize_optional_text(caption),
                description=_normalize_optional_text(description),
                variants=variants,
                metadata=metadata,
                uploader_user_id=current_user['id'],
                created_at=created_at,
            )
    except IntegrityError as exc:
        _cleanup_stored_media(backend, stored_media, variants)
        raise MediaError(
            detail='A conflicting media record already exists',
            code='MEDIA_CONFLICT',
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        _cleanup_stored_media(backend, stored_media, variants)
        raise StorageError(
            detail='Unable to store media metadata',
            code='MEDIA_CREATE_FAILED',
        ) from exc

    return _media_response_from_record(record)


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
        items=[_media_response_from_record(row) for row in rows],
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

    return _media_response_from_record(row)


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
            variants = dict(row['variants'] or {})
            media_queries.delete_media(connection, media_id)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to delete the requested media asset',
            code='MEDIA_DELETE_FAILED',
        ) from exc

    for key in [storage_key, *variants.values()]:
        try:
            backend.delete(str(key))
        except StorageError:
            logger.warning(
                'Failed to clean up deleted media bytes',
                extra={'media_id': str(media_id), 'storage_key': str(key)},
            )


def resolve_media_content(
    storage: DatabasePool,
    settings: Settings,
    media_id: UUID,
    variant_name: str | None = None,
) -> tuple[Path, str, str]:
    """Resolve stored media bytes for authenticated download or preview.

    Args:
        storage: Initialized database pool manager.
        settings: Application settings.
        media_id: Media asset identifier.
        variant_name: Optional derivative variant name.

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

    filename = str(row['original_filename'])
    mime_type = str(row['mime_type'])
    storage_key = str(row['storage_key'])
    if variant_name is not None:
        variants = dict(row['variants'] or {})
        variant_key = variants.get(variant_name)
        if variant_key is None:
            raise MediaError(
                detail='Media variant not found',
                code='MEDIA_VARIANT_NOT_FOUND',
                status_code=HTTPStatus.NOT_FOUND,
            )
        storage_key = str(variant_key)
        mime_type = _VARIANT_MIME_TYPES.get(variant_name, mime_type)
        filename = f'{Path(filename).stem}-{variant_name}{Path(storage_key).suffix}'

    path = backend.resolve(storage_key)
    if not path.exists():
        raise MediaError(
            detail='Stored media bytes are missing',
            code='MEDIA_FILE_MISSING',
            status_code=HTTPStatus.NOT_FOUND,
        )

    return path, mime_type, filename


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


def _validate_upload_size(size_bytes: int, settings: Settings) -> None:
    """Validate upload size metadata against size and emptiness rules."""

    if size_bytes <= 0:
        raise MediaError(detail='Upload body is empty', code='MEDIA_UPLOAD_EMPTY')
    if size_bytes > settings.media_max_upload_bytes:
        raise MediaError(
            detail='Upload exceeds the configured size limit',
            code='MEDIA_UPLOAD_TOO_LARGE',
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        )


def _normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional upload metadata text values."""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _seek_upload_start(upload_source: BinaryIO) -> None:
    """Seek an upload source back to its first byte."""

    try:
        upload_source.seek(0)
    except (OSError, ValueError) as exc:
        raise MediaError(
            detail='Upload source is not readable',
            code='MEDIA_UPLOAD_SOURCE_INVALID',
        ) from exc


def _read_upload_prefix(upload_source: BinaryIO, byte_count: int) -> bytes:
    """Read a bounded prefix from a seekable upload source."""

    _seek_upload_start(upload_source)
    try:
        return upload_source.read(byte_count)
    except (OSError, ValueError) as exc:
        raise MediaError(
            detail='Upload source is not readable',
            code='MEDIA_UPLOAD_SOURCE_INVALID',
        ) from exc


def _sniff_media_type(upload_source: BinaryIO, declared_content_type: str | None) -> str:
    """Determine the real media MIME type from the uploaded stream.

    Args:
        upload_source: Seekable upload source.
        declared_content_type: Optional client-declared content type.

    Returns:
        str: Trusted MIME type derived from magic bytes.

    Raises:
        MediaError: If the bytes do not match a supported format.
    """

    header = _read_upload_prefix(upload_source, 64)
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if header[:6] in {b'GIF87a', b'GIF89a'}:
        return 'image/gif'
    if len(header) >= 12 and header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp'
    if header.startswith(b'%PDF-'):
        return 'application/pdf'
    if header.startswith(b'ID3') or (
        len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
    ):
        return 'audio/mpeg'
    if len(header) >= 12 and header[:4] == b'RIFF' and header[8:12] == b'WAVE':
        return 'audio/wav'
    if header.startswith(b'OggS'):
        return 'audio/ogg'
    if len(header) >= 12 and header[4:8] == b'ftyp':
        return 'video/mp4'
    if header.startswith(b'\x1aE\xdf\xa3'):
        return 'video/webm'

    detail = 'Uploaded bytes do not match a supported media format'
    if declared_content_type:
        detail = f'Uploaded bytes do not match a supported media format for {declared_content_type}'
    raise MediaError(
        detail=detail,
        code='MEDIA_TYPE_UNSUPPORTED',
        status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    )


def _extract_dimensions(
    upload_source: BinaryIO,
    mime_type: str,
) -> tuple[int | None, int | None]:
    """Extract image dimensions from a validated media payload stream."""

    header = _read_upload_prefix(upload_source, _UPLOAD_HEADER_READ_BYTES)
    if mime_type == 'image/png' and len(header) >= 24:
        return int.from_bytes(header[16:20], 'big'), int.from_bytes(header[20:24], 'big')
    if mime_type == 'image/gif' and len(header) >= 10:
        return int.from_bytes(header[6:8], 'little'), int.from_bytes(header[8:10], 'little')
    if mime_type == 'image/jpeg':
        return _extract_jpeg_dimensions(upload_source)
    if mime_type == 'image/webp':
        return _extract_webp_dimensions(header)
    return None, None


def _extract_jpeg_dimensions(upload_source: BinaryIO) -> tuple[int | None, int | None]:
    """Extract JPEG dimensions from Start Of Frame markers."""

    _seek_upload_start(upload_source)
    if upload_source.read(2) != b'\xff\xd8':
        return None, None

    while True:
        marker_prefix = upload_source.read(1)
        if not marker_prefix:
            return None, None
        if marker_prefix != b'\xff':
            continue

        marker_data = upload_source.read(1)
        while marker_data == b'\xff':
            marker_data = upload_source.read(1)
        if not marker_data:
            return None, None

        marker = marker_data[0]
        if marker in {0xD8, 0xD9, 0x01}:
            continue

        segment_length_data = upload_source.read(2)
        if len(segment_length_data) < 2:
            return None, None

        segment_length = int.from_bytes(segment_length_data, 'big')
        if segment_length < 2:
            return None, None
        if marker in _JPEG_SOF_MARKERS and segment_length >= 7:
            dimension_data = upload_source.read(5)
            if len(dimension_data) < 5:
                return None, None
            height = int.from_bytes(dimension_data[1:3], 'big')
            width = int.from_bytes(dimension_data[3:5], 'big')
            return width, height

        upload_source.seek(segment_length - 2, 1)

def _extract_media_metadata(
    upload_source: BinaryIO,
    mime_type: str,
    size_bytes: int,
) -> dict[str, Any]:
    """Extract safe metadata from a validated upload stream.

    Args:
        upload_source: Seekable upload source.
        mime_type: Trusted MIME type.
        size_bytes: Observed upload size in bytes.

    Returns:
        dict[str, Any]: Safe metadata suitable for API responses.

    Raises:
        MediaError: If metadata extraction requires unreadable upload bytes.
    """

    metadata: dict[str, Any] = {
        'media_kind': _MEDIA_KIND_BY_MIME_TYPE.get(mime_type, 'unknown'),
        'size_bytes': size_bytes,
    }
    if mime_type == 'application/pdf':
        page_count = _extract_pdf_page_count(upload_source)
        if page_count is not None:
            metadata['page_count'] = page_count
    elif mime_type.startswith(('audio/', 'video/')):
        duration = _extract_duration_seconds(upload_source)
        if duration is not None:
            metadata['duration_seconds'] = duration
    return metadata

def _extract_pdf_page_count(upload_source: BinaryIO) -> int | None:
    """Return the number of pages in a PDF upload when readable."""

    _seek_upload_start(upload_source)
    try:
        return len(PdfReader(upload_source).pages)
    except (PdfReadError, OSError, ValueError):
        return None

def _extract_duration_seconds(upload_source: BinaryIO) -> float | None:
    """Return audio/video duration when mutagen can parse it safely."""

    _seek_upload_start(upload_source)
    try:
        media_file = MutagenFile(upload_source)
    except (MutagenError, OSError, ValueError):
        return None
    if media_file is None or media_file.info is None:
        return None
    length = getattr(media_file.info, 'length', None)
    if length is None:
        return None
    return round(float(length), 3)

def _build_thumbnail_variant(
    backend: StorageBackend,
    stored_media: StoredMedia,
    media_id: UUID,
    created_at: Any,
) -> str:
    """Create and store a JPEG thumbnail for a raster image."""

    with Image.open(stored_media.filesystem_path) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail(_THUMBNAIL_SIZE)
        if image.mode not in {'RGB', 'L'}:
            image = image.convert('RGB')
        output = BytesIO()
        image.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        thumbnail = backend.store_variant_from_stream(
            media_id=media_id,
            variant_name='thumbnail',
            source=output,
            mime_type=_THUMBNAIL_MIME_TYPE,
            created_at=created_at,
        )
    return thumbnail.storage_key


def _extract_webp_dimensions(header: bytes) -> tuple[int | None, int | None]:
    """Extract WebP dimensions from supported RIFF chunk layouts."""

    if len(header) < 30:
        return None, None

    chunk_type = header[12:16]
    if chunk_type == b'VP8X':
        width = 1 + int.from_bytes(header[24:27], 'little')
        height = 1 + int.from_bytes(header[27:30], 'little')
        return width, height
    if chunk_type == b'VP8L' and len(header) >= 25:
        bits = int.from_bytes(header[21:25], 'little')
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    if chunk_type == b'VP8 ':
        width = int.from_bytes(header[26:28], 'little') & 0x3FFF
        height = int.from_bytes(header[28:30], 'little') & 0x3FFF
        return width, height
    return None, None


def _build_media_variants(
    backend: StorageBackend,
    stored_media: StoredMedia,
    media_id: UUID,
    mime_type: str,
    created_at: Any,
) -> dict[str, str]:
    """Build derivative metadata for an uploaded media asset.

    Args:
        backend: Active media storage backend.
        stored_media: Saved original media storage details.
        media_id: Media asset identifier.
        mime_type: Validated MIME type.
        created_at: Timestamp used for derivative storage layout.

    Returns:
        dict[str, str]: Stored derivative storage keys by variant name.

    Raises:
        RuntimeError: If derivative generation fails unexpectedly.
    """

    if mime_type not in {'image/gif', 'image/jpeg', 'image/png', 'image/webp'}:
        return {}
    return {'thumbnail': _build_thumbnail_variant(backend, stored_media, media_id, created_at)}


def _cleanup_stored_media(
    backend: StorageBackend,
    stored_media: StoredMedia,
    variants: dict[str, str] | None = None,
) -> None:
    """Best-effort cleanup for orphaned stored media bytes.

    Args:
        backend: Active storage backend.
        stored_media: Stored original media details to remove.
        variants: Optional derivative storage keys to remove.

    Returns:
        None.

    Raises:
        None.
    """

    for storage_key in [stored_media.storage_key, *(variants or {}).values()]:
        try:
            backend.delete(storage_key)
        except StorageError:
            logger.warning(
                'Failed to clean up orphaned stored media bytes',
                extra={'storage_key': storage_key},
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

def _media_response_from_record(record: dict[str, Any]) -> MediaAssetResponse:
    """Build an API response while converting variant keys to authenticated URLs."""

    media_id = record['id']
    response_record = dict(record)
    variants = dict(record.get('variants') or {})
    response_record['variants'] = {
        name: _build_variant_url(media_id, name)
        for name in variants
        if name in _VARIANT_MIME_TYPES
    }
    return MediaAssetResponse.from_record(response_record, _build_content_url(media_id))

def _build_variant_url(media_id: UUID, variant_name: str) -> str:
    """Build the authenticated API URL for a stored media variant."""

    return f'/api/v1/media/assets/{media_id}/variants/{variant_name}'
