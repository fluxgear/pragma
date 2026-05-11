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

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

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


class ContentSeoRobots(StrEnum):
    """Supported entry-level search indexing directives."""

    INDEX = "index"
    NOINDEX = "noindex"


class ContentRevisionAction(StrEnum):
    """Immutable content revision action labels."""

    CREATE = "create"
    UPDATE = "update"
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    RESTORE = "restore"


class ContentEntrySeoMetadata(BaseModel):
    """Authorable SEO/social metadata for a content entry."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=70)
    description: str | None = Field(default=None, max_length=320)
    canonical_url: str | None = Field(default=None, max_length=2048)
    robots: ContentSeoRobots = ContentSeoRobots.INDEX
    og_title: str | None = Field(default=None, max_length=95)
    og_description: str | None = Field(default=None, max_length=300)
    og_image: str | None = Field(default=None, max_length=2048)

    @field_validator(
        "title",
        "description",
        "canonical_url",
        "og_title",
        "og_description",
        "og_image",
        mode="before",
    )
    @classmethod
    def _empty_strings_to_none(cls, value: object) -> object:
        """Normalize empty string values to omitted metadata."""

        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("canonical_url", "og_image")
    @classmethod
    def _validate_public_url(cls, value: str | None) -> str | None:
        """Allow only relative paths or HTTP(S) URLs for SEO URL fields."""

        if value is None:
            return None
        if value.startswith("/") or value.startswith(("http://", "https://")):
            return value
        raise ValueError("must be a relative path or HTTP(S) URL")

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ContentEntrySeoMetadata:
        """Build SEO metadata from entry/revision storage columns."""

        raw_metadata = record.get("seo_metadata")
        if isinstance(raw_metadata, Mapping):
            return cls.model_validate(raw_metadata)
        return cls(
            title=record.get("seo_title"),
            description=record.get("seo_description"),
            canonical_url=record.get("seo_canonical_url"),
            robots=record.get("seo_robots") or ContentSeoRobots.INDEX,
            og_title=record.get("seo_og_title"),
            og_description=record.get("seo_og_description"),
            og_image=record.get("seo_og_image"),
        )

    def to_storage(self) -> dict[str, Any]:
        """Return JSON-serializable SEO metadata for storage snapshots."""

        return self.model_dump(mode="json")


class _FieldDefinitionBase(BaseModel):
    """Shared configuration for content field definitions.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=64, pattern=_FIELD_NAME_PATTERN)
    label: str = Field(min_length=1, max_length=120)
    required: bool = False
    help_text: str | None = Field(default=None, max_length=500)
    default_value: Any = None


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


class BlockDocumentFieldDefinition(_FieldDefinitionBase):
    """Field definition for versioned block-document values.

    Args:
        _FieldDefinitionBase: Shared content field definition attributes.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    kind: Literal["block_document"]


type FieldDefinitionModel = (
    TextFieldDefinition
    | IntegerFieldDefinition
    | NumberFieldDefinition
    | BooleanFieldDefinition
    | DateFieldDefinition
    | DateTimeFieldDefinition
    | JsonFieldDefinition
    | BlockDocumentFieldDefinition
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

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

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

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

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
    entry_count: int = Field(ge=0)
    can_delete: bool
    created_by_user_id: UUID | None
    updated_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(
        cls,
        record: Mapping[str, Any],
        field_definitions: list[FieldDefinitionModel],
        *,
        entry_count: int,
    ) -> ContentTypeResponse:
        """Build a response model from a storage-layer record.

        Args:
            record: Content-type record returned by the storage layer.
            field_definitions: Parsed field definitions for the content type.
            entry_count: Server-derived number of entries for the content type.

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
            entry_count=entry_count,
            can_delete=entry_count == 0,
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
    seo_metadata: ContentEntrySeoMetadata = Field(
        default_factory=ContentEntrySeoMetadata
    )


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
    seo_metadata: ContentEntrySeoMetadata = Field(
        default_factory=ContentEntrySeoMetadata
    )
    expected_version: int | None = Field(default=None, ge=1)


class ContentEntryAutosaveRequest(BaseModel):
    """Payload for storing the current user's entry autosave."""

    model_config = ConfigDict(extra="forbid")

    base_version: int = Field(ge=1)
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    payload: dict[str, Any]
    seo_metadata: ContentEntrySeoMetadata = Field(
        default_factory=ContentEntrySeoMetadata
    )


class ContentEntryAutosaveResponse(BaseModel):
    """Serialized current-user autosave snapshot for an entry."""

    entry_id: UUID
    user_id: UUID
    base_version: int = Field(ge=1)
    current_version: int = Field(ge=1)
    is_stale: bool
    slug: str
    payload: dict[str, Any]
    seo_metadata: ContentEntrySeoMetadata
    updated_at: datetime


class ContentEntryActivityAction(StrEnum):
    """Durable content entry activity action labels."""

    CREATE = "create"
    UPDATE = "update"
    AUTOSAVE = "autosave"
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    RESTORE = "restore"
    PREVIEW = "preview"
    DELETE = "delete"
    SCHEDULE_SET = "schedule_set"
    SCHEDULE_CANCEL = "schedule_cancel"
    SCHEDULE_EXECUTE = "schedule_execute"
    SCHEDULE_FAIL = "schedule_fail"


