# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Search API routes for Pragma.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from pragma.auth.dependencies import get_optional_current_user
from pragma.config import Settings, get_settings
from pragma.search.models import SearchQueryParams, SearchQueryResponse
from pragma.search.service import search_public_entries
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

router = APIRouter(
    prefix='/search',
    tags=['search'],
)

_ERROR_RESPONSE_SCHEMA = {
    'type': 'object',
    'required': ['detail', 'code'],
    'properties': {
        'detail': {'type': 'string'},
        'code': {'type': 'string'},
    },
}
_SEARCH_ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {
        'description': 'Search query or filters were invalid',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        'description': 'Request validation failed',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        'description': 'Search backend unavailable',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}


@router.get(
    '/entries',
    response_model=SearchQueryResponse,
    responses=_SEARCH_ERROR_RESPONSES,
)
def search_entries(
    params: Annotated[SearchQueryParams, Query()],
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[dict[str, object] | None, Depends(get_optional_current_user)],
) -> SearchQueryResponse:
    """Search published content entries.

    Args:
        params: Search query parameters.
        storage: Initialized database pool manager.
        settings: Application settings.
        current_user: Optional authenticated user context.

    Returns:
        SearchQueryResponse: Paginated public-search response.

    Raises:
        SearchError: If the supplied search request is invalid.
        StorageError: If PostgreSQL access fails.
    """

    return search_public_entries(
        storage,
        settings,
        params,
        allow_provider_embeddings=current_user is not None,
    )
