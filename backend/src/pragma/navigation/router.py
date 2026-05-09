# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Navigation administration API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from pragma.auth.dependencies import get_current_user, require_permission
from pragma.auth.permissions import PERMISSION_NAVIGATION_MANAGE
from pragma.navigation.models import NavigationMenuReplaceRequest, NavigationMenuResponse
from pragma.navigation.service import get_primary_menu_snapshot, replace_primary_menu
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

router = APIRouter(
    prefix='/navigation',
    tags=['navigation'],
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

_NAVIGATION_ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {
        'description': 'Navigation request is invalid',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
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
        'description': 'Navigation storage is unavailable',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}


@router.get(
    '/primary',
    response_model=NavigationMenuResponse,
    responses=_NAVIGATION_ERROR_RESPONSES,
)
def get_primary_menu(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_NAVIGATION_MANAGE))
    ],
) -> NavigationMenuResponse:
    """Return the current primary navigation menu."""

    _ = current_user
    return get_primary_menu_snapshot(storage)


@router.put(
    '/primary',
    response_model=NavigationMenuResponse,
    responses=_NAVIGATION_ERROR_RESPONSES,
)
def put_primary_menu(
    payload: NavigationMenuReplaceRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_NAVIGATION_MANAGE))
    ],
) -> NavigationMenuResponse:
    """Replace the primary navigation menu items."""

    return replace_primary_menu(storage, payload, current_user)
