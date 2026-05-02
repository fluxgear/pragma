# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""AI-provider API routes for Pragma.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from pragma.ai.models import (
    AIProviderSettingsResponse,
    AIProviderSettingsUpdateRequest,
    AIProviderTestRequest,
    AIProviderTestResponse,
    AISearchEmbeddingRebuildRequest,
    AISearchEmbeddingRebuildResponse,
)
from pragma.ai.service import (
    get_ai_provider_settings_snapshot,
    rebuild_search_embeddings,
    test_ai_provider_connection,
    update_ai_provider_settings_snapshot,
)
from pragma.auth.dependencies import get_current_user, require_permission
from pragma.auth.permissions import PERMISSION_AI_SETTINGS_MANAGE
from pragma.config import Settings, get_settings
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

router = APIRouter(prefix='/ai', tags=['ai'], dependencies=[Depends(get_current_user)])

_ERROR_RESPONSE_SCHEMA = {
    'type': 'object',
    'required': ['detail', 'code'],
    'properties': {
        'detail': {'type': 'string'},
        'code': {'type': 'string'},
    },
}

_AUTHENTICATED_AI_ERROR_RESPONSES = {
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
        'description': 'Storage or provider services unavailable',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}

_SUPERUSER_AI_ERROR_RESPONSES = {
    **_AUTHENTICATED_AI_ERROR_RESPONSES,
    status.HTTP_400_BAD_REQUEST: {
        'description': 'AI provider settings are invalid',
        'content': {'application/json': {'schema': _ERROR_RESPONSE_SCHEMA}},
    },
}


@router.get(
    '/settings',
    response_model=AIProviderSettingsResponse,
    responses=_SUPERUSER_AI_ERROR_RESPONSES,
)
def get_ai_settings(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_AI_SETTINGS_MANAGE))
    ],
) -> AIProviderSettingsResponse:
    """Return the persisted AI-provider settings snapshot.

    Args:
        storage: Initialized database pool manager.
        current_user: Authenticated user context with AI-settings permission.

    Returns:
        AIProviderSettingsResponse: Current AI-provider settings snapshot.

    Raises:
        ConfigError: If persisted settings are invalid.
        StorageError: If PostgreSQL access fails.
    """

    _ = current_user
    return get_ai_provider_settings_snapshot(storage)


@router.put(
    '/settings',
    response_model=AIProviderSettingsResponse,
    responses=_SUPERUSER_AI_ERROR_RESPONSES,
)
def update_ai_settings(
    payload: AIProviderSettingsUpdateRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_AI_SETTINGS_MANAGE))
    ],
) -> AIProviderSettingsResponse:
    """Update AI-provider settings for semantic search integrations.

    Args:
        payload: Provider settings update payload.
        storage: Initialized database pool manager.
        settings: Application settings controlling provider URL hardening.
        current_user: Authenticated user context with AI-settings permission.

    Returns:
        AIProviderSettingsResponse: Updated AI-provider settings snapshot.

    Raises:
        ConfigError: If payload settings are invalid.
        StorageError: If PostgreSQL access fails.
    """

    return update_ai_provider_settings_snapshot(storage, settings, payload, current_user)


@router.post(
    '/settings/test',
    response_model=AIProviderTestResponse,
    responses=_SUPERUSER_AI_ERROR_RESPONSES,
)
def test_ai_settings(
    payload: AIProviderTestRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_AI_SETTINGS_MANAGE))
    ],
) -> AIProviderTestResponse:
    """Test provider connectivity using the persisted AI settings.

    Args:
        payload: Provider connectivity test payload.
        storage: Initialized database pool manager.
        settings: Application settings controlling provider URL hardening.
        current_user: Authenticated user context with AI-settings permission.

    Returns:
        AIProviderTestResponse: Provider test result payload.

    Raises:
        ConfigError: If provider settings are invalid.
        SearchError: If provider request fails.
        StorageError: If PostgreSQL access fails.
    """

    _ = current_user
    return test_ai_provider_connection(storage, settings, payload)


@router.post(
    '/search/rebuild',
    response_model=AISearchEmbeddingRebuildResponse,
    responses=_SUPERUSER_AI_ERROR_RESPONSES,
)
def rebuild_ai_embeddings(
    payload: AISearchEmbeddingRebuildRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_AI_SETTINGS_MANAGE))
    ],
) -> AISearchEmbeddingRebuildResponse:
    """Rebuild search embeddings without touching content CRUD hooks.

    Args:
        payload: Search-embedding rebuild payload.
        storage: Initialized database pool manager.
        settings: Application settings controlling provider URL hardening.
        current_user: Authenticated user context with AI-settings permission.

    Returns:
        AISearchEmbeddingRebuildResponse: Rebuild result payload.

    Raises:
        ConfigError: If provider settings are invalid.
        SearchError: If semantic embeddings are unavailable.
        StorageError: If PostgreSQL access fails.
    """

    _ = current_user
    return rebuild_search_embeddings(storage, payload, settings)
