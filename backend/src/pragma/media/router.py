# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Media-library API routes for Pragma.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import unquote_to_bytes
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import FileResponse

from pragma.auth.dependencies import get_current_user, require_permission
from pragma.auth.permissions import (
    PERMISSION_MEDIA_ASSETS_DELETE,
    PERMISSION_MEDIA_ASSETS_READ,
    PERMISSION_MEDIA_ASSETS_UPLOAD,
)
from pragma.config import Settings, get_settings
from pragma.errors import MediaError
from pragma.media.models import MediaAssetListParams, MediaAssetListResponse, MediaAssetResponse
from pragma.media.service import (
    create_media_asset,
    delete_media_asset,
    get_media_asset,
    list_media_assets,
    resolve_media_content,
)
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

router = APIRouter(
    prefix='/media',
    tags=['media'],
    dependencies=[Depends(get_current_user)],
)

_ERROR_RESPONSE_SCHEMA = {
    'type': 'object',
    'required': ['detail', 'code'],
    'properties': {
        'detail': {'type': 'string'},
        'code': {'type': 'string'},
    },
}
_COMMON_MEDIA_ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {
        'description': 'Authentication required',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_403_FORBIDDEN: {
        'description': 'Permission required',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        'description': 'Request validation failed',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        'description': 'Storage backend unavailable',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}
_UPLOAD_MEDIA_ERROR_RESPONSES = {
    **_COMMON_MEDIA_ERROR_RESPONSES,
    status.HTTP_400_BAD_REQUEST: {
        'description': 'Upload validation failed',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_409_CONFLICT: {
        'description': 'Media conflict',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_413_CONTENT_TOO_LARGE: {
        'description': 'Upload exceeded configured size limit',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
        'description': 'Uploaded media type is unsupported or disallowed',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}
_DETAIL_MEDIA_ERROR_RESPONSES = {
    **_COMMON_MEDIA_ERROR_RESPONSES,
    status.HTTP_404_NOT_FOUND: {
        'description': 'Media asset or content was not found',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}


_UPLOAD_METADATA_HEADER_ENCODING_PREFIX = 'utf8-url:'


def _decode_upload_header_value(value: str | None, max_length: int) -> str | None:
    """Decode an upload metadata header value produced by the admin client."""

    if value is None:
        return None
    if not value.startswith(_UPLOAD_METADATA_HEADER_ENCODING_PREFIX):
        decoded_value = value
    else:
        encoded_value = value[len(_UPLOAD_METADATA_HEADER_ENCODING_PREFIX) :]
        try:
            decoded_value = unquote_to_bytes(encoded_value).decode('utf-8')
        except UnicodeDecodeError as exc:
            raise MediaError(
                detail='Upload metadata header is not valid UTF-8 percent encoding',
                code='MEDIA_METADATA_HEADER_INVALID',
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc

    if len(decoded_value) > max_length:
        raise MediaError(
            detail='Upload metadata header is too long',
            code='MEDIA_METADATA_HEADER_TOO_LONG',
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return decoded_value

def _raise_upload_too_large() -> None:
    """Raise the standard oversized media-upload error.

    Args:
        None.

    Returns:
        None.

    Raises:
        MediaError: Always raised with the media upload size-limit code.
    """

    raise MediaError(
        detail='Upload exceeds the configured size limit',
        code='MEDIA_UPLOAD_TOO_LARGE',
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
    )


async def _read_limited_upload_body(request: Request, settings: Settings) -> bytes:
    """Read raw upload bytes while enforcing the configured size limit.

    Args:
        request: FastAPI request carrying raw upload bytes.
        settings: Application settings with the media upload limit.

    Returns:
        bytes: Raw request body bytes capped by the configured limit.

    Raises:
        MediaError: If Content-Length or streamed bytes exceed the limit.
    """

    content_length = request.headers.get('content-length')
    if content_length is not None:
        normalized_content_length = content_length.strip()
        if normalized_content_length.isdecimal():
            declared_size = int(normalized_content_length)
            if declared_size > settings.media_max_upload_bytes:
                _raise_upload_too_large()

    body = bytearray()
    received_size = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        received_size += len(chunk)
        if received_size > settings.media_max_upload_bytes:
            _raise_upload_too_large()
        body.extend(chunk)

    return bytes(body)


def _resolve_upload_metadata(
    *,
    header_filename: str | None,
    query_filename: str | None,
    header_alt_text: str | None,
    query_alt_text: str | None,
    header_caption: str | None,
    query_caption: str | None,
    header_description: str | None,
    query_description: str | None,
) -> tuple[str, str | None, str | None, str | None]:
    """Resolve upload metadata from preferred headers or legacy query params."""

    decoded_header_filename = _decode_upload_header_value(header_filename, 255)
    filename = decoded_header_filename if header_filename is not None else query_filename
    if filename is None:
        raise MediaError(
            detail='Upload filename is required',
            code='MEDIA_FILENAME_REQUIRED',
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return (
        filename,
        _decode_upload_header_value(header_alt_text, 255)
        if header_alt_text is not None
        else query_alt_text,
        _decode_upload_header_value(header_caption, 1000)
        if header_caption is not None
        else query_caption,
        _decode_upload_header_value(header_description, 4000)
        if header_description is not None
        else query_description,
    )


@router.post(
    '/assets',
    response_model=MediaAssetResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_UPLOAD_MEDIA_ERROR_RESPONSES,
)
async def upload_media_asset(
    request: Request,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_MEDIA_ASSETS_UPLOAD))
    ],
    header_filename: Annotated[
        str | None,
        Header(alias='X-Pragma-Media-Filename', min_length=1, max_length=4096),
    ] = None,
    header_alt_text: Annotated[
        str | None, Header(alias='X-Pragma-Media-Alt-Text', max_length=4096)
    ] = None,
    header_caption: Annotated[
        str | None, Header(alias='X-Pragma-Media-Caption', max_length=13000)
    ] = None,
    header_description: Annotated[
        str | None, Header(alias='X-Pragma-Media-Description', max_length=50000)
    ] = None,
    query_filename: Annotated[
        str | None, Query(alias='filename', min_length=1, max_length=255)
    ] = None,
    query_alt_text: Annotated[
        str | None, Query(alias='alt_text', max_length=255)
    ] = None,
    query_caption: Annotated[
        str | None, Query(alias='caption', max_length=1000)
    ] = None,
    query_description: Annotated[
        str | None, Query(alias='description', max_length=4000)
    ] = None,
) -> MediaAssetResponse:
    """Upload a new media asset from the raw request body."""

    filename, alt_text, caption, description = _resolve_upload_metadata(
        header_filename=header_filename,
        query_filename=query_filename,
        header_alt_text=header_alt_text,
        query_alt_text=query_alt_text,
        header_caption=header_caption,
        query_caption=query_caption,
        header_description=header_description,
        query_description=query_description,
    )
    body = await _read_limited_upload_body(request, settings)
    declared_content_type = request.headers.get('content-type')
    return create_media_asset(
        storage=storage,
        settings=settings,
        data=body,
        declared_content_type=declared_content_type,
        filename=filename,
        alt_text=alt_text,
        caption=caption,
        description=description,
        current_user=dict(current_user),
    )


@router.get(
    '/assets',
    response_model=MediaAssetListResponse,
    responses=_COMMON_MEDIA_ERROR_RESPONSES,
)
def list_media_library_assets(
    params: Annotated[MediaAssetListParams, Query()],
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_MEDIA_ASSETS_READ))
    ],
) -> MediaAssetListResponse:
    """List stored media assets.

    Args:
        params: Media-list query parameters.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        MediaAssetListResponse: Paginated media response.

    Raises:
        StorageError: If the storage layer fails.
    """

    _ = current_user
    return list_media_assets(storage, params)


@router.get(
    '/assets/{media_id}',
    response_model=MediaAssetResponse,
    responses=_DETAIL_MEDIA_ERROR_RESPONSES,
)
def get_media_library_asset(
    media_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_MEDIA_ASSETS_READ))
    ],
) -> MediaAssetResponse:
    """Return a single media asset by identifier.

    Args:
        media_id: Media asset identifier.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        MediaAssetResponse: Serialized media response.

    Raises:
        MediaError: If the media asset does not exist.
        StorageError: If the storage layer fails.
    """

    _ = current_user
    return get_media_asset(storage, media_id)


