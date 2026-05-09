# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Pydantic models for AI-provider settings and operations."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AIProvider(StrEnum):
    """Supported provider keys for AI integrations."""

    VOYAGE = 'voyage'
    OPENAI = 'openai'
    OPENAI_COMPATIBLE = 'openai_compatible'


class AIProviderAPIMode(StrEnum):
    """Supported provider API surfaces for generation."""

    RESPONSES = 'responses'
    CHAT_COMPLETIONS = 'chat_completions'


class AIProviderAuthMode(StrEnum):
    """Supported provider authorization modes."""

    API_KEY = 'api_key'
    OAUTH = 'oauth'


class AICapability(StrEnum):
    """Normalized provider capability flags."""

    TEXT_GENERATION = 'text_generation'
    EDITOR_ASSIST = 'editor_assist'
    SEO_ASSIST = 'seo_assist'
    EMBEDDINGS = 'embeddings'
    IMAGE_GENERATION = 'image_generation'
    STREAMING = 'streaming'
    TOOL_CALLING = 'tool_calling'


class AIProviderSecretStatus(BaseModel):
    """Non-secret provider credential status metadata."""

    model_config = ConfigDict(extra='forbid')

    configured: bool = False
    auth_mode: AIProviderAuthMode = AIProviderAuthMode.API_KEY
    last4: str | None = None
    updated_at: datetime | None = None


class AIGenerationScope(StrEnum):
    """Generation use cases with distinct permissions."""

    EDITOR = 'editor'
    SEO = 'seo'


class AIGenerationMessageRole(StrEnum):
    """Normalized generation message roles."""

    SYSTEM = 'system'
    DEVELOPER = 'developer'
    USER = 'user'
    ASSISTANT = 'assistant'


class AIGenerationMessage(BaseModel):
    """One normalized chat-style generation message."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    role: AIGenerationMessageRole
    content: str = Field(min_length=1, max_length=8000)


class AIGenerationRequest(BaseModel):
    """Normalized text-generation request for editor and SEO assist."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    scope: AIGenerationScope = AIGenerationScope.EDITOR
    input: str = Field(min_length=1, max_length=16000)
    instructions: str | None = Field(default=None, min_length=1, max_length=8000)
    messages: list[AIGenerationMessage] = Field(default_factory=list, max_length=20)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=1, le=8192)


class AIGenerationResponse(BaseModel):
    """Normalized text-generation response returned by backend adapters."""

    model_config = ConfigDict(extra='forbid')

    provider: AIProvider
    api_mode: AIProviderAPIMode
    model: str
    text: str
    finish_reason: str | None = None
    usage: dict[str, int] | None = None


class AIOAuthStatusResponse(BaseModel):
    """OAuth provider authorization status without token exposure."""

    model_config = ConfigDict(extra='forbid')

    provider: AIProvider | None = None
    supported: bool = False
    connected: bool = False
    auth_mode: AIProviderAuthMode | None = None
    reason: str


class AIOAuthStartResponse(BaseModel):
    """OAuth start response for supported providers or deterministic unsupported state."""

    model_config = ConfigDict(extra='forbid')

    supported: bool = False
    authorization_url: str | None = None
    state: str | None = None
    reason: str


