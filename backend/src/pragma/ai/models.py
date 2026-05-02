# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Pydantic models for AI-provider settings and operations.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AIProvider(StrEnum):
    """Supported provider keys for semantic embeddings.

    Args:
        StrEnum: String enum base class.

    Returns:
        None.

    Raises:
        None.
    """

    VOYAGE = 'voyage'
    OPENAI_COMPATIBLE = 'openai_compatible'


class AIProviderSettingsResponse(BaseModel):
    """Serialized AI-provider settings for admin/API consumers.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If record values cannot be normalized.
    """

    model_config = ConfigDict(extra='forbid')

    enabled: bool = False
    provider: AIProvider | None = None
    base_url: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = Field(default=None, ge=1, le=2000)
    request_timeout_seconds: int | None = None
    api_key_configured: bool = False
    updated_at: datetime | None = None
    embeddings_rebuild_required: bool = False

    @classmethod
    def from_record(
        cls, record: dict[str, Any] | None, *, embeddings_rebuild_required: bool = False
    ) -> AIProviderSettingsResponse:
        """Build response payload from the persisted singleton row.

        Args:
            record: Optional settings row from storage.
            embeddings_rebuild_required: Whether saved semantic contract changes
                require a rebuild after this response.

        Returns:
            AIProviderSettingsResponse: Normalized settings payload.

        Raises:
            ValueError: If an unexpected provider value is persisted.
        """

        if record is None:
            return cls(embeddings_rebuild_required=embeddings_rebuild_required)
        return cls(
            enabled=bool(record['enabled']),
            provider=(AIProvider(str(record['provider'])) if record['provider'] else None),
            base_url=(str(record['base_url']) if record['base_url'] else None),
            embedding_model=(
                str(record['embedding_model']) if record['embedding_model'] else None
            ),
            embedding_dimensions=(
                int(record['embedding_dimensions'])
                if record.get('embedding_dimensions') is not None
                else None
            ),
            request_timeout_seconds=(
                int(record['request_timeout_seconds'])
                if record['request_timeout_seconds'] is not None
                else None
            ),
            api_key_configured=bool(record['api_key']),
            updated_at=record['updated_at'],
            embeddings_rebuild_required=embeddings_rebuild_required,
        )


class AIProviderSettingsUpdateRequest(BaseModel):
    """Update payload for the provider-settings singleton.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    enabled: bool = False
    provider: AIProvider | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    embedding_model: str | None = Field(default=None, min_length=1, max_length=200)
    embedding_dimensions: int | None = Field(default=None, ge=1, le=2000)
    request_timeout_seconds: int = Field(default=15, ge=1, le=120)
    api_key: str | None = Field(default=None, min_length=1, max_length=500)
    retain_existing_api_key: bool = False


class AIProviderTestRequest(BaseModel):
    """Input payload for validating configured provider connectivity.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    query_text: str = Field(default='semantic search healthcheck', min_length=1, max_length=500)


class AIProviderTestResponse(BaseModel):
    """Response payload for provider connectivity checks.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response fields are invalid.
    """

    model_config = ConfigDict(extra='forbid')

    provider: AIProvider
    embedding_model: str
    embedding_dimensions: int = Field(ge=1)


class AISearchEmbeddingRebuildRequest(BaseModel):
    """Input payload for explicit search-embedding rebuild runs.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    batch_size: int = Field(default=20, ge=1, le=100)
    max_documents: int = Field(default=200, ge=1, le=5000)
    content_type_slug: str | None = Field(default=None, min_length=1, max_length=160)
    force: bool = False


class AISearchEmbeddingRebuildResponse(BaseModel):
    """Result payload for search-embedding rebuild runs.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If response fields are invalid.
    """

    model_config = ConfigDict(extra='forbid')

    attempted: int = Field(ge=0)
    embedded: int = Field(ge=0)
    failed: int = Field(ge=0)
    failed_entry_ids: list[str] = Field(default_factory=list)
