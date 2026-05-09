# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Content-engine API routes for Pragma.

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

from fastapi import APIRouter, Depends, Query, Response, status

from pragma.auth.dependencies import get_current_user, require_permission
from pragma.auth.permissions import (
    PERMISSION_CONTENT_ENTRIES_DELETE,
    PERMISSION_CONTENT_ENTRIES_READ,
    PERMISSION_CONTENT_ENTRIES_WRITE,
    PERMISSION_CONTENT_TYPES_MANAGE,
    PERMISSION_CONTENT_TYPES_READ,
)
from pragma.config import Settings, get_settings
from pragma.content.models import (
    ContentEntryCreateRequest,
    ContentEntryListParams,
    ContentEntryListResponse,
    ContentEntryPreviewResponse,
    ContentEntryResponse,
    ContentEntryRevisionListResponse,
    ContentEntryRevisionRestoreRequest,
    ContentEntryTransitionRequest,
    ContentEntryUpdateRequest,
    ContentTypeCreateRequest,
    ContentTypeListParams,
    ContentTypeListResponse,
    ContentTypeResponse,
    ContentTypeUpdateRequest,
)
from pragma.content.service import (
    create_content_type_record,
    create_entry_preview_record,
    create_entry_record,
    delete_content_type_record,
    delete_entry_record,
    get_content_type_record,
    get_entry_record,
    list_content_type_records,
    list_entry_records,
    list_entry_revision_records,
    publish_entry_record,
    restore_entry_revision_record,
    unpublish_entry_record,
    update_content_type_record,
    update_entry_record,
)
from pragma.errors import ApiError
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

router = APIRouter(
    prefix="/content",
    tags=["content"],
    dependencies=[Depends(get_current_user)],
)

_CONTENT_BASE_ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {
        'model': ApiError,
        'description': 'Authentication required',
    },
    status.HTTP_403_FORBIDDEN: {
        'model': ApiError,
        'description': 'Permission required',
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        'model': ApiError,
        'description': 'Request validation failed',
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        'model': ApiError,
        'description': 'Content storage is unavailable',
    },
}
_CONTENT_INVALID_REQUEST_ERROR_RESPONSES = {
    **_CONTENT_BASE_ERROR_RESPONSES,
    status.HTTP_400_BAD_REQUEST: {
        'model': ApiError,
        'description': 'Content request is invalid',
    },
}
_CONTENT_MUTATION_ERROR_RESPONSES = {
    **_CONTENT_INVALID_REQUEST_ERROR_RESPONSES,
    status.HTTP_409_CONFLICT: {
        'model': ApiError,
        'description': 'Content resource conflicts with existing data',
    },
}
_CONTENT_DETAIL_ERROR_RESPONSES = {
    **_CONTENT_BASE_ERROR_RESPONSES,
    status.HTTP_404_NOT_FOUND: {
        'model': ApiError,
        'description': 'Content resource was not found',
    },
}
_CONTENT_DETAIL_MUTATION_ERROR_RESPONSES = {
    **_CONTENT_MUTATION_ERROR_RESPONSES,
    status.HTTP_404_NOT_FOUND: {
        'model': ApiError,
        'description': 'Content resource was not found',
    },
}
_CONTENT_DELETE_TYPE_ERROR_RESPONSES = {
    **_CONTENT_DETAIL_ERROR_RESPONSES,
    status.HTTP_409_CONFLICT: {
        'model': ApiError,
        'description': 'Content type cannot be deleted while entries exist',
    },
}
_CONTENT_ENTRY_CREATE_ERROR_RESPONSES = {
    **_CONTENT_MUTATION_ERROR_RESPONSES,
    status.HTTP_404_NOT_FOUND: {
        'model': ApiError,
        'description': 'Content type was not found',
    },
}


