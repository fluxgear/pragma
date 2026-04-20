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

from pragma.auth.dependencies import get_current_user
from pragma.content.models import (
    ContentEntryCreateRequest,
    ContentEntryListParams,
    ContentEntryListResponse,
    ContentEntryResponse,
    ContentEntryUpdateRequest,
    ContentTypeCreateRequest,
    ContentTypeListParams,
    ContentTypeListResponse,
    ContentTypeResponse,
    ContentTypeUpdateRequest,
)
from pragma.content.service import (
    create_content_type_record,
    create_entry_record,
    delete_content_type_record,
    delete_entry_record,
    get_content_type_record,
    get_entry_record,
    list_content_type_records,
    list_entry_records,
    update_content_type_record,
    update_entry_record,
)
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

router = APIRouter(
    prefix="/content",
    tags=["content"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/types", response_model=ContentTypeResponse, status_code=status.HTTP_201_CREATED)
def create_content_type(
    payload: ContentTypeCreateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[dict[str, object], Depends(get_current_user)],
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


@router.get("/types", response_model=ContentTypeListResponse)
def list_content_types(
    params: Annotated[ContentTypeListParams, Query()],
    storage: Annotated[DatabasePool, Depends(get_storage)],
) -> ContentTypeListResponse:
    """List content types.

    Args:
        params: Content-type list query parameters.
        storage: Initialized database pool manager.

    Returns:
        ContentTypeListResponse: Paginated content-type response.

    Raises:
        StorageError: If the storage layer fails.
    """

    return list_content_type_records(storage, params)


@router.get("/types/{content_type_id}", response_model=ContentTypeResponse)
def get_content_type(
    content_type_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
) -> ContentTypeResponse:
    """Return a single content type by identifier.

    Args:
        content_type_id: Content-type identifier.
        storage: Initialized database pool manager.

    Returns:
        ContentTypeResponse: Serialized content-type response.

    Raises:
        ContentError: If the content type does not exist.
        StorageError: If the storage layer fails.
    """

    return get_content_type_record(storage, content_type_id)


@router.put("/types/{content_type_id}", response_model=ContentTypeResponse)
def update_content_type(
    content_type_id: UUID,
    payload: ContentTypeUpdateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[dict[str, object], Depends(get_current_user)],
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


@router.delete("/types/{content_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content_type(
    content_type_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
) -> Response:
    """Delete a content type when it has no entries.

    Args:
        content_type_id: Content-type identifier.
        storage: Initialized database pool manager.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        ContentError: If the content type does not exist or has entries.
        StorageError: If the storage layer fails.
    """

    delete_content_type_record(storage, content_type_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/entries", response_model=ContentEntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: ContentEntryCreateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[dict[str, object], Depends(get_current_user)],
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


@router.get("/entries", response_model=ContentEntryListResponse)
def list_entries_for_content(
    params: Annotated[ContentEntryListParams, Query()],
    storage: Annotated[DatabasePool, Depends(get_storage)],
) -> ContentEntryListResponse:
    """List content entries.

    Args:
        params: Content-entry list query parameters.
        storage: Initialized database pool manager.

    Returns:
        ContentEntryListResponse: Paginated content-entry response.

    Raises:
        ContentError: If query filters are invalid.
        StorageError: If the storage layer fails.
    """

    return list_entry_records(storage, params)


@router.get("/entries/{entry_id}", response_model=ContentEntryResponse)
def get_entry(
    entry_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
) -> ContentEntryResponse:
    """Return a single content entry by identifier.

    Args:
        entry_id: Content-entry identifier.
        storage: Initialized database pool manager.

    Returns:
        ContentEntryResponse: Serialized content-entry response.

    Raises:
        ContentError: If the entry does not exist.
        StorageError: If the storage layer fails.
    """

    return get_entry_record(storage, entry_id)


@router.put("/entries/{entry_id}", response_model=ContentEntryResponse)
def update_entry(
    entry_id: UUID,
    payload: ContentEntryUpdateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[dict[str, object], Depends(get_current_user)],
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


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry_for_content(
    entry_id: UUID,
    storage: Annotated[DatabasePool, Depends(get_storage)],
) -> Response:
    """Delete a content entry.

    Args:
        entry_id: Content-entry identifier.
        storage: Initialized database pool manager.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        ContentError: If the entry does not exist.
        StorageError: If the storage layer fails.
    """

    delete_entry_record(storage, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
