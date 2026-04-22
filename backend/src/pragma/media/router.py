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
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import FileResponse

from pragma.auth.dependencies import get_current_user
from pragma.config import Settings, get_settings
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


@router.post('/assets', response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_media_asset(
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[dict[str, object], Depends(get_current_user)],
    alt_text: Annotated[str | None, Query(max_length=255)] = None,
    caption: Annotated[str | None, Query(max_length=1000)] = None,
    description: Annotated[str | None, Query(max_length=4000)] = None,
) -> MediaAssetResponse:
    """Upload a new media asset from the raw request body.

    Args:
        request: FastAPI request carrying raw upload bytes.
        filename: Client-visible filename query parameter.
        storage: Initialized database pool manager.
        settings: Application settings.
        current_user: Authenticated user context.
        alt_text: Optional alt text supplied at upload time.
        caption: Optional caption supplied at upload time.
        description: Optional description supplied at upload time.

    Returns:
        MediaAssetResponse: Created media-asset response.

    Raises:
        MediaError: If upload validation fails.
        StorageError: If the storage layer fails.
    """

    body = await request.body()
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


@router.get('/assets', response_model=MediaAssetListResponse)
def list_media_library_assets(
    params: Annotated[MediaAssetListParams, Query()],
    storage: Annotated[DatabasePool, Depends(get_storage)],
) -> MediaAssetListResponse:
    """List stored media assets.

    Args:
        params: Media-list query parameters.
        storage: Initialized database pool manager.

    Returns:
        MediaAssetListResponse: Paginated media response.

    Raises:
        StorageError: If the storage layer fails.
    """

    return list_media_assets(storage, params)


@router.get('/assets/{media_id}', response_model=MediaAssetResponse)
def get_media_library_asset(
    media_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
) -> MediaAssetResponse:
    """Return a single media asset by identifier.

    Args:
        media_id: Media asset identifier.
        storage: Initialized database pool manager.

    Returns:
        MediaAssetResponse: Serialized media response.

    Raises:
        MediaError: If the media asset does not exist.
        StorageError: If the storage layer fails.
    """

    return get_media_asset(storage, media_id)


@router.get('/assets/{media_id}/content')
def get_media_library_content(
    media_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Return stored media bytes for authenticated preview or download.

    Args:
        media_id: Media asset identifier.
        storage: Initialized database pool manager.
        settings: Application settings.

    Returns:
        FileResponse: Authenticated file response.

    Raises:
        MediaError: If the media asset does not exist or bytes are missing.
        StorageError: If the storage layer fails.
    """

    path, mime_type, filename = resolve_media_content(storage, settings, media_id)
    return FileResponse(path=path, media_type=mime_type, filename=filename)


@router.delete('/assets/{media_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_media_library_asset(
    media_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Delete a stored media asset.

    Args:
        media_id: Media asset identifier.
        storage: Initialized database pool manager.
        settings: Application settings.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        MediaError: If the media asset does not exist.
        StorageError: If the storage layer fails.
    """

    delete_media_asset(storage, settings, media_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
