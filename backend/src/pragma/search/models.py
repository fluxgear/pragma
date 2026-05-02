# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Pydantic models for Pragma search APIs.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_SEARCH_LIMIT = 100
MAX_SEARCH_OFFSET = 9_900
MAX_SEARCH_RANKING_CANDIDATES = MAX_SEARCH_LIMIT + MAX_SEARCH_OFFSET
type SearchStrategy = Literal['keyword', 'fuzzy', 'vector']


class SearchMode(StrEnum):
    """Supported search execution modes.

    Args:
        StrEnum: String enum base class.

    Returns:
        None.

    Raises:
        None.
    """

    AUTO = 'auto'
    KEYWORD = 'keyword'
    FUZZY = 'fuzzy'
    VECTOR = 'vector'
    HYBRID = 'hybrid'


class SearchQueryParams(BaseModel):
    """Query parameters for public search endpoints.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=20, gt=0, le=MAX_SEARCH_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_SEARCH_OFFSET)
    content_type_slug: str | None = Field(default=None, min_length=1, max_length=160)
    mode: SearchMode = SearchMode.AUTO
    query_embedding: list[float] | None = Field(default=None, min_length=1, max_length=4096)

    @field_validator('query_embedding')
    @classmethod
    def validate_query_embedding(
        cls, value: list[float] | None
    ) -> list[float] | None:
        """Validate optional query-embedding values.

        Args:
            value: Optional query embedding supplied by the caller.

        Returns:
            list[float] | None: Validated embedding values.

        Raises:
            ValueError: If any vector element is not finite.
        """

        if value is None:
            return None
        if any(not math.isfinite(item) for item in value):
            raise ValueError('query_embedding must contain only finite floats')
        return value


class SearchEntryResponse(BaseModel):
    """Serialized search-result entry.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    id: UUID
    content_type_slug: str
    slug: str
    title: str
    excerpt: str
    published_at: datetime

    @classmethod
    def from_record(
        cls, record: Mapping[str, Any], excerpt: str
    ) -> SearchEntryResponse:
        """Build a search-result response from a storage-layer record.

        Args:
            record: Search-document record returned by the storage layer.
            excerpt: Plain-text excerpt derived for the result row.

        Returns:
            SearchEntryResponse: Serialized search-result payload.

        Raises:
            ValidationError: If record fields are invalid.
        """

        return cls(
            id=record['id'],
            content_type_slug=str(record['content_type_slug']),
            slug=str(record['slug']),
            title=str(record['title']),
            excerpt=excerpt,
            published_at=record['published_at'],
        )


class SearchQueryResponse(BaseModel):
    """Paginated public-search response payload.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    items: list[SearchEntryResponse]
    total: int
    limit: int
    offset: int
    query: str
    mode_requested: SearchMode
    mode_applied: SearchMode
    applied_strategies: list[SearchStrategy]
    semantic_diagnostics: list[str] = Field(default_factory=list)