@router.post(
    "/types",
    response_model=ContentTypeResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_CONTENT_MUTATION_ERROR_RESPONSES,
)
def create_content_type(
    payload: ContentTypeCreateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_TYPES_MANAGE))
    ],
) -> ContentTypeResponse:
    """Create a content type with its field definitions.

    Args:
        payload: Content-type creation payload.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        ContentTypeResponse: Created content-type response.

    Raises:
        ContentError: If the content-type payload is invalid.
        StorageError: If the storage layer fails.
    """

    return create_content_type_record(storage, payload, current_user)


@router.get(
    "/types",
    response_model=ContentTypeListResponse,
    responses=_CONTENT_BASE_ERROR_RESPONSES,
)
def list_content_types(
    params: Annotated[ContentTypeListParams, Query()],
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_TYPES_READ))
    ],
) -> ContentTypeListResponse:
    """List content types.

    Args:
        params: Content-type list query parameters.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        ContentTypeListResponse: Paginated content-type response.

    Raises:
        StorageError: If the storage layer fails.
    """

    _ = current_user
    return list_content_type_records(storage, params)


@router.get(
    "/types/{content_type_id}",
    response_model=ContentTypeResponse,
    responses=_CONTENT_DETAIL_ERROR_RESPONSES,
)
def get_content_type(
    content_type_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_TYPES_READ))
    ],
) -> ContentTypeResponse:
    """Return a single content type by identifier.

    Args:
        content_type_id: Content-type identifier.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        ContentTypeResponse: Serialized content-type response.

    Raises:
        ContentError: If the content type does not exist.
        StorageError: If the storage layer fails.
    """

    _ = current_user
    return get_content_type_record(storage, content_type_id)


@router.put(
    "/types/{content_type_id}",
    response_model=ContentTypeResponse,
    responses=_CONTENT_DETAIL_MUTATION_ERROR_RESPONSES,
)
def update_content_type(
    content_type_id: UUID,
    payload: ContentTypeUpdateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_TYPES_MANAGE))
    ],
) -> ContentTypeResponse:
    """Update a content type and its field definitions.

    Args:
        content_type_id: Content-type identifier.
        payload: Content-type update payload.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        ContentTypeResponse: Updated content-type response.

    Raises:
        ContentError: If the content type cannot be updated.
        StorageError: If the storage layer fails.
    """

    return update_content_type_record(storage, content_type_id, payload, current_user)


@router.delete(
    "/types/{content_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_CONTENT_DELETE_TYPE_ERROR_RESPONSES,
)
def delete_content_type(
    content_type_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_TYPES_MANAGE))
    ],
) -> Response:
    """Delete a content type when it has no entries.

    Args:
        content_type_id: Content-type identifier.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        ContentError: If the content type does not exist or has entries.
        StorageError: If the storage layer fails.
    """

    _ = current_user
    delete_content_type_record(storage, content_type_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/entries",
    response_model=ContentEntryResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_CONTENT_ENTRY_CREATE_ERROR_RESPONSES,
)
def create_entry(
    payload: ContentEntryCreateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_WRITE))
    ],
) -> ContentEntryResponse:
    """Create a content entry.

    Args:
        payload: Content-entry creation payload.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        ContentEntryResponse: Created content-entry response.

    Raises:
        ContentError: If the entry payload is invalid.
        StorageError: If the storage layer fails.
    """

    return create_entry_record(storage, payload, current_user)


@router.get(
    "/entries",
    response_model=ContentEntryListResponse,
    responses=_CONTENT_INVALID_REQUEST_ERROR_RESPONSES,
)
def list_entries_for_content(
    params: Annotated[ContentEntryListParams, Query()],
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_READ))
    ],
) -> ContentEntryListResponse:
    """List content entries.

    Args:
        params: Content-entry list query parameters.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        ContentEntryListResponse: Paginated content-entry response.

    Raises:
        ContentError: If query filters are invalid.
        StorageError: If the storage layer fails.
    """

    _ = current_user
    return list_entry_records(storage, params)