class AIProviderSettingsResponse(BaseModel):
    """Serialized AI-provider settings for admin/API consumers."""

    model_config = ConfigDict(extra='forbid')

    enabled: bool = False
    provider: AIProvider | None = None
    display_name: str | None = None
    api_mode: AIProviderAPIMode = AIProviderAPIMode.CHAT_COMPLETIONS
    auth_mode: AIProviderAuthMode = AIProviderAuthMode.API_KEY
    base_url: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = Field(default=None, ge=1, le=2000)
    generation_model: str | None = None
    capabilities: list[AICapability] = Field(default_factory=list)
    request_timeout_seconds: int | None = None
    api_key_configured: bool = False
    api_key_status: AIProviderSecretStatus = Field(default_factory=AIProviderSecretStatus)
    oauth_connected: bool = False
    last_test_status: str | None = None
    last_tested_at: datetime | None = None
    updated_at: datetime | None = None
    embeddings_rebuild_required: bool = False

    @classmethod
    def from_record(
        cls, record: dict[str, Any] | None, *, embeddings_rebuild_required: bool = False
    ) -> AIProviderSettingsResponse:
        """Build response payload from the persisted singleton row."""

        if record is None:
            return cls(embeddings_rebuild_required=embeddings_rebuild_required)

        api_key = str(record.get('api_key') or '')
        auth_mode = AIProviderAuthMode(str(record.get('auth_mode') or 'api_key'))
        capabilities: list[AICapability] = []
        if record.get('embedding_model') and record.get('embedding_dimensions') is not None:
            capabilities.append(AICapability.EMBEDDINGS)
        if bool(record.get('text_generation_enabled')):
            capabilities.append(AICapability.TEXT_GENERATION)
        if bool(record.get('editor_assist_enabled')):
            capabilities.append(AICapability.EDITOR_ASSIST)
        if bool(record.get('seo_assist_enabled')):
            capabilities.append(AICapability.SEO_ASSIST)

        return cls(
            enabled=bool(record['enabled']),
            provider=(AIProvider(str(record['provider'])) if record['provider'] else None),
            display_name=(str(record['display_name']) if record.get('display_name') else None),
            api_mode=AIProviderAPIMode(str(record.get('api_mode') or 'chat_completions')),
            auth_mode=auth_mode,
            base_url=(str(record['base_url']) if record['base_url'] else None),
            embedding_model=(
                str(record['embedding_model']) if record['embedding_model'] else None
            ),
            embedding_dimensions=(
                int(record['embedding_dimensions'])
                if record.get('embedding_dimensions') is not None
                else None
            ),
            generation_model=(
                str(record['generation_model']) if record.get('generation_model') else None
            ),
            capabilities=capabilities,
            request_timeout_seconds=(
                int(record['request_timeout_seconds'])
                if record['request_timeout_seconds'] is not None
                else None
            ),
            api_key_configured=bool(api_key),
            api_key_status=AIProviderSecretStatus(
                configured=bool(api_key),
                auth_mode=auth_mode,
                last4=(api_key[-4:] if api_key else None),
                updated_at=record['updated_at'],
            ),
            oauth_connected=False,
            last_test_status=(
                str(record['last_test_status']) if record.get('last_test_status') else None
            ),
            last_tested_at=record.get('last_tested_at'),
            updated_at=record['updated_at'],
            embeddings_rebuild_required=embeddings_rebuild_required,
        )


class AIProviderSettingsUpdateRequest(BaseModel):
    """Update payload for the provider-settings singleton."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    enabled: bool = False
    provider: AIProvider | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    api_mode: AIProviderAPIMode = AIProviderAPIMode.CHAT_COMPLETIONS
    auth_mode: AIProviderAuthMode = AIProviderAuthMode.API_KEY
    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    embedding_model: str | None = Field(default=None, min_length=1, max_length=200)
    embedding_dimensions: int | None = Field(default=None, ge=1, le=2000)
    generation_model: str | None = Field(default=None, min_length=1, max_length=200)
    text_generation_enabled: bool = False
    editor_assist_enabled: bool = False
    seo_assist_enabled: bool = False
    request_timeout_seconds: int = Field(default=15, ge=1, le=120)
    api_key: str | None = Field(default=None, min_length=1, max_length=500)
    retain_existing_api_key: bool = False


class AIProviderTestRequest(BaseModel):
    """Input payload for validating configured provider connectivity."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    query_text: str = Field(default='semantic search healthcheck', min_length=1, max_length=500)


class AIProviderTestResponse(BaseModel):
    """Response payload for provider connectivity checks."""

    model_config = ConfigDict(extra='forbid')

    provider: AIProvider
    embedding_model: str
    embedding_dimensions: int = Field(ge=1)


class AISearchEmbeddingRebuildRequest(BaseModel):
    """Input payload for explicit search-embedding rebuild runs."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    batch_size: int = Field(default=20, ge=1, le=100)
    max_documents: int = Field(default=200, ge=1, le=5000)
    content_type_slug: str | None = Field(default=None, min_length=1, max_length=160)
    force: bool = False


class AISearchEmbeddingRebuildResponse(BaseModel):
    """Result payload for search-embedding rebuild runs."""

    model_config = ConfigDict(extra='forbid')

    attempted: int = Field(ge=0)
    embedded: int = Field(ge=0)
    failed: int = Field(ge=0)
    failed_entry_ids: list[str] = Field(default_factory=list)