class ContentEntryActivityListParams(BaseModel):
    """Query parameters for content-entry activity lists."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, gt=0, le=100)
    offset: int = Field(default=0, ge=0)


class ContentEntryActivityResponse(BaseModel):
    """Serialized durable content-entry activity row."""

    id: UUID
    entry_id: UUID
    content_type_id: UUID | None
    entry_slug: str | None
    entry_version: int | None = Field(default=None, ge=1)
    action: ContentEntryActivityAction
    actor_user_id: UUID | None
    details: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ContentEntryActivityResponse:
        """Build an activity response from a storage-layer row."""

        entry_version = record.get("entry_version")
        return cls(
            id=record["id"],
            entry_id=record["entry_id"],
            content_type_id=record.get("content_type_id"),
            entry_slug=record.get("entry_slug"),
            entry_version=int(entry_version) if entry_version is not None else None,
            action=record["action"],
            actor_user_id=record.get("actor_user_id"),
            details=record.get("details") or {},
            created_at=record["created_at"],
        )


class ContentEntryActivityListResponse(BaseModel):
    """Paginated durable content-entry activity list."""

    items: list[ContentEntryActivityResponse]
    total: int
    limit: int
    offset: int


class ContentEntryScheduleAction(StrEnum):
    """Supported scheduled entry workflow actions."""

    PUBLISH = "publish"
    UNPUBLISH = "unpublish"


class ContentEntryScheduleState(StrEnum):
    """Stored states for scheduled entry workflow actions."""

    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ContentEntryScheduleRequest(BaseModel):
    """Payload for replacing pending publish/unpublish schedules."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    publish_at: datetime | None = None
    unpublish_at: datetime | None = None


class ContentEntryScheduleItemResponse(BaseModel):
    """Serialized scheduled entry workflow action."""

    id: UUID
    entry_id: UUID
    action: ContentEntryScheduleAction
    run_at: datetime
    requested_entry_version: int = Field(ge=1)
    requested_by_user_id: UUID | None
    state: ContentEntryScheduleState
    created_at: datetime
    updated_at: datetime
    executed_at: datetime | None = None
    cancelled_at: datetime | None = None
    failure_code: str | None = None
    failure_detail: str | None = None

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ContentEntryScheduleItemResponse:
        """Build a schedule item response from a storage-layer row."""

        return cls(
            id=record["id"],
            entry_id=record["entry_id"],
            action=record["action"],
            run_at=record["run_at"],
            requested_entry_version=int(record["requested_entry_version"]),
            requested_by_user_id=record.get("requested_by_user_id"),
            state=record["state"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            executed_at=record.get("executed_at"),
            cancelled_at=record.get("cancelled_at"),
            failure_code=record.get("failure_code"),
            failure_detail=record.get("failure_detail"),
        )


class ContentEntryScheduleResponse(BaseModel):
    """Pending schedule summary for a content entry."""

    entry_id: UUID
    publish: ContentEntryScheduleItemResponse | None = None
    unpublish: ContentEntryScheduleItemResponse | None = None


class ContentEntryScheduleExecutionResult(BaseModel):
    """Summary returned by the manual due-schedule executor."""

    checked: int = Field(ge=0)
    executed: int = Field(ge=0)
    failed: int = Field(ge=0)


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
    seo_metadata: ContentEntrySeoMetadata
    version: int = Field(ge=1)
    revision_number: int | None = Field(default=None, ge=1)
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

        version = int(record.get("version") or 1)
        revision_number = record.get("revision_number")
        return cls(
            id=record["id"],
            content_type_id=record["content_type_id"],
            content_type_slug=str(record["content_type_slug"]),
            slug=str(record["slug"]),
            status=record["status"],
            payload=record["payload"],
            seo_metadata=ContentEntrySeoMetadata.from_record(record),
            version=version,
            revision_number=int(revision_number) if revision_number is not None else None,
            published_at=record["published_at"],
            created_by_user_id=record["created_by_user_id"],
            updated_by_user_id=record["updated_by_user_id"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )


class ContentEntryTransitionRequest(BaseModel):
    """Payload for explicit publish/unpublish transitions."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int | None = Field(default=None, ge=1)


class ContentEntryRevisionRestoreRequest(BaseModel):
    """Payload for restoring an immutable content revision."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int | None = Field(default=None, ge=1)


class ContentEntryPreviewResponse(BaseModel):
    """Short-lived signed preview URL for a content entry."""

    entry_id: UUID
    token: str = Field(min_length=32)
    preview_url: str = Field(min_length=1)
    expires_at: datetime


class ContentEntryRevisionResponse(BaseModel):
    """Serialized immutable content-entry revision snapshot."""

    id: UUID
    entry_id: UUID
    revision_number: int = Field(ge=1)
    action: ContentRevisionAction
    slug: str
    status: ContentStatus
    payload: dict[str, Any]
    seo_metadata: ContentEntrySeoMetadata
    published_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    restore_source_revision_id: UUID | None = None

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ContentEntryRevisionResponse:
        """Build a revision response from a storage-layer row."""

        return cls(
            id=record["id"],
            entry_id=record["entry_id"],
            revision_number=int(record["revision_number"]),
            action=record["action"],
            slug=str(record["slug"]),
            status=record["status"],
            payload=record["payload"],
            seo_metadata=ContentEntrySeoMetadata.from_record(record),
            published_at=record["published_at"],
            created_by_user_id=record["created_by_user_id"],
            created_at=record["created_at"],
            restore_source_revision_id=record.get("restore_source_revision_id"),
        )


class ContentEntryRevisionListResponse(BaseModel):
    """List of immutable content-entry revisions."""

    items: list[ContentEntryRevisionResponse]


class ContentEntryListResponse(BaseModel):
    """Paginated content-entry list response.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        None.
    """

    items: list[ContentEntryResponse]
    total: int
    limit: int
    offset: int