@router.get(
    '/assets/{media_id}/content',
    responses=_DETAIL_MEDIA_ERROR_RESPONSES,
)
def get_media_library_content(
    media_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_MEDIA_ASSETS_READ))
    ],
) -> FileResponse:
    """Return stored media bytes for authenticated preview or download.

    Args:
        media_id: Media asset identifier.
        storage: Initialized database pool manager.
        settings: Application settings.
        current_user: Authenticated user context.

    Returns:
        FileResponse: Authenticated file response.

    Raises:
        MediaError: If the media asset does not exist or bytes are missing.
        StorageError: If the storage layer fails.
    """

    _ = current_user
    path, mime_type, filename = resolve_media_content(storage, settings, media_id)
    return FileResponse(path=path, media_type=mime_type, filename=filename)


@router.delete(
    '/assets/{media_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_DETAIL_MEDIA_ERROR_RESPONSES,
)
def delete_media_library_asset(
    media_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_MEDIA_ASSETS_DELETE))
    ],
) -> Response:
    """Delete a stored media asset.

    Args:
        media_id: Media asset identifier.
        storage: Initialized database pool manager.
        settings: Application settings.
        current_user: Authenticated user context.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        MediaError: If the media asset does not exist.
        StorageError: If the storage layer fails.
    """

    _ = current_user
    delete_media_asset(storage, settings, media_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
