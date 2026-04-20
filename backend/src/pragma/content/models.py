# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Pydantic models for the Pragma content engine.

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
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

_FIELD_NAME_PATTERN = r"^[a-z][a-z0-9_]{1,63}$"


class ContentStatus(StrEnum):
    """Supported publish states for content entries.

    Args:
        StrEnum: String enum base class.

    Returns:
        None.

    Raises:
        None.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class _FieldDefinitionBase(BaseModel):
    """Shared configuration for content field definitions.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=64, pattern=_FIELD_NAME_PATTERN)
    label: str = Field(min_length=1, max_length=120)
    required: bool = False


class TextFieldDefinition(_FieldDefinitionBase):
    """Field definition for text-like values.

    Args:
        _FieldDefinitionBase: Shared content field definition attributes.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    kind: Literal["text", "long_text", "rich_text"]
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=1)


class IntegerFieldDefinition(_FieldDefinitionBase):
    """Field definition for integer values.

    Args:
        _FieldDefinitionBase: Shared content field definition attributes.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    kind: Literal["integer"]
    minimum: int | None = None
    maximum: int | None = None


class NumberFieldDefinition(_FieldDefinitionBase):
    """Field definition for numeric values.

    Args:
        _FieldDefinitionBase: Shared content field definition attributes.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    kind: Literal["number"]
    minimum: float | None = None
    maximum: float | None = None


class BooleanFieldDefinition(_FieldDefinitionBase):
    """Field definition for boolean values.

    Args:
        _FieldDefinitionBase: Shared content field definition attributes.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    kind: Literal["boolean"]


class DateFieldDefinition(_FieldDefinitionBase):
    """Field definition for ISO-8601 date strings.

    Args:
        _FieldDefinitionBase: Shared content field definition attributes.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    kind: Literal["date"]


class DateTimeFieldDefinition(_FieldDefinitionBase):
    """Field definition for ISO-8601 datetime strings.

    Args:
        _FieldDefinitionBase: Shared content field definition attributes.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    kind: Literal["datetime"]


class JsonFieldDefinition(_FieldDefinitionBase):
    """Field definition for arbitrary JSON values.

    Args:
        _FieldDefinitionBase: Shared content field definition attributes.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    kind: Literal["json"]


type FieldDefinitionModel = (
    TextFieldDefinition
    | IntegerFieldDefinition
    | NumberFieldDefinition
    | BooleanFieldDefinition
    | DateFieldDefinition
    | DateTimeFieldDefinition
    | JsonFieldDefinition
)
FieldDefinition = Annotated[FieldDefinitionModel, Field(discriminator="kind")]
_FIELD_DEFINITION_ADAPTER = TypeAdapter(FieldDefinition)


def parse_field_definition(data: Mapping[str, Any]) -> FieldDefinitionModel:
    """Parse a stored field-definition mapping into a typed model.

    Args:
        data: Serialized field-definition mapping.

    Returns:
        FieldDefinitionModel: Parsed field-definition model.

    Raises:
        ValidationError: If the mapping cannot be parsed.
    """

    return _FIELD_DEFINITION_ADAPTER.validate_python(dict(data))


class ContentTypeCreateRequest(BaseModel):
    """Payload for creating a content type.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    field_definitions: list[FieldDefinition] = Field(min_length=1, max_length=100)


class ContentTypeUpdateRequest(BaseModel):
    """Payload for updating a content type.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    field_definitions: list[FieldDefinition] = Field(min_length=1, max_length=100)


class ContentTypeListParams(BaseModel):
    """Query parameters for content-type list endpoints.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, gt=0, le=100)
    offset: int = Field(default=0, ge=0)
    order_by: Literal["created_at", "updated_at", "name", "slug"] = "updated_at"


class ContentTypeResponse(BaseModel):
    """Serialized content-type response.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    id: UUID
    name: str
    slug: str
    description: str | None
    field_definitions: list[FieldDefinition]
    created_by_user_id: UUID | None
    updated_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(
        cls,
        record: Mapping[str, Any],
        field_definitions: list[FieldDefinitionModel],
    ) -> ContentTypeResponse:
        """Build a response model from a storage-layer record.

        Args:
            record: Content-type record returned by the storage layer.
            field_definitions: Parsed field definitions for the content type.

        Returns:
            ContentTypeResponse: Serialized content-type payload.

        Raises:
            ValidationError: If record fields are invalid.
        """

        return cls(
            id=record["id"],
            name=str(record["name"]),
            slug=str(record["slug"]),
            description=record["description"],
            field_definitions=field_definitions,
            created_by_user_id=record["created_by_user_id"],
            updated_by_user_id=record["updated_by_user_id"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )


class ContentTypeListResponse(BaseModel):
    """Paginated content-type list response.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    items: list[ContentTypeResponse]
    total: int
    limit: int
    offset: int


class ContentEntryCreateRequest(BaseModel):
    """Payload for creating a content entry.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra="forbid")

    content_type_id: UUID
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    status: ContentStatus = ContentStatus.DRAFT
    payload: dict[str, Any]


class ContentEntryUpdateRequest(BaseModel):
    """Payload for updating a content entry.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str | None = Field(default=None, min_length=1, max_length=160)
    status: ContentStatus
    payload: dict[str, Any]


class ContentEntryListParams(BaseModel):
    """Query parameters for content-entry list endpoints.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, gt=0, le=100)
    offset: int = Field(default=0, ge=0)
    order_by: Literal["created_at", "updated_at", "published_at", "slug"] = (
        "updated_at"
    )
    content_type_id: UUID | None = None
    content_type_slug: str | None = Field(default=None, min_length=1, max_length=160)
    status: ContentStatus | None = None


class ContentEntryResponse(BaseModel):
    """Serialized content-entry response.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    id: UUID
    content_type_id: UUID
    content_type_slug: str
    slug: str
    status: ContentStatus
    payload: dict[str, Any]
    published_at: datetime | None
    created_by_user_id: UUID | None
    updated_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ContentEntryResponse:
        """Build a response model from a storage-layer record.

        Args:
            record: Content-entry record returned by the storage layer.

        Returns:
            ContentEntryResponse: Serialized content-entry payload.

        Raises:
            ValidationError: If record fields are invalid.
        """

        return cls(
            id=record["id"],
            content_type_id=record["content_type_id"],
            content_type_slug=str(record["content_type_slug"]),
            slug=str(record["slug"]),
            status=record["status"],
            payload=record["payload"],
            published_at=record["published_at"],
            created_by_user_id=record["created_by_user_id"],
            updated_by_user_id=record["updated_by_user_id"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )


class ContentEntryListResponse(BaseModel):
    """Paginated content-entry list response.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    items: list[ContentEntryResponse]
    total: int
    limit: int
    offset: int