@router.get(
    "/entries/{entry_id}",
    response_model=ContentEntryResponse,
    responses=_CONTENT_DETAIL_ERROR_RESPONSES,
)
def get_entry(
    entry_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_READ))
    ],
) -> ContentEntryResponse:
    """Return a single content entry by identifier.

    Args:
        entry_id: Content-entry identifier.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        ContentEntryResponse: Serialized content-entry response.

    Raises:
        ContentError: If the entry does not exist.
        StorageError: If the storage layer fails.
    """

    _ = current_user
    return get_entry_record(storage, entry_id)


@router.put(
    "/entries/{entry_id}",
    response_model=ContentEntryResponse,
    responses=_CONTENT_DETAIL_MUTATION_ERROR_RESPONSES,
)
def update_entry(
    entry_id: UUID,
    payload: ContentEntryUpdateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_WRITE))
    ],
) -> ContentEntryResponse:
    """Update a content entry.

    Args:
        entry_id: Content-entry identifier.
        payload: Content-entry update payload.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        ContentEntryResponse: Updated content-entry response.

    Raises:
        ContentError: If the entry payload is invalid.
        StorageError: If the storage layer fails.
    """

    return update_entry_record(storage, entry_id, payload, current_user)


@router.get(
    "/entries/{entry_id}/revisions",
    response_model=ContentEntryRevisionListResponse,
    responses=_CONTENT_DETAIL_ERROR_RESPONSES,
)
def list_entry_revisions_for_content(
    entry_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_READ))
    ],
) -> ContentEntryRevisionListResponse:
    """List immutable revisions for a content entry."""

    _ = current_user
    return list_entry_revision_records(storage, entry_id)


@router.post(
    "/entries/{entry_id}/preview",
    response_model=ContentEntryPreviewResponse,
    responses=_CONTENT_DETAIL_ERROR_RESPONSES,
)
def create_entry_preview_for_content(
    entry_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_READ))
    ],
) -> ContentEntryPreviewResponse:
    """Create a short-lived signed preview URL for a content entry."""

    _ = current_user
    return create_entry_preview_record(storage, settings, entry_id)


@router.post(
    "/entries/{entry_id}/publish",
    response_model=ContentEntryResponse,
    responses=_CONTENT_DETAIL_MUTATION_ERROR_RESPONSES,
)
def publish_entry_for_content(
    entry_id: UUID,
    payload: ContentEntryTransitionRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_WRITE))
    ],
) -> ContentEntryResponse:
    """Publish a draft content entry explicitly."""

    return publish_entry_record(storage, entry_id, payload, current_user)


@router.post(
    "/entries/{entry_id}/unpublish",
    response_model=ContentEntryResponse,
    responses=_CONTENT_DETAIL_MUTATION_ERROR_RESPONSES,
)
def unpublish_entry_for_content(
    entry_id: UUID,
    payload: ContentEntryTransitionRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_WRITE))
    ],
) -> ContentEntryResponse:
    """Unpublish a published content entry explicitly."""

    return unpublish_entry_record(storage, entry_id, payload, current_user)


@router.post(
    "/entries/{entry_id}/revisions/{revision_id}/restore",
    response_model=ContentEntryResponse,
    responses=_CONTENT_DETAIL_MUTATION_ERROR_RESPONSES,
)
def restore_entry_revision_for_content(
    entry_id: UUID,
    revision_id: UUID,
    payload: ContentEntryRevisionRestoreRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_WRITE))
    ],
) -> ContentEntryResponse:
    """Restore a prior immutable revision as a new current version."""

    return restore_entry_revision_record(
        storage, entry_id, revision_id, payload, current_user
    )


@router.delete(
    "/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_CONTENT_DETAIL_ERROR_RESPONSES,
)
def delete_entry_for_content(
    entry_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_DELETE))
    ],
) -> Response:
    """Delete a content entry."""

    _ = current_user
    delete_entry_record(storage, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
