# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Theme administration API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from pragma.auth.dependencies import get_current_user, require_permission
from pragma.auth.permissions import PERMISSION_THEMES_MANAGE
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool
from pragma.themes.models import ThemeSettingsResponse, ThemeSettingsUpdateRequest
from pragma.themes.runtime import ThemeRuntime
from pragma.themes.service import (
    get_theme_settings_snapshot,
    reset_theme_settings_snapshot,
    update_theme_settings_snapshot,
)

router = APIRouter(prefix='/themes', tags=['themes'], dependencies=[Depends(get_current_user)])

_ERROR_RESPONSE_SCHEMA = {
    'type': 'object',
    'required': ['detail', 'code'],
    'properties': {
        'detail': {'type': 'string'},
        'code': {'type': 'string'},
    },
}

_THEME_ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {
        'description': 'Theme request is invalid',
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
        'description': 'Theme storage is unavailable',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}


def get_admin_theme_runtime(request: Request) -> ThemeRuntime:
    """Return the initialized theme runtime from application state."""

    return request.app.state.theme_runtime


@router.get('', response_model=ThemeSettingsResponse, responses=_THEME_ERROR_RESPONSES)
def list_themes(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    runtime: Annotated[ThemeRuntime, Depends(get_admin_theme_runtime)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_THEMES_MANAGE))
    ],
) -> ThemeSettingsResponse:
    """Return discovered themes and active/default design settings."""

    _ = current_user
    return get_theme_settings_snapshot(storage, runtime)


@router.put('/settings', response_model=ThemeSettingsResponse, responses=_THEME_ERROR_RESPONSES)
def update_theme_settings(
    payload: ThemeSettingsUpdateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    runtime: Annotated[ThemeRuntime, Depends(get_admin_theme_runtime)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_THEMES_MANAGE))
    ],
) -> ThemeSettingsResponse:
    """Update the active theme id and safe design settings."""

    return update_theme_settings_snapshot(storage, runtime, payload, current_user)


@router.post(
    '/settings/reset',
    response_model=ThemeSettingsResponse,
    responses=_THEME_ERROR_RESPONSES,
)
def reset_theme_settings(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    runtime: Annotated[ThemeRuntime, Depends(get_admin_theme_runtime)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_THEMES_MANAGE))
    ],
) -> ThemeSettingsResponse:
    """Reset persisted theme settings to environment/default behavior."""

    return reset_theme_settings_snapshot(storage, runtime, current_user)
