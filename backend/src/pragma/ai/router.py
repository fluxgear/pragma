# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""AI-provider API routes for Pragma."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from pragma.ai.models import (
    AIGenerationRequest,
    AIGenerationResponse,
    AIGenerationScope,
    AIOAuthStartResponse,
    AIOAuthStatusResponse,
    AIProviderSettingsResponse,
    AIProviderSettingsUpdateRequest,
    AIProviderTestRequest,
    AIProviderTestResponse,
    AISearchEmbeddingRebuildRequest,
    AISearchEmbeddingRebuildResponse,
)
from pragma.ai.service import (
    disconnect_ai_oauth,
    generate_ai_text,
    get_ai_oauth_status,
    get_ai_provider_settings_snapshot,
    rebuild_search_embeddings,
    start_ai_oauth,
    test_ai_provider_connection,
    update_ai_provider_settings_snapshot,
)
from pragma.auth.dependencies import get_current_user, require_permission
from pragma.auth.permissions import (
    PERMISSION_AI_EDITOR_ASSIST,
    PERMISSION_AI_OAUTH_MANAGE,
    PERMISSION_AI_SEO_ASSIST,
    PERMISSION_AI_SETTINGS_MANAGE,
    ensure_permission,
)
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
    """Return the persisted AI-provider settings snapshot."""

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
    """Update AI-provider settings for search and generation integrations."""

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
    """Test provider connectivity using the persisted AI settings."""

    _ = current_user
    return test_ai_provider_connection(storage, settings, payload)


@router.post(
    '/generate',
    response_model=AIGenerationResponse,
    responses=_SUPERUSER_AI_ERROR_RESPONSES,
)
def generate_ai(
    payload: AIGenerationRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[dict[str, object], Depends(get_current_user)],
) -> AIGenerationResponse:
    """Generate text through a backend-held provider adapter."""

    permission = (
        PERMISSION_AI_SEO_ASSIST
        if payload.scope is AIGenerationScope.SEO
        else PERMISSION_AI_EDITOR_ASSIST
    )
    ensure_permission(current_user, permission)
    return generate_ai_text(storage, settings, payload)


@router.get(
    '/oauth/status',
    response_model=AIOAuthStatusResponse,
    responses=_SUPERUSER_AI_ERROR_RESPONSES,
)
def get_oauth_status(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_AI_OAUTH_MANAGE))
    ],
) -> AIOAuthStatusResponse:
    """Return provider OAuth status without exposing tokens."""

    _ = current_user
    return get_ai_oauth_status(storage)


@router.post(
    '/oauth/start',
    response_model=AIOAuthStartResponse,
    responses=_SUPERUSER_AI_ERROR_RESPONSES,
)
def start_oauth(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_AI_OAUTH_MANAGE))
    ],
) -> AIOAuthStartResponse:
    """Return deterministic unsupported OAuth start response."""

    _ = current_user
    return start_ai_oauth(storage)


@router.get(
    '/oauth/callback',
    response_model=AIOAuthStatusResponse,
    responses=_SUPERUSER_AI_ERROR_RESPONSES,
)
def oauth_callback(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_AI_OAUTH_MANAGE))
    ],
) -> AIOAuthStatusResponse:
    """Return deterministic unsupported OAuth callback response."""

    _ = current_user
    return get_ai_oauth_status(storage)


@router.delete(
    '/oauth',
    response_model=AIOAuthStatusResponse,
    responses=_SUPERUSER_AI_ERROR_RESPONSES,
)
def disconnect_oauth(
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_AI_OAUTH_MANAGE))
    ],
) -> AIOAuthStatusResponse:
    """Return deterministic unsupported OAuth disconnect response."""

    _ = current_user
    return disconnect_ai_oauth(storage)


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
    """Rebuild search embeddings without touching content CRUD hooks."""

    _ = current_user
    return rebuild_search_embeddings(storage, payload, settings)
