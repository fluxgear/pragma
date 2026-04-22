# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Pydantic models for the Pragma media library.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MediaSelection(BaseModel):
    """Selection contract for later editor integration.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    id: UUID
    filename: str
    mime_type: str
    width: int | None
    height: int | None
    alt_text: str | None
    content_url: str


class MediaAssetResponse(BaseModel):
    """Serialized media-asset response.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    id: UUID
    original_filename: str
    storage_key: str
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    alt_text: str | None
    caption: str | None
    description: str | None
    variants: dict[str, str]
    uploader_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
    content_url: str
    is_image: bool
    selection: MediaSelection

    @classmethod
    def from_record(cls, record: Mapping[str, Any], content_url: str) -> MediaAssetResponse:
        """Build a response model from a storage-layer record.

        Args:
            record: Media record returned by the storage layer.
            content_url: Authenticated API URL for the stored media bytes.

        Returns:
            MediaAssetResponse: Serialized media payload.

        Raises:
            ValidationError: If record fields are invalid.
        """

        mime_type = str(record['mime_type'])
        filename = str(record['original_filename'])
        width = record['width']
        height = record['height']
        alt_text = record['alt_text']

        return cls(
            id=record['id'],
            original_filename=filename,
            storage_key=str(record['storage_key']),
            mime_type=mime_type,
            size_bytes=int(record['size_bytes']),
            width=width,
            height=height,
            alt_text=alt_text,
            caption=record['caption'],
            description=record['description'],
            variants=dict(record['variants'] or {}),
            uploader_user_id=record['uploader_user_id'],
            created_at=record['created_at'],
            updated_at=record['updated_at'],
            content_url=content_url,
            is_image=mime_type.startswith('image/'),
            selection=MediaSelection(
                id=record['id'],
                filename=filename,
                mime_type=mime_type,
                width=width,
                height=height,
                alt_text=alt_text,
                content_url=content_url,
            ),
        )


class MediaAssetListParams(BaseModel):
    """Query parameters for media-list endpoints.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra='forbid')

    limit: int = Field(default=50, gt=0, le=100)
    offset: int = Field(default=0, ge=0)
    order_by: Literal['created_at', 'updated_at', 'original_filename', 'size_bytes'] = 'updated_at'
    mime_type: str | None = Field(default=None, min_length=1, max_length=255)


class MediaAssetListResponse(BaseModel):
    """Paginated media-asset list response.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    items: list[MediaAssetResponse]
    total: int
    limit: int
    offset: int
