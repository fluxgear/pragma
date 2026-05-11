# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Service-layer logic for the Pragma content engine.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from html.parser import HTMLParser
from http import HTTPStatus
from typing import Any, cast
from uuid import UUID, uuid4

from psycopg import Error as PsycopgError
from psycopg import IntegrityError

from pragma.auth.security import utc_now
from pragma.blocks.validator import (
    BlockDocumentValidationError,
    validate_block_document,
)
from pragma.config import Settings
from pragma.content.models import (
    BlockDocumentFieldDefinition,
    BooleanFieldDefinition,
    ContentEntryActivityListParams,
    ContentEntryActivityListResponse,
    ContentEntryAutosaveRequest,
    ContentEntryAutosaveResponse,
    ContentEntryCreateRequest,
    ContentEntryListParams,
    ContentEntryListResponse,
    ContentEntryPreviewResponse,
    ContentEntryResponse,
    ContentEntryRevisionListResponse,
    ContentEntryRevisionResponse,
    ContentEntryRevisionRestoreRequest,
    ContentEntryScheduleExecutionResult,
    ContentEntryScheduleRequest,
    ContentEntryScheduleResponse,
    ContentEntrySeoMetadata,
    ContentEntryTransitionRequest,
    ContentEntryUpdateRequest,
    ContentRevisionAction,
    ContentStatus,
    ContentTypeCreateRequest,
    ContentTypeListParams,
    ContentTypeListResponse,
    ContentTypeResponse,
    ContentTypeUpdateRequest,
    DateFieldDefinition,
    DateTimeFieldDefinition,
    FieldDefinitionModel,
    IntegerFieldDefinition,
    JsonFieldDefinition,
    NumberFieldDefinition,
    TextFieldDefinition,
    parse_field_definition,
)
from pragma.errors import ContentError, SearchError, StorageError
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.content import (
    count_content_types,
    count_entries,
    count_entries_by_content_type_ids,
    count_entries_for_content_type,
    create_content_entry_revision,
    create_content_type,
    create_entry,
    delete_content_type_if_unused,
    delete_entry,
    get_content_entry_revision,
    get_content_type_by_id,
    get_content_type_by_id_for_key_share,
    get_content_type_by_id_for_update,
    get_content_type_by_slug,
    get_entry_by_id,
    get_entry_by_id_for_update,
    get_entry_by_slug,
    get_field_definitions,
    list_content_entry_revisions,
    list_content_types,
    list_entries,
    list_entries_for_content_type_validation,
    list_field_definitions,
    replace_field_definitions,
    update_content_type,
    update_entry,
)

_MAX_SLUG_LENGTH = 160
_RESERVED_FIELD_NAMES = {
    "id",
    "slug",
    "status",
    "payload",
    "published_at",
    "created_at",
    "updated_at",
    "content_type_id",
}
_TEXT_FIELD_KINDS = {"text", "long_text", "rich_text"}
_ALLOWED_RICH_TEXT_TAGS = {
    "blockquote",
    "br",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "strong",
    "ul",
}
_VOID_RICH_TEXT_TAGS = {"br", "hr"}
_MULTI_HYPHEN_PATTERN = re.compile(r"-{2,}")


class _RichTextHTMLValidator(HTMLParser):
    """Validate Pragma's restricted rich-text HTML contract.

    Args:
        HTMLParser: Standard-library HTML parser base class.

    Returns:
        None.

    Raises:
        ValueError: If the HTML fragment violates the allowed tag contract.
    """

    def __init__(self) -> None:
        """Initialize rich-text validation state.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        super().__init__(convert_charrefs=True)
        self._stack: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Validate a start tag.

        Args:
            tag: Lowercase tag name.
            attrs: Tag attribute pairs.

        Returns:
            None.

        Raises:
            ValueError: If the tag or its attributes are not allowed.
        """

        if tag not in _ALLOWED_RICH_TEXT_TAGS:
            raise ValueError(f"contains unsupported rich-text HTML tag '{tag}'")
        if attrs:
            raise ValueError(
                f"contains unsupported rich-text HTML attributes on '<{tag}>'"
            )
        if tag not in _VOID_RICH_TEXT_TAGS:
            self._stack.append(tag)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Validate a self-closing tag.

        Args:
            tag: Lowercase tag name.
            attrs: Tag attribute pairs.

        Returns:
            None.

        Raises:
            ValueError: If the tag or its attributes are not allowed.
        """

        if tag not in _VOID_RICH_TEXT_TAGS:
            raise ValueError(f"contains unsupported self-closing rich-text HTML tag '{tag}'")
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        """Validate an end tag.

        Args:
            tag: Lowercase tag name.

        Returns:
            None.

        Raises:
            ValueError: If the tag order is invalid.
        """

        if tag in _VOID_RICH_TEXT_TAGS:
            raise ValueError(f"contains an unexpected closing tag '</{tag}>'")
        if not self._stack:
            raise ValueError(f"contains an unexpected closing tag '</{tag}>'")
        expected_tag = self._stack.pop()
        if expected_tag != tag:
            raise ValueError(
                "contains mismatched rich-text HTML tags: expected "
                f"'</{expected_tag}>' before '</{tag}>'"
            )

    def handle_data(self, data: str) -> None:
        """Record text content for plain-text length checks.

        Args:
            data: Text node content.

        Returns:
            None.

        Raises:
            None.
        """

        self.text_parts.append(data)

    def handle_comment(self, data: str) -> None:
        """Reject HTML comments.

        Args:
            data: Comment payload.

        Returns:
            None.

        Raises:
            ValueError: Always, because comments are not supported.
        """

        raise ValueError("contains unsupported rich-text HTML comments")

    def handle_decl(self, decl: str) -> None:
        """Reject HTML declarations.

        Args:
            decl: Declaration payload.

        Returns:
            None.

        Raises:
            ValueError: Always, because declarations are not supported.
        """

        raise ValueError("contains unsupported rich-text HTML declarations")

    def unknown_decl(self, data: str) -> None:
        """Reject unknown HTML declarations.

        Args:
            data: Declaration payload.

        Returns:
            None.

        Raises:
            ValueError: Always, because declarations are not supported.
        """

        raise ValueError("contains unsupported rich-text HTML declarations")

    def handle_pi(self, data: str) -> None:
        """Reject processing instructions.

        Args:
            data: Processing-instruction payload.

        Returns:
            None.

        Raises:
            ValueError: Always, because processing instructions are not supported.
        """

        raise ValueError("contains unsupported rich-text processing instructions")

    def close(self) -> None:
        """Finalize parsing and reject unclosed tags.

        Args:
            None.

        Returns:
            None.

        Raises:
            ValueError: If any non-void tags remain unclosed.
        """

        super().close()
        if self._stack:
            unclosed_tag = self._stack[-1]
            raise ValueError(f"contains an unclosed rich-text HTML tag '<{unclosed_tag}>'")


def _validate_rich_text_html(value: str, field_name: str) -> tuple[str, int]:
    """Validate restricted rich-text HTML and compute plain-text length.

    Args:
        value: Raw HTML fragment from the request payload.
        field_name: Field name for structured error messages.

    Returns:
        tuple[str, int]: Original HTML plus normalized plain-text character count.

    Raises:
        ContentError: If the HTML fragment violates the rich-text contract.
    """

    parser = _RichTextHTMLValidator()

    try:
        parser.feed(value)
        parser.close()
    except ValueError as exc:
        raise ContentError(
            detail=f"Field '{field_name}' {exc}",
            code="ENTRY_FIELD_INVALID",
        ) from exc

    normalized_text = re.sub(r"\s+", " ", "".join(parser.text_parts)).strip()
    return value, len(normalized_text)


def _normalize_slug(value: str, error_code: str) -> str:
    """Normalize a slug candidate into the stored URL-safe form.

    Args:
        value: Raw slug candidate.
        error_code: Error code to use when normalization fails.

    Returns:
        str: Normalized slug.

    Raises:
        ContentError: If the slug does not contain a usable value.
    """

    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    slug = _MULTI_HYPHEN_PATTERN.sub("-", slug)
    slug = slug[:_MAX_SLUG_LENGTH].strip("-")
    if not slug:
        raise ContentError(detail="Slug must contain letters or numbers", code=error_code)
    return slug


def _slug_with_suffix(base_slug: str, suffix: int) -> str:
    """Append a numeric suffix to a slug without exceeding the max length.

    Args:
        base_slug: Base slug value.
        suffix: Numeric suffix to append.

    Returns:
        str: Slug with suffix appended.

    Raises:
        None.
    """

    suffix_value = f"-{suffix}"
    available = _MAX_SLUG_LENGTH - len(suffix_value)
    trimmed = base_slug[:available].rstrip("-")
    return f"{trimmed}{suffix_value}"


def _field_definition_to_storage_payload(
    field_definition: FieldDefinitionModel,
) -> dict[str, Any]:
    """Serialize a field definition for the storage layer.

    Args:
        field_definition: Parsed field-definition model.

    Returns:
        dict[str, Any]: Serialized storage payload.

    Raises:
        None.
    """

    dumped = field_definition.model_dump(mode="json")
    config = {
        key: value
        for key, value in dumped.items()
        if key not in {"name", "label", "kind", "required"} and value is not None
    }
    storage_kind = dumped["kind"]
    if storage_kind == "block_document":
        storage_kind = "json"
        config["kind"] = dumped["kind"]

    return {
        "name": dumped["name"],
        "label": dumped["label"],
        "kind": storage_kind,
        "required": dumped["required"],
        "config": config,
    }


def _field_definition_from_row(row: Mapping[str, Any]) -> FieldDefinitionModel:
    """Build a typed field definition from a storage row.

    Args:
        row: Storage-layer row from ``pragma_content_fields``.

    Returns:
        FieldDefinitionModel: Parsed field-definition model.

    Raises:
        ValidationError: If the row cannot be parsed.
    """

    config = cast(dict[str, Any], row["config"] or {})
    return parse_field_definition(
        {
            "name": row["name"],
            "label": row["label"],
            "kind": row["field_type"],
            "required": row["is_required"],
            **config,
        }
    )


def _field_definitions_from_rows(rows: Sequence[Mapping[str, Any]]) -> list[FieldDefinitionModel]:
    """Build typed field definitions from storage rows.

    Args:
        rows: Storage-layer rows from ``pragma_content_fields``.

    Returns:
        list[FieldDefinitionModel]: Parsed field-definition models.

    Raises:
        ValidationError: If any row cannot be parsed.
    """

    return [_field_definition_from_row(row) for row in rows]


def _field_definition_has_default(field_definition: FieldDefinitionModel) -> bool:
    """Return whether a field definition explicitly defines a default value.

    Args:
        field_definition: Parsed field definition.

    Returns:
        bool: True when ``default_value`` was supplied by API or storage config.

    Raises:
        None.
    """

    return "default_value" in field_definition.model_fields_set


def _field_definition_default_value(field_definition: FieldDefinitionModel) -> Any:
    """Return the explicit default value for a field definition.

    Args:
        field_definition: Parsed field definition.

    Returns:
        Any: Supplied default value.

    Raises:
        None.
    """

    return field_definition.default_value


def _require_user_id(current_user: Mapping[str, object]) -> UUID:
    """Return the authenticated user identifier from dependency context.

    Args:
        current_user: Authenticated user mapping.

    Returns:
        UUID: Authenticated user identifier.

    Raises:
        ContentError: If the authenticated user context is incomplete.
    """

    user_id = current_user.get("id")
    if not isinstance(user_id, UUID):
        raise ContentError(
            detail="Authenticated user context is invalid",
            code="CONTENT_AUTH_CONTEXT_INVALID",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
    return user_id


def _validate_field_definitions(field_definitions: Sequence[FieldDefinitionModel]) -> None:
    """Validate content-type field definitions with explicit domain errors.

    Args:
        field_definitions: Parsed field-definition models to validate.

    Returns:
        None.

    Raises:
        ContentError: If the field-definition set is invalid.
    """

    seen_names: set[str] = set()

    for field_definition in field_definitions:
        if field_definition.name in _RESERVED_FIELD_NAMES:
            raise ContentError(
                detail=(
                    f"Field name '{field_definition.name}' is reserved for the content system"
                ),
                code="CONTENT_FIELD_RESERVED_NAME",
            )

        if field_definition.name in seen_names:
            raise ContentError(
                detail=f"Field definition '{field_definition.name}' is duplicated",
                code="CONTENT_FIELD_DUPLICATE",
            )
        seen_names.add(field_definition.name)

        if isinstance(field_definition, TextFieldDefinition):
            if (
                field_definition.min_length is not None
                and field_definition.max_length is not None
                and field_definition.min_length > field_definition.max_length
            ):
                raise ContentError(
                    detail=(
                        f"Field '{field_definition.name}' has min_length greater than max_length"
                    ),
                    code="CONTENT_FIELD_RANGE_INVALID",
                )
        elif isinstance(field_definition, IntegerFieldDefinition | NumberFieldDefinition) and (
            field_definition.minimum is not None
            and field_definition.maximum is not None
            and field_definition.minimum > field_definition.maximum
        ):
            raise ContentError(
                detail=(
                    f"Field '{field_definition.name}' has minimum greater than maximum"
                ),
                code="CONTENT_FIELD_RANGE_INVALID",
            )

        if not _field_definition_has_default(field_definition):
            continue

        default_value = _field_definition_default_value(field_definition)
        try:
            json.dumps(default_value)
        except TypeError as exc:
            raise ContentError(
                detail=(
                    f"Field '{field_definition.name}' default_value must contain "
                    "JSON-serializable data"
                ),
                code="CONTENT_FIELD_DEFAULT_INVALID",
            ) from exc

        if field_definition.required and default_value is None:
            raise ContentError(
                detail=(
                    f"Field '{field_definition.name}' default_value is required when "
                    "the field is required"
                ),
                code="CONTENT_FIELD_DEFAULT_INVALID",
            )

        try:
            _validate_field_value(field_definition, default_value)
        except ContentError as exc:
            raise ContentError(
                detail=(
                    f"Field '{field_definition.name}' default_value is invalid: "
                    f"{exc.detail}"
                ),
                code="CONTENT_FIELD_DEFAULT_INVALID",
            ) from exc


def _validate_datetime_value(value: str, field_name: str) -> str:
    """Validate and normalize an ISO-8601 datetime string.

    Args:
        value: Raw datetime string.
        field_name: Field name for error reporting.

    Returns:
        str: Normalized datetime string.

    Raises:
        ContentError: If the value is not a valid ISO-8601 datetime string.
    """

    candidate = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ContentError(
            detail=f"Field '{field_name}' must be a valid ISO-8601 datetime string",
            code="ENTRY_FIELD_INVALID",
        ) from exc
    return parsed.isoformat()


def _validate_field_value(
    field_definition: FieldDefinitionModel,
    value: Any,
    *,
    existing_value: Any = None,
    allow_legacy_rich_text_passthrough: bool = False,
) -> Any:
    """Validate a single entry-field value against its definition.

    Args:
        field_definition: Parsed field definition.
        value: Raw field value from the entry payload.
        existing_value: Existing stored field value for update flows.
        allow_legacy_rich_text_passthrough: Whether unchanged legacy ``rich_text``
            values may bypass the strict M4 HTML validator.

    Returns:
        Any: Normalized field value ready for JSONB storage.

    Raises:
        ContentError: If the supplied value violates the field definition.
    """

    field_name = field_definition.name

    if value is None:
        if field_definition.required:
            raise ContentError(
                detail=f"Field '{field_name}' is required",
                code="ENTRY_FIELD_REQUIRED",
            )
        return None

    if isinstance(field_definition, TextFieldDefinition):
        if not isinstance(value, str):
            raise ContentError(
                detail=f"Field '{field_name}' must be a string",
                code="ENTRY_FIELD_INVALID",
            )

        normalized_value = value
        length_value = len(value)
        if field_definition.kind == "rich_text":
            if (
                allow_legacy_rich_text_passthrough
                and isinstance(existing_value, str)
                and value == existing_value
            ):
                return value
            normalized_value, length_value = _validate_rich_text_html(value, field_name)

        if field_definition.min_length is not None and length_value < field_definition.min_length:
            raise ContentError(
                detail=(
                    f"Field '{field_name}' must be at least "
                    f"{field_definition.min_length} characters"
                ),
                code="ENTRY_FIELD_INVALID",
            )
        if field_definition.max_length is not None and length_value > field_definition.max_length:
            raise ContentError(
                detail=(
                    f"Field '{field_name}' must be at most "
                    f"{field_definition.max_length} characters"
                ),
                code="ENTRY_FIELD_INVALID",
            )
        return normalized_value

    if isinstance(field_definition, IntegerFieldDefinition):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ContentError(
                detail=f"Field '{field_name}' must be an integer",
                code="ENTRY_FIELD_INVALID",
            )
        if field_definition.minimum is not None and value < field_definition.minimum:
            raise ContentError(
                detail=f"Field '{field_name}' must be at least {field_definition.minimum}",
                code="ENTRY_FIELD_INVALID",
            )
        if field_definition.maximum is not None and value > field_definition.maximum:
            raise ContentError(
                detail=f"Field '{field_name}' must be at most {field_definition.maximum}",
                code="ENTRY_FIELD_INVALID",
            )
        return value

    if isinstance(field_definition, NumberFieldDefinition):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ContentError(
                detail=f"Field '{field_name}' must be a number",
                code="ENTRY_FIELD_INVALID",
            )
        numeric_value = cast(int | float, value)
        if field_definition.minimum is not None and numeric_value < field_definition.minimum:
            raise ContentError(
                detail=f"Field '{field_name}' must be at least {field_definition.minimum}",
                code="ENTRY_FIELD_INVALID",
            )
        if field_definition.maximum is not None and numeric_value > field_definition.maximum:
            raise ContentError(
                detail=f"Field '{field_name}' must be at most {field_definition.maximum}",
                code="ENTRY_FIELD_INVALID",
            )
        return numeric_value

    if isinstance(field_definition, BooleanFieldDefinition):
        if not isinstance(value, bool):
            raise ContentError(
                detail=f"Field '{field_name}' must be a boolean",
                code="ENTRY_FIELD_INVALID",
            )
        return value

    if isinstance(field_definition, DateFieldDefinition):
        if not isinstance(value, str):
            raise ContentError(
                detail=f"Field '{field_name}' must be a date string",
                code="ENTRY_FIELD_INVALID",
            )
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ContentError(
                detail=f"Field '{field_name}' must be a valid ISO-8601 date string",
                code="ENTRY_FIELD_INVALID",
            ) from exc
        return parsed.isoformat()

    if isinstance(field_definition, DateTimeFieldDefinition):
        if not isinstance(value, str):
            raise ContentError(
                detail=f"Field '{field_name}' must be a datetime string",
                code="ENTRY_FIELD_INVALID",
            )
        return _validate_datetime_value(value, field_name)

    if isinstance(field_definition, BlockDocumentFieldDefinition):
        try:
            return validate_block_document(value)
        except BlockDocumentValidationError as exc:
            raise ContentError(
                detail=f"Field '{field_name}' block document is invalid: {exc}",
                code="ENTRY_FIELD_INVALID",
            ) from exc

    if not isinstance(field_definition, JsonFieldDefinition):
        raise ContentError(
            detail=f"Field '{field_name}' uses an unsupported field type",
            code="CONTENT_FIELD_INVALID",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    try:
        json.dumps(value)
    except TypeError as exc:
        raise ContentError(
            detail=f"Field '{field_name}' must contain JSON-serializable data",
            code="ENTRY_FIELD_INVALID",
        ) from exc
    return value


def _validate_entry_payload(
    payload: Mapping[str, Any],
    field_definitions: Sequence[FieldDefinitionModel],
    *,
    existing_payload: Mapping[str, Any] | None = None,
    legacy_rich_text_fields: set[str] | None = None,
) -> dict[str, Any]:
    """Validate an entry payload against content-type field definitions.

    Args:
        payload: Raw entry payload mapping.
        field_definitions: Parsed field definitions for the content type.
        existing_payload: Existing stored payload for update-validation flows.
        legacy_rich_text_fields: Rich-text field names allowed to preserve an
            unchanged legacy HTML value.

    Returns:
        dict[str, Any]: Normalized payload ready for JSONB storage.

    Raises:
        ContentError: If the entry payload is invalid.
    """

    field_map = {field_definition.name: field_definition for field_definition in field_definitions}
    unknown_fields = sorted(set(payload) - set(field_map))
    if unknown_fields:
        names = ', '.join(unknown_fields)
        raise ContentError(
            detail=f"Unknown field(s) for this content type: {names}",
            code="ENTRY_FIELD_UNKNOWN",
        )

    normalized_payload: dict[str, Any] = {}
    for field_definition in field_definitions:
        if field_definition.name not in payload:
            if _field_definition_has_default(field_definition):
                normalized_payload[field_definition.name] = _validate_field_value(
                    field_definition,
                    _field_definition_default_value(field_definition),
                )
                continue
            if field_definition.required:
                raise ContentError(
                    detail=f"Field '{field_definition.name}' is required",
                    code="ENTRY_FIELD_REQUIRED",
                )
            continue
        normalized_payload[field_definition.name] = _validate_field_value(
            field_definition,
            payload[field_definition.name],
            existing_value=(
                existing_payload.get(field_definition.name)
                if existing_payload is not None
                else None
            ),
            allow_legacy_rich_text_passthrough=(
                legacy_rich_text_fields is not None
                and field_definition.name in legacy_rich_text_fields
            ),
        )
    return normalized_payload


def _auto_entry_slug(
    content_type_slug: str,
    payload: Mapping[str, Any],
    field_definitions: Sequence[FieldDefinitionModel],
) -> str:
    """Build a slug candidate for an entry when no explicit slug is supplied.

    Args:
        content_type_slug: Normalized content-type slug.
        payload: Validated entry payload.
        field_definitions: Parsed field definitions for the content type.

    Returns:
        str: Auto-generated slug candidate.

    Raises:
        ContentError: If normalization fails unexpectedly.
    """

    preferred_names = ("title", "name")
    for field_name in preferred_names:
        value = payload.get(field_name)
        if isinstance(value, str) and value.strip():
            return _normalize_slug(value, "ENTRY_SLUG_INVALID")

    for field_definition in field_definitions:
        if field_definition.kind not in _TEXT_FIELD_KINDS:
            continue
        value = payload.get(field_definition.name)
        if isinstance(value, str) and value.strip():
            return _normalize_slug(value, "ENTRY_SLUG_INVALID")

    fallback = f"{content_type_slug}-{uuid4().hex[:8]}"
    return _normalize_slug(fallback, "ENTRY_SLUG_INVALID")


def _resolve_entry_slug(
    *,
    content_type_id: UUID,
    content_type_slug: str,
    requested_slug: str | None,
    existing_slug: str | None,
    payload: Mapping[str, Any],
    field_definitions: Sequence[FieldDefinitionModel],
    storage_connection: Any,
    entry_id: UUID | None = None,
) -> str:
    """Resolve an entry slug, enforcing uniqueness rules for the content type.

    Args:
        content_type_id: Content-type identifier.
        content_type_slug: Content-type slug for fallback generation.
        requested_slug: Explicit slug from the request, if any.
        existing_slug: Existing slug for update flows, if any.
        payload: Validated entry payload.
        field_definitions: Parsed field definitions for the content type.
        storage_connection: Open PostgreSQL connection.
        entry_id: Existing entry identifier for update flows.

    Returns:
        str: Final, unique slug for the entry.

    Raises:
        ContentError: If an explicit slug conflicts with an existing entry.
    """

    if requested_slug is not None:
        normalized_slug = _normalize_slug(requested_slug, "ENTRY_SLUG_INVALID")
        existing_entry = get_entry_by_slug(storage_connection, content_type_id, normalized_slug)
        if existing_entry is not None and existing_entry["id"] != entry_id:
            raise ContentError(
                detail="An entry with this slug already exists for the content type",
                code="ENTRY_SLUG_CONFLICT",
                status_code=HTTPStatus.CONFLICT,
            )
        return normalized_slug

    if existing_slug is not None:
        return existing_slug

    base_slug = _auto_entry_slug(content_type_slug, payload, field_definitions)
    candidate = base_slug
    suffix = 2
    while True:
        existing_entry = get_entry_by_slug(storage_connection, content_type_id, candidate)
        if existing_entry is None or existing_entry["id"] == entry_id:
            return candidate
        candidate = _slug_with_suffix(base_slug, suffix)
        suffix += 1


def _resolve_published_at(
    status: ContentStatus,
    existing_published_at: datetime | None,
    timestamp: datetime,
) -> datetime | None:
    """Resolve the published-at timestamp for a status transition.

    Args:
        status: Requested publish state.
        existing_published_at: Existing publish timestamp, if any.
        timestamp: Current operation timestamp.

    Returns:
        datetime | None: Publish timestamp to persist.

    Raises:
        None.
    """

    if status is ContentStatus.PUBLISHED:
        return existing_published_at or timestamp
    if status is ContentStatus.ARCHIVED:
        return existing_published_at
    return None


def _validate_content_type_update_against_entries(
    *,
    existing_field_definitions: Sequence[FieldDefinitionModel],
    proposed_field_definitions: Sequence[FieldDefinitionModel],
    entry_rows: Sequence[Mapping[str, Any]],
    legacy_rich_text_fields: set[str],
) -> None:
    """Validate a proposed schema update against existing entries.

    Args:
        existing_field_definitions: Currently stored field definitions.
        proposed_field_definitions: Proposed replacement field definitions.
        entry_rows: Existing entry payload rows for the content type.
        legacy_rich_text_fields: Rich-text field names that may preserve legacy HTML.

    Returns:
        None.

    Raises:
        ContentError: If the proposed update is unsafe for existing entries.
    """

    if not entry_rows:
        return

    existing_by_name = {item.name: item for item in existing_field_definitions}
    proposed_by_name = {item.name: item for item in proposed_field_definitions}

    removed_names = sorted(set(existing_by_name) - set(proposed_by_name))
    if removed_names:
        names = ', '.join(removed_names)
        raise ContentError(
            detail=(
                "Field definition update would remove field(s) with existing data: "
                f"{names}"
            ),
            code="CONTENT_TYPE_UPDATE_INVALID",
            status_code=HTTPStatus.CONFLICT,
        )

    type_changed_names = sorted(
        name
        for name in set(existing_by_name) & set(proposed_by_name)
        if existing_by_name[name].kind != proposed_by_name[name].kind
    )
    if type_changed_names:
        names = ', '.join(type_changed_names)
        raise ContentError(
            detail=(
                "Field definition update would change field type for existing "
                f"field(s): {names}"
            ),
            code="CONTENT_TYPE_UPDATE_INVALID",
            status_code=HTTPStatus.CONFLICT,
        )

    for entry_row in entry_rows:
        entry_payload = cast(dict[str, Any], entry_row["payload"])
        try:
            _validate_entry_payload(
                entry_payload,
                proposed_field_definitions,
                existing_payload=entry_payload,
                legacy_rich_text_fields=legacy_rich_text_fields,
            )
        except ContentError as exc:
            raise ContentError(
                detail=(
                    "Field definition update would invalidate existing entry "
                    f"'{entry_row['slug']}': {exc.detail}"
                ),
                code="CONTENT_TYPE_UPDATE_INVALID",
                status_code=HTTPStatus.CONFLICT,
            ) from exc


def _build_content_type_response(
    content_type_row: Mapping[str, Any],
    field_rows: Sequence[Mapping[str, Any]],
    *,
    entry_count: int,
) -> ContentTypeResponse:
    """Build a content-type response from storage rows.

    Args:
        content_type_row: Content-type storage row.
        field_rows: Field-definition storage rows for the content type.
        entry_count: Server-derived number of entries for the content type.

    Returns:
        ContentTypeResponse: Serialized content-type response model.

    Raises:
        ValidationError: If the stored data cannot be parsed.
    """

    return ContentTypeResponse.from_record(
        content_type_row,
        _field_definitions_from_rows(field_rows),
        entry_count=entry_count,
    )


def _run_search_indexing_hook(
    connection: Any,
    *,
    operation: str,
    context: Mapping[str, object],
    hook: Callable[[], None],
) -> None:
    """Run a derived search-indexing hook without blocking content CRUD.

    Args:
        connection: Open PostgreSQL connection with an active content transaction.
        operation: Stable operation name for diagnostic logs.
        context: Identifiers useful for diagnosing indexing failures.
        hook: Search synchronization callable to execute in a savepoint.

    Returns:
        None.

    Raises:
        None.
    """

    try:
        with connection.transaction():
            hook()
    except SearchError as exc:
        logging.getLogger(__name__).warning(
            "Content search-indexing hook failed",
            extra={
                "operation": operation,
                "search_code": exc.code,
                **context,
            },
        )
    except PsycopgError:
        logging.getLogger(__name__).warning(
            "Content search-indexing storage hook failed",
            extra={"operation": operation, **context},
            exc_info=True,
        )


def create_content_type_record(
    storage: DatabasePool,
    payload: ContentTypeCreateRequest,
    current_user: Mapping[str, object],
) -> ContentTypeResponse:
    """Create a content type with its field definitions.

    Args:
        storage: Initialized database pool manager.
        payload: Content-type creation payload.
        current_user: Authenticated user context.

    Returns:
        ContentTypeResponse: Created content-type response.

    Raises:
        ContentError: If the content-type payload conflicts with existing data.
        StorageError: If PostgreSQL access fails.
    """

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    field_definitions = list(payload.field_definitions)
    _validate_field_definitions(field_definitions)
    slug = _normalize_slug(payload.slug or payload.name, "CONTENT_TYPE_SLUG_INVALID")

    try:
        with storage.connection() as connection, connection.transaction():
            existing_type = get_content_type_by_slug(connection, slug)
            if existing_type is not None:
                raise ContentError(
                    detail="A content type with this slug already exists",
                    code="CONTENT_TYPE_SLUG_CONFLICT",
                    status_code=HTTPStatus.CONFLICT,
                )

            content_type_row = create_content_type(
                connection=connection,
                content_type_id=uuid4(),
                name=payload.name.strip(),
                slug=slug,
                description=payload.description.strip() if payload.description else None,
                user_id=user_id,
                created_at=timestamp,
            )
            replace_field_definitions(
                connection,
                content_type_row["id"],
                [_field_definition_to_storage_payload(item) for item in field_definitions],
                timestamp,
            )
            field_rows = get_field_definitions(connection, content_type_row["id"])
            entry_count = count_entries_for_content_type(connection, content_type_row["id"])
    except ContentError:
        raise
    except IntegrityError as exc:
        raise ContentError(
            detail="A content type with this slug already exists",
            code="CONTENT_TYPE_SLUG_CONFLICT",
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to create content type",
            code="CONTENT_TYPE_CREATE_FAILED",
        ) from exc

    return _build_content_type_response(
        content_type_row,
        field_rows,
        entry_count=entry_count,
    )


def list_content_type_records(
    storage: DatabasePool, params: ContentTypeListParams
) -> ContentTypeListResponse:
    """List content types with pagination.

    Args:
        storage: Initialized database pool manager.
        params: Content-type list parameters.

    Returns:
        ContentTypeListResponse: Paginated content-type response.

    Raises:
        StorageError: If PostgreSQL access fails.
    """

    try:
        with storage.connection() as connection:
            content_type_rows = list_content_types(
                connection,
                limit=params.limit,
                offset=params.offset,
                order_by=params.order_by,
            )
            total = count_content_types(connection)
            content_type_ids = [cast(UUID, row["id"]) for row in content_type_rows]
            fields_by_content_type = list_field_definitions(connection, content_type_ids)
            entry_counts = count_entries_by_content_type_ids(connection, content_type_ids)
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to list content types",
            code="CONTENT_TYPE_LIST_FAILED",
        ) from exc

    items = [
        _build_content_type_response(
            row,
            fields_by_content_type.get(cast(UUID, row["id"]), []),
            entry_count=entry_counts.get(cast(UUID, row["id"]), 0),
        )
        for row in content_type_rows
    ]
    return ContentTypeListResponse(
        items=items,
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


def get_content_type_record(storage: DatabasePool, content_type_id: UUID) -> ContentTypeResponse:
    """Return a single content type by identifier.

    Args:
        storage: Initialized database pool manager.
        content_type_id: Content-type identifier.

    Returns:
        ContentTypeResponse: Serialized content-type response.

    Raises:
        ContentError: If the content type does not exist.
        StorageError: If PostgreSQL access fails.
    """

    try:
        with storage.connection() as connection:
            content_type_row = get_content_type_by_id(connection, content_type_id)
            if content_type_row is None:
                raise ContentError(
                    detail="Content type not found",
                    code="CONTENT_TYPE_NOT_FOUND",
                    status_code=HTTPStatus.NOT_FOUND,
                )
            field_rows = get_field_definitions(connection, content_type_id)
            entry_count = count_entries_for_content_type(connection, content_type_id)
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to load content type",
            code="CONTENT_TYPE_LOOKUP_FAILED",
        ) from exc

    return _build_content_type_response(
        content_type_row,
        field_rows,
        entry_count=entry_count,
    )


def update_content_type_record(
    storage: DatabasePool,
    content_type_id: UUID,
    payload: ContentTypeUpdateRequest,
    current_user: Mapping[str, object],
) -> ContentTypeResponse:
    """Update a content type and its field definitions.

    Args:
        storage: Initialized database pool manager.
        content_type_id: Content-type identifier to update.
        payload: Content-type update payload.
        current_user: Authenticated user context.

    Returns:
        ContentTypeResponse: Updated content-type response.

    Raises:
        ContentError: If the content type cannot be updated safely.
        StorageError: If PostgreSQL access fails.
    """

    from pragma.search.service import rebuild_search_documents_for_content_type

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    field_definitions = list(payload.field_definitions)
    _validate_field_definitions(field_definitions)
    slug = _normalize_slug(payload.slug or payload.name, "CONTENT_TYPE_SLUG_INVALID")

    try:
        with storage.connection() as connection, connection.transaction():
            existing_type = get_content_type_by_id_for_update(connection, content_type_id)
            if existing_type is None:
                raise ContentError(
                    detail="Content type not found",
                    code="CONTENT_TYPE_NOT_FOUND",
                    status_code=HTTPStatus.NOT_FOUND,
                )

            existing_field_definitions = _field_definitions_from_rows(
                get_field_definitions(connection, content_type_id)
            )
            legacy_rich_text_fields = {
                field_definition.name
                for field_definition in existing_field_definitions
                if isinstance(field_definition, TextFieldDefinition)
                and field_definition.kind == "rich_text"
            } & {
                field_definition.name
                for field_definition in field_definitions
                if isinstance(field_definition, TextFieldDefinition)
                and field_definition.kind == "rich_text"
            }

            conflicting_type = get_content_type_by_slug(connection, slug)
            if conflicting_type is not None and conflicting_type["id"] != content_type_id:
                raise ContentError(
                    detail="A content type with this slug already exists",
                    code="CONTENT_TYPE_SLUG_CONFLICT",
                    status_code=HTTPStatus.CONFLICT,
                )

            _validate_content_type_update_against_entries(
                existing_field_definitions=existing_field_definitions,
                proposed_field_definitions=field_definitions,
                entry_rows=list_entries_for_content_type_validation(
                    connection, content_type_id
                ),
                legacy_rich_text_fields=legacy_rich_text_fields,
            )

            content_type_row = update_content_type(
                connection=connection,
                content_type_id=content_type_id,
                name=payload.name.strip(),
                slug=slug,
                description=payload.description.strip() if payload.description else None,
                user_id=user_id,
                updated_at=timestamp,
            )
            replace_field_definitions(
                connection,
                content_type_id,
                [_field_definition_to_storage_payload(item) for item in field_definitions],
                timestamp,
            )
            field_rows = get_field_definitions(connection, content_type_id)
            entry_count = count_entries_for_content_type(connection, content_type_id)
    except ContentError:
        raise
    except IntegrityError as exc:
        raise ContentError(
            detail="A content type with this slug already exists",
            code="CONTENT_TYPE_SLUG_CONFLICT",
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to update content type",
            code="CONTENT_TYPE_UPDATE_FAILED",
        ) from exc

    try:
        with storage.connection() as rebuild_connection:
            _run_search_indexing_hook(
                rebuild_connection,
                operation="content_type_rebuild",
                context={"content_type_id": str(content_type_id)},
                hook=lambda: rebuild_search_documents_for_content_type(
                    rebuild_connection,
                    content_type_id=content_type_id,
                    field_rows=field_rows,
                ),
            )
    except PsycopgError:
        logging.getLogger(__name__).warning(
            "Content search-indexing storage hook failed",
            extra={
                "operation": "content_type_rebuild",
                "content_type_id": str(content_type_id),
            },
            exc_info=True,
        )

    return _build_content_type_response(
        content_type_row,
        field_rows,
        entry_count=entry_count,
    )


def delete_content_type_record(storage: DatabasePool, content_type_id: UUID) -> None:
    """Delete a content type when it has no entries.

    Args:
        storage: Initialized database pool manager.
        content_type_id: Content-type identifier to delete.

    Returns:
        None.

    Raises:
        ContentError: If the content type is missing or still has entries.
        StorageError: If PostgreSQL access fails.
    """

    try:
        with storage.connection() as connection, connection.transaction():
            existing_type = get_content_type_by_id_for_update(connection, content_type_id)
            if existing_type is None:
                raise ContentError(
                    detail="Content type not found",
                    code="CONTENT_TYPE_NOT_FOUND",
                    status_code=HTTPStatus.NOT_FOUND,
                )

            if count_entries_for_content_type(connection, content_type_id) > 0:
                raise ContentError(
                    detail="Content type has existing entries and cannot be deleted",
                    code="CONTENT_TYPE_IN_USE",
                    status_code=HTTPStatus.CONFLICT,
                )

            if not delete_content_type_if_unused(connection, content_type_id):
                raise ContentError(
                    detail="Content type has existing entries and cannot be deleted",
                    code="CONTENT_TYPE_IN_USE",
                    status_code=HTTPStatus.CONFLICT,
                )
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to delete content type",
            code="CONTENT_TYPE_DELETE_FAILED",
        ) from exc


def create_entry_record(
    storage: DatabasePool,
    payload: ContentEntryCreateRequest,
    current_user: Mapping[str, object],
) -> ContentEntryResponse:
    """Create a content entry within a content type."""

    from pragma.auth.permissions import (
        PERMISSION_CONTENT_ENTRIES_PUBLISH,
        ensure_permission,
    )
    from pragma.content.models import ContentEntryActivityAction
    from pragma.modules.service import dispatch_content_entry_event
    from pragma.realtime.service import publish_content_entry_event
    from pragma.search.service import sync_search_document

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    if payload.status.value == 'published':
        ensure_permission(current_user, PERMISSION_CONTENT_ENTRIES_PUBLISH)

    try:
        with storage.connection() as connection, connection.transaction():
            content_type_row = get_content_type_by_id_for_key_share(
                connection, payload.content_type_id
            )
            if content_type_row is None:
                raise ContentError(
                    detail='Content type not found',
                    code='CONTENT_TYPE_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )

            field_definitions = _field_definitions_from_rows(
                get_field_definitions(connection, payload.content_type_id)
            )
            validated_payload = _validate_entry_payload(payload.payload, field_definitions)
            slug = _resolve_entry_slug(
                content_type_id=payload.content_type_id,
                content_type_slug=cast(str, content_type_row['slug']),
                requested_slug=payload.slug,
                existing_slug=None,
                payload=validated_payload,
                field_definitions=field_definitions,
                storage_connection=connection,
            )
            published_at = _resolve_published_at(payload.status, None, timestamp)
            seo_metadata = payload.seo_metadata.to_storage()
            entry_row = create_entry(
                connection=connection,
                entry_id=uuid4(),
                content_type_id=payload.content_type_id,
                slug=slug,
                status=payload.status.value,
                payload=validated_payload,
                seo_metadata=seo_metadata,
                published_at=published_at,
                user_id=user_id,
                created_at=timestamp,
            )
            entry_row = {**entry_row, 'content_type_slug': content_type_row['slug']}
            _create_entry_revision(
                connection,
                entry_row=entry_row,
                action=ContentRevisionAction.CREATE,
                user_id=user_id,
                timestamp=timestamp,
            )
            _record_entry_activity(
                connection,
                entry_id=cast(UUID, entry_row['id']),
                entry_row=entry_row,
                action=ContentEntryActivityAction.CREATE.value,
                actor_user_id=user_id,
                timestamp=timestamp,
            )
            _run_search_indexing_hook(
                connection,
                operation='entry_create_sync',
                context={
                    'entry_id': str(entry_row['id']),
                    'content_type_id': str(payload.content_type_id),
                },
                hook=lambda: sync_search_document(
                    connection,
                    entry_row=entry_row,
                    content_type_slug=cast(str, content_type_row['slug']),
                    field_definitions=field_definitions,
                ),
            )
    except ContentError:
        raise
    except IntegrityError as exc:
        raise ContentError(
            detail='An entry with this slug already exists for the content type',
            code='ENTRY_SLUG_CONFLICT',
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to create content entry',
            code='CONTENT_ENTRY_CREATE_FAILED',
        ) from exc

    entry_response = ContentEntryResponse.from_record(entry_row)
    publish_content_entry_event(
        event_type='content.entry.created',
        entry=entry_response,
        actor_id=user_id,
    )
    dispatch_content_entry_event(
        'content.entry.created',
        {
            'event': 'content.entry.created',
            'entry': entry_response.model_dump(mode='json'),
        },
    )
    return entry_response


def list_entry_records(
    storage: DatabasePool, params: ContentEntryListParams
) -> ContentEntryListResponse:
    """List content entries with pagination and optional filters.

    Args:
        storage: Initialized database pool manager.
        params: Content-entry list parameters.

    Returns:
        ContentEntryListResponse: Paginated content-entry response.

    Raises:
        ContentError: If mutually exclusive filters are combined.
        StorageError: If PostgreSQL access fails.
    """

    if params.content_type_id is not None and params.content_type_slug is not None:
        raise ContentError(
            detail="Use either content_type_id or content_type_slug, not both",
            code="ENTRY_FILTER_CONFLICT",
        )

    normalized_slug = (
        _normalize_slug(params.content_type_slug, "CONTENT_TYPE_SLUG_INVALID")
        if params.content_type_slug is not None
        else None
    )

    try:
        with storage.connection() as connection:
            entry_rows = list_entries(
                connection=connection,
                limit=params.limit,
                offset=params.offset,
                order_by=params.order_by,
                content_type_id=params.content_type_id,
                content_type_slug=normalized_slug,
                status=params.status.value if params.status is not None else None,
            )
            total = count_entries(
                connection=connection,
                content_type_id=params.content_type_id,
                content_type_slug=normalized_slug,
                status=params.status.value if params.status is not None else None,
            )
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to list content entries",
            code="CONTENT_ENTRY_LIST_FAILED",
        ) from exc

    return ContentEntryListResponse(
        items=[ContentEntryResponse.from_record(row) for row in entry_rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


def get_entry_record(storage: DatabasePool, entry_id: UUID) -> ContentEntryResponse:
    """Return a single content entry by identifier.

    Args:
        storage: Initialized database pool manager.
        entry_id: Content-entry identifier.

    Returns:
        ContentEntryResponse: Serialized content-entry response.

    Raises:
        ContentError: If the entry does not exist.
        StorageError: If PostgreSQL access fails.
    """

    try:
        with storage.connection() as connection:
            entry_row = get_entry_by_id(connection, entry_id)
            if entry_row is None:
                raise ContentError(
                    detail="Content entry not found",
                    code="CONTENT_ENTRY_NOT_FOUND",
                    status_code=HTTPStatus.NOT_FOUND,
                )
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to load content entry",
            code="CONTENT_ENTRY_LOOKUP_FAILED",
        ) from exc

    return ContentEntryResponse.from_record(entry_row)


def _record_entry_activity(
    connection: Any,
    *,
    entry_id: UUID,
    action: str,
    actor_user_id: UUID | None,
    timestamp: datetime,
    entry_row: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Append durable activity without requiring the entry row to survive."""

    from pragma.storage.queries.content import create_content_entry_activity

    entry_version = None
    if entry_row is not None and entry_row.get('version') is not None:
        entry_version = int(entry_row['version'])
    create_content_entry_activity(
        connection,
        activity_id=uuid4(),
        entry_id=entry_id,
        content_type_id=(
            cast(UUID, entry_row.get('content_type_id'))
            if entry_row is not None
            else None
        ),
        entry_slug=(
            cast(str, entry_row.get('slug')) if entry_row is not None else None
        ),
        entry_version=entry_version,
        action=action,
        actor_user_id=actor_user_id,
        details=dict(details or {}),
        created_at=timestamp,
    )


def _build_autosave_response(
    autosave_row: Mapping[str, Any], *, current_version: int
) -> ContentEntryAutosaveResponse:
    """Build a current-user autosave response from storage rows."""

    from pragma.content.models import ContentEntryAutosaveResponse

    base_version = int(autosave_row['base_version'])
    return ContentEntryAutosaveResponse(
        entry_id=autosave_row['entry_id'],
        user_id=autosave_row['user_id'],
        base_version=base_version,
        current_version=current_version,
        is_stale=base_version != current_version,
        slug=cast(str, autosave_row['slug']),
        payload=cast(dict[str, Any], autosave_row['payload']),
        seo_metadata=ContentEntrySeoMetadata.from_record(autosave_row),
        updated_at=autosave_row['updated_at'],
    )


def _legacy_rich_text_fields(
    field_definitions: Sequence[FieldDefinitionModel],
) -> set[str]:
    """Return rich-text fields allowed to preserve unchanged legacy HTML."""

    return {
        field_definition.name
        for field_definition in field_definitions
        if isinstance(field_definition, TextFieldDefinition)
        and field_definition.kind == 'rich_text'
    }


def save_entry_autosave_record(
    storage: DatabasePool,
    entry_id: UUID,
    payload: ContentEntryAutosaveRequest,
    current_user: Mapping[str, object],
) -> ContentEntryAutosaveResponse:
    """Store a validated per-user autosave snapshot without mutating the entry."""

    from pragma.content.models import ContentEntryActivityAction
    from pragma.storage.queries.content import upsert_entry_autosave

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    try:
        with storage.connection() as connection, connection.transaction():
            existing_entry = get_entry_by_id(connection, entry_id)
            if existing_entry is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            field_definitions = _field_definitions_from_rows(
                get_field_definitions(connection, existing_entry['content_type_id'])
            )
            existing_payload = cast(dict[str, Any], existing_entry['payload'])
            validated_payload = _validate_entry_payload(
                payload.payload,
                field_definitions,
                existing_payload=existing_payload,
                legacy_rich_text_fields=_legacy_rich_text_fields(field_definitions),
            )
            slug = _resolve_entry_slug(
                content_type_id=existing_entry['content_type_id'],
                content_type_slug=cast(str, existing_entry['content_type_slug']),
                requested_slug=payload.slug,
                existing_slug=existing_entry['slug'] if payload.slug is None else None,
                payload=validated_payload,
                field_definitions=field_definitions,
                storage_connection=connection,
                entry_id=entry_id,
            )
            current_version = int(existing_entry['version'])
            autosave_row = upsert_entry_autosave(
                connection,
                entry_id=entry_id,
                user_id=user_id,
                base_version=payload.base_version,
                slug=slug,
                payload=validated_payload,
                seo_metadata=payload.seo_metadata.to_storage(),
                timestamp=timestamp,
            )
            _record_entry_activity(
                connection,
                entry_id=entry_id,
                entry_row=existing_entry,
                action=ContentEntryActivityAction.AUTOSAVE.value,
                actor_user_id=user_id,
                timestamp=timestamp,
                details={
                    'base_version': payload.base_version,
                    'current_version': current_version,
                    'is_stale': payload.base_version != current_version,
                },
            )
    except ContentError:
        raise
    except IntegrityError as exc:
        raise ContentError(
            detail='An entry with this slug already exists for the content type',
            code='ENTRY_SLUG_CONFLICT',
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to save content entry autosave',
            code='CONTENT_ENTRY_AUTOSAVE_SAVE_FAILED',
        ) from exc

    return _build_autosave_response(autosave_row, current_version=current_version)


def get_entry_autosave_record(
    storage: DatabasePool,
    entry_id: UUID,
    current_user: Mapping[str, object],
) -> ContentEntryAutosaveResponse:
    """Return the current user's autosave snapshot for an entry."""

    from pragma.storage.queries.content import get_entry_autosave

    user_id = _require_user_id(current_user)
    try:
        with storage.connection() as connection:
            existing_entry = get_entry_by_id(connection, entry_id)
            if existing_entry is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            autosave_row = get_entry_autosave(connection, entry_id, user_id)
            if autosave_row is None:
                raise ContentError(
                    detail='Content entry autosave not found',
                    code='CONTENT_ENTRY_AUTOSAVE_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            current_version = int(existing_entry['version'])
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load content entry autosave',
            code='CONTENT_ENTRY_AUTOSAVE_LOOKUP_FAILED',
        ) from exc

    return _build_autosave_response(autosave_row, current_version=current_version)


def delete_entry_autosave_record(
    storage: DatabasePool,
    entry_id: UUID,
    current_user: Mapping[str, object],
) -> None:
    """Discard the current user's autosave snapshot for an entry."""

    from pragma.content.models import ContentEntryActivityAction
    from pragma.storage.queries.content import delete_entry_autosave

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    try:
        with storage.connection() as connection, connection.transaction():
            existing_entry = get_entry_by_id(connection, entry_id)
            if existing_entry is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            deleted = delete_entry_autosave(connection, entry_id, user_id)
            if deleted:
                _record_entry_activity(
                    connection,
                    entry_id=entry_id,
                    entry_row=existing_entry,
                    action=ContentEntryActivityAction.AUTOSAVE.value,
                    actor_user_id=user_id,
                    timestamp=timestamp,
                    details={'discarded': True},
                )
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to delete content entry autosave',
            code='CONTENT_ENTRY_AUTOSAVE_DELETE_FAILED',
        ) from exc


def list_entry_activity_records(
    storage: DatabasePool,
    entry_id: UUID,
    params: ContentEntryActivityListParams,
) -> ContentEntryActivityListResponse:
    """List durable content-entry activity newest-first."""

    from pragma.content.models import (
        ContentEntryActivityListResponse,
        ContentEntryActivityResponse,
    )
    from pragma.storage.queries.content import (
        count_content_entry_activity,
        list_content_entry_activity,
    )

    try:
        with storage.connection() as connection:
            activity_rows = list_content_entry_activity(
                connection, entry_id, params.limit, params.offset
            )
            total = count_content_entry_activity(connection, entry_id)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to list content entry activity',
            code='CONTENT_ENTRY_ACTIVITY_LIST_FAILED',
        ) from exc

    return ContentEntryActivityListResponse(
        items=[ContentEntryActivityResponse.from_record(row) for row in activity_rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


def _build_schedule_response(
    entry_id: UUID, schedule_rows: Sequence[Mapping[str, Any]]
) -> ContentEntryScheduleResponse:
    """Build a pending schedule summary from storage rows."""

    from pragma.content.models import (
        ContentEntryScheduleItemResponse,
        ContentEntryScheduleResponse,
    )

    items = {
        str(row['action']): ContentEntryScheduleItemResponse.from_record(row)
        for row in schedule_rows
    }
    return ContentEntryScheduleResponse(
        entry_id=entry_id,
        publish=items.get('publish'),
        unpublish=items.get('unpublish'),
    )


def _schedule_invalid(detail: str) -> ContentError:
    """Build a structured invalid schedule error."""

    return ContentError(
        detail=detail,
        code='CONTENT_ENTRY_SCHEDULE_INVALID',
        status_code=HTTPStatus.CONFLICT,
    )


def _normalize_schedule_time(
    value: datetime | None, *, field_name: str, now: datetime
) -> datetime | None:
    """Require timezone-aware future schedule timestamps."""

    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise _schedule_invalid(f'{field_name} must include a timezone')
    normalized = value.astimezone(now.tzinfo)
    if normalized <= now:
        raise _schedule_invalid(f'{field_name} must be in the future')
    return normalized


def _validate_schedule_request(
    existing_entry: Mapping[str, Any],
    payload: ContentEntryScheduleRequest,
    current_user: Mapping[str, object],
    *,
    now: datetime,
) -> tuple[datetime | None, datetime | None]:
    """Validate and normalize a schedule replacement request."""

    from pragma.auth.permissions import (
        PERMISSION_CONTENT_ENTRIES_PUBLISH,
        ensure_permission,
    )

    if payload.publish_at is None and payload.unpublish_at is None:
        raise _schedule_invalid('At least one schedule timestamp is required')

    if int(existing_entry['version']) != payload.expected_version:
        _raise_version_conflict()

    publish_at = _normalize_schedule_time(
        payload.publish_at, field_name='publish_at', now=now
    )
    unpublish_at = _normalize_schedule_time(
        payload.unpublish_at, field_name='unpublish_at', now=now
    )
    if publish_at is not None and unpublish_at is not None and publish_at >= unpublish_at:
        raise _schedule_invalid('publish_at must be before unpublish_at')

    existing_status = cast(str, existing_entry['status'])
    if existing_status == 'archived':
        raise _schedule_invalid('Archived entries cannot be scheduled')
    if publish_at is not None and existing_status != 'draft':
        raise _schedule_invalid('Only draft entries can schedule publish')
    if unpublish_at is not None and existing_status == 'draft' and publish_at is None:
        raise _schedule_invalid('Draft entries must schedule publish before unpublish')

    ensure_permission(current_user, PERMISSION_CONTENT_ENTRIES_PUBLISH)
    return publish_at, unpublish_at


def get_entry_schedule_record(
    storage: DatabasePool, entry_id: UUID
) -> ContentEntryScheduleResponse:
    """Return pending schedule metadata for a content entry."""

    from pragma.storage.queries.content import list_pending_content_entry_schedules

    try:
        with storage.connection() as connection:
            if get_entry_by_id(connection, entry_id) is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            schedule_rows = list_pending_content_entry_schedules(connection, entry_id)
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load content entry schedules',
            code='CONTENT_ENTRY_SCHEDULE_LOOKUP_FAILED',
        ) from exc

    return _build_schedule_response(entry_id, schedule_rows)


def set_entry_schedule_record(
    storage: DatabasePool,
    entry_id: UUID,
    payload: ContentEntryScheduleRequest,
    current_user: Mapping[str, object],
) -> ContentEntryScheduleResponse:
    """Replace pending publish/unpublish schedules for a content entry."""

    from pragma.content.models import ContentEntryActivityAction
    from pragma.storage.queries.content import (
        cancel_pending_content_entry_schedules,
        list_pending_content_entry_schedules,
        upsert_content_entry_schedule,
    )

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    try:
        with storage.connection() as connection, connection.transaction():
            existing_entry = get_entry_by_id_for_update(connection, entry_id)
            if existing_entry is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            publish_at, unpublish_at = _validate_schedule_request(
                existing_entry, payload, current_user, now=timestamp
            )

            requested_actions = []
            if publish_at is not None:
                requested_actions.append('publish')
            if unpublish_at is not None:
                requested_actions.append('unpublish')

            omitted_actions = [
                action
                for action in ('publish', 'unpublish')
                if action not in requested_actions
            ]
            cancelled_rows = cancel_pending_content_entry_schedules(
                connection,
                entry_id=entry_id,
                actions=omitted_actions,
                timestamp=timestamp,
            )
            for row in cancelled_rows:
                _record_entry_activity(
                    connection,
                    entry_id=entry_id,
                    entry_row=existing_entry,
                    action=ContentEntryActivityAction.SCHEDULE_CANCEL.value,
                    actor_user_id=user_id,
                    timestamp=timestamp,
                    details={
                        'schedule_id': str(row['id']),
                        'schedule_action': row['action'],
                    },
                )

            for action, run_at in (
                ('publish', publish_at),
                ('unpublish', unpublish_at),
            ):
                if run_at is None:
                    continue
                schedule_row = upsert_content_entry_schedule(
                    connection,
                    schedule_id=uuid4(),
                    entry_id=entry_id,
                    action=action,
                    run_at=run_at,
                    requested_entry_version=payload.expected_version,
                    requested_by_user_id=user_id,
                    timestamp=timestamp,
                )
                _record_entry_activity(
                    connection,
                    entry_id=entry_id,
                    entry_row=existing_entry,
                    action=ContentEntryActivityAction.SCHEDULE_SET.value,
                    actor_user_id=user_id,
                    timestamp=timestamp,
                    details={
                        'schedule_id': str(schedule_row['id']),
                        'schedule_action': action,
                        'run_at': run_at.isoformat(),
                        'expected_version': payload.expected_version,
                    },
                )

            schedule_rows = list_pending_content_entry_schedules(connection, entry_id)
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to set content entry schedule',
            code='CONTENT_ENTRY_SCHEDULE_SET_FAILED',
        ) from exc

    return _build_schedule_response(entry_id, schedule_rows)


def cancel_entry_schedule_record(
    storage: DatabasePool,
    entry_id: UUID,
    current_user: Mapping[str, object],
) -> ContentEntryScheduleResponse:
    """Cancel all pending schedules for a content entry."""

    from pragma.content.models import ContentEntryActivityAction
    from pragma.storage.queries.content import (
        cancel_pending_content_entry_schedules,
        list_pending_content_entry_schedules,
    )

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    try:
        with storage.connection() as connection, connection.transaction():
            existing_entry = get_entry_by_id_for_update(connection, entry_id)
            if existing_entry is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            cancelled_rows = cancel_pending_content_entry_schedules(
                connection,
                entry_id=entry_id,
                actions=('publish', 'unpublish'),
                timestamp=timestamp,
            )
            for row in cancelled_rows:
                _record_entry_activity(
                    connection,
                    entry_id=entry_id,
                    entry_row=existing_entry,
                    action=ContentEntryActivityAction.SCHEDULE_CANCEL.value,
                    actor_user_id=user_id,
                    timestamp=timestamp,
                    details={
                        'schedule_id': str(row['id']),
                        'schedule_action': row['action'],
                    },
                )
            schedule_rows = list_pending_content_entry_schedules(connection, entry_id)
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to cancel content entry schedules',
            code='CONTENT_ENTRY_SCHEDULE_CANCEL_FAILED',
        ) from exc

    return _build_schedule_response(entry_id, schedule_rows)


def _schedule_failure(
    connection: Any,
    *,
    schedule_row: Mapping[str, Any],
    entry_row: Mapping[str, Any] | None,
    failure_code: str,
    failure_detail: str,
    timestamp: datetime,
) -> None:
    """Mark a due schedule failed and append durable activity."""

    from pragma.content.models import ContentEntryActivityAction
    from pragma.storage.queries.content import mark_content_entry_schedule_failed

    failed_row = mark_content_entry_schedule_failed(
        connection,
        schedule_id=schedule_row['id'],
        failure_code=failure_code,
        failure_detail=failure_detail[:500],
        timestamp=timestamp,
    )
    _record_entry_activity(
        connection,
        entry_id=schedule_row['entry_id'],
        entry_row=entry_row,
        action=ContentEntryActivityAction.SCHEDULE_FAIL.value,
        actor_user_id=failed_row.get('requested_by_user_id'),
        timestamp=timestamp,
        details={
            'schedule_id': str(failed_row['id']),
            'schedule_action': failed_row['action'],
            'failure_code': failure_code,
        },
    )


def execute_due_content_entry_schedules(
    storage: DatabasePool,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> ContentEntryScheduleExecutionResult:
    """Execute due pending publish/unpublish schedules once.

    This function is intentionally caller-driven; no background worker is started here.
    """

    from functools import partial

    from pragma.content.models import (
        ContentEntryActivityAction,
        ContentEntryScheduleExecutionResult,
    )
    from pragma.search.service import sync_search_document
    from pragma.storage.queries.content import (
        claim_due_content_entry_schedules,
        mark_content_entry_schedule_executed,
    )

    if limit < 1:
        raise ContentError(
            detail='Schedule execution limit must be at least 1',
            code='CONTENT_ENTRY_SCHEDULE_LIMIT_INVALID',
        )

    timestamp = now or utc_now()
    emitted: list[tuple[ContentEntryResponse, UUID | None]] = []
    checked = 0
    executed = 0
    failed = 0
    try:
        with storage.connection() as connection, connection.transaction():
            due_rows = claim_due_content_entry_schedules(
                connection, now=timestamp, limit=limit
            )
            checked = len(due_rows)
            for schedule_row in due_rows:
                entry_id = cast(UUID, schedule_row['entry_id'])
                existing_entry = get_entry_by_id_for_update(connection, entry_id)
                if existing_entry is None:
                    _schedule_failure(
                        connection,
                        schedule_row=schedule_row,
                        entry_row=None,
                        failure_code='CONTENT_ENTRY_NOT_FOUND',
                        failure_detail='Content entry not found',
                        timestamp=timestamp,
                    )
                    failed += 1
                    continue

                expected_version = int(schedule_row['requested_entry_version'])
                if int(existing_entry['version']) != expected_version:
                    _schedule_failure(
                        connection,
                        schedule_row=schedule_row,
                        entry_row=existing_entry,
                        failure_code='CONTENT_ENTRY_VERSION_CONFLICT',
                        failure_detail=(
                            'Content entry version does not match scheduled version'
                        ),
                        timestamp=timestamp,
                    )
                    failed += 1
                    continue

                action_value = cast(str, schedule_row['action'])
                target_status = (
                    ContentStatus.PUBLISHED
                    if action_value == 'publish'
                    else ContentStatus.DRAFT
                )
                if target_status is ContentStatus.PUBLISHED and existing_entry['status'] != 'draft':
                    _schedule_failure(
                        connection,
                        schedule_row=schedule_row,
                        entry_row=existing_entry,
                        failure_code='CONTENT_ENTRY_TRANSITION_INVALID',
                        failure_detail='Only draft entries can be published',
                        timestamp=timestamp,
                    )
                    failed += 1
                    continue
                if target_status is ContentStatus.DRAFT and existing_entry['status'] != 'published':
                    _schedule_failure(
                        connection,
                        schedule_row=schedule_row,
                        entry_row=existing_entry,
                        failure_code='CONTENT_ENTRY_TRANSITION_INVALID',
                        failure_detail='Only published entries can be unpublished',
                        timestamp=timestamp,
                    )
                    failed += 1
                    continue

                field_definitions = _field_definitions_from_rows(
                    get_field_definitions(connection, existing_entry['content_type_id'])
                )
                published_at = _resolve_published_at(
                    target_status, existing_entry['published_at'], timestamp
                )
                entry_row = update_entry(
                    connection=connection,
                    entry_id=entry_id,
                    slug=cast(str, existing_entry['slug']),
                    status=target_status.value,
                    payload=cast(dict[str, Any], existing_entry['payload']),
                    seo_metadata=ContentEntrySeoMetadata.from_record(
                        existing_entry
                    ).to_storage(),
                    published_at=published_at,
                    user_id=cast(UUID, schedule_row['requested_by_user_id']),
                    updated_at=timestamp,
                    expected_version=expected_version,
                )
                if entry_row is None:
                    _schedule_failure(
                        connection,
                        schedule_row=schedule_row,
                        entry_row=existing_entry,
                        failure_code='CONTENT_ENTRY_VERSION_CONFLICT',
                        failure_detail=(
                            'Content entry version does not match scheduled version'
                        ),
                        timestamp=timestamp,
                    )
                    failed += 1
                    continue

                content_type_slug = cast(str, existing_entry['content_type_slug'])
                entry_row = {
                    **entry_row,
                    'content_type_slug': content_type_slug,
                }
                revision_action = (
                    ContentRevisionAction.PUBLISH
                    if target_status is ContentStatus.PUBLISHED
                    else ContentRevisionAction.UNPUBLISH
                )
                _create_entry_revision(
                    connection,
                    entry_row=entry_row,
                    action=revision_action,
                    user_id=cast(UUID, schedule_row['requested_by_user_id']),
                    timestamp=timestamp,
                )
                _run_search_indexing_hook(
                    connection,
                    operation='entry_schedule_sync',
                    context={
                        'entry_id': str(entry_id),
                        'content_type_id': str(existing_entry['content_type_id']),
                    },
                    hook=partial(
                        sync_search_document,
                        connection,
                        entry_row=entry_row,
                        content_type_slug=content_type_slug,
                        field_definitions=field_definitions,
                    ),
                )
                executed_row = mark_content_entry_schedule_executed(
                    connection, schedule_id=schedule_row['id'], timestamp=timestamp
                )
                _record_entry_activity(
                    connection,
                    entry_id=entry_id,
                    entry_row=entry_row,
                    action=ContentEntryActivityAction.SCHEDULE_EXECUTE.value,
                    actor_user_id=executed_row.get('requested_by_user_id'),
                    timestamp=timestamp,
                    details={
                        'schedule_id': str(executed_row['id']),
                        'schedule_action': executed_row['action'],
                    },
                )
                response = ContentEntryResponse.from_record(entry_row)
                emitted.append((response, executed_row.get('requested_by_user_id')))
                executed += 1
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to execute due content entry schedules',
            code='CONTENT_ENTRY_SCHEDULE_EXECUTE_FAILED',
        ) from exc

    for entry_response, actor_id in emitted:
        if actor_id is not None:
            _emit_entry_updated(entry_response, actor_id)

    return ContentEntryScheduleExecutionResult(
        checked=checked,
        executed=executed,
        failed=failed,
    )


CONTENT_ENTRY_PREVIEW_TOKEN_TYPE = 'content_preview'
_CONTENT_ENTRY_PREVIEW_TTL_SECONDS = 15 * 60


def create_content_entry_preview_token(
    settings: Settings,
    *,
    entry_id: UUID,
    ttl_seconds: int = _CONTENT_ENTRY_PREVIEW_TTL_SECONDS,
    issued_at: datetime | None = None,
) -> tuple[str, datetime]:
    """Create a non-guessable stateless signed preview token.

    Args:
        settings: Application settings containing the JWT/HMAC secret.
        entry_id: Content entry identifier to preview.
        ttl_seconds: Token lifetime in seconds.
        issued_at: Optional issued-at timestamp for tests.

    Returns:
        tuple[str, datetime]: Encoded preview token and expiry timestamp.

    Raises:
        None.
    """

    from datetime import timedelta

    import jwt

    issued_at = issued_at or utc_now()
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    payload = {
        'sub': str(entry_id),
        'typ': CONTENT_ENTRY_PREVIEW_TOKEN_TYPE,
        'jti': str(uuid4()),
        'iat': int(issued_at.timestamp()),
        'exp': int(expires_at.timestamp()),
        'iss': settings.jwt_issuer,
        'aud': settings.jwt_audience,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_content_entry_preview_token(settings: Settings, token: str) -> UUID:
    """Decode and validate a signed content-entry preview token."""

    from pragma.auth.security import decode_token
    from pragma.errors import AuthError

    payload = decode_token(
        settings=settings,
        token=token,
        expected_token_type=CONTENT_ENTRY_PREVIEW_TOKEN_TYPE,
    )
    subject = payload.get('sub')
    if not isinstance(subject, str):
        raise AuthError(detail='Preview token subject is missing', code='TOKEN_INVALID')
    try:
        return UUID(subject)
    except ValueError as exc:
        raise AuthError(detail='Preview token subject is invalid', code='TOKEN_INVALID') from exc


def create_entry_preview_record(
    storage: DatabasePool,
    settings: Settings,
    entry_id: UUID,
    current_user: Mapping[str, object],
) -> ContentEntryPreviewResponse:
    """Create a short-lived preview token/URL for a content entry."""

    from pragma.content.models import (
        ContentEntryActivityAction,
        ContentEntryPreviewResponse,
    )

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    token, expires_at = create_content_entry_preview_token(
        settings,
        entry_id=entry_id,
        issued_at=timestamp,
    )

    try:
        with storage.connection() as connection, connection.transaction():
            entry_row = get_entry_by_id(connection, entry_id)
            if entry_row is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            _record_entry_activity(
                connection,
                entry_id=entry_id,
                entry_row=entry_row,
                action=ContentEntryActivityAction.PREVIEW.value,
                actor_user_id=user_id,
                timestamp=timestamp,
                details={'expires_at': expires_at.isoformat()},
            )
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to create content entry preview',
            code='CONTENT_ENTRY_PREVIEW_CREATE_FAILED',
        ) from exc

    preview_url = f"{settings.base_url.rstrip('/')}/preview/content/{token}"
    return ContentEntryPreviewResponse(
        entry_id=entry_id,
        token=token,
        preview_url=preview_url,
        expires_at=expires_at,
    )


def update_entry_record(
    storage: DatabasePool,
    entry_id: UUID,
    payload: ContentEntryUpdateRequest,
    current_user: Mapping[str, object],
) -> ContentEntryResponse:
    """Update an existing content entry."""

    from pragma.auth.permissions import (
        PERMISSION_CONTENT_ENTRIES_PUBLISH,
        ensure_permission,
    )
    from pragma.modules.service import dispatch_content_entry_event
    from pragma.realtime.service import publish_content_entry_event
    from pragma.search.service import sync_search_document

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    if payload.status.value == 'published':
        ensure_permission(current_user, PERMISSION_CONTENT_ENTRIES_PUBLISH)

    try:
        with storage.connection() as connection, connection.transaction():
            existing_entry = get_entry_by_id_for_update(connection, entry_id)
            if existing_entry is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )

            if (
                existing_entry['status'] == 'published'
                and payload.status.value != 'published'
            ):
                ensure_permission(current_user, PERMISSION_CONTENT_ENTRIES_PUBLISH)

            field_definitions = _field_definitions_from_rows(
                get_field_definitions(connection, existing_entry['content_type_id'])
            )
            existing_payload = cast(dict[str, Any], existing_entry['payload'])
            legacy_rich_text_fields = {
                field_definition.name
                for field_definition in field_definitions
                if isinstance(field_definition, TextFieldDefinition)
                and field_definition.kind == 'rich_text'
            }
            validated_payload = _validate_entry_payload(
                payload.payload,
                field_definitions,
                existing_payload=existing_payload,
                legacy_rich_text_fields=legacy_rich_text_fields,
            )
            slug = _resolve_entry_slug(
                content_type_id=existing_entry['content_type_id'],
                content_type_slug=cast(str, existing_entry['content_type_slug']),
                requested_slug=payload.slug,
                existing_slug=existing_entry['slug'] if payload.slug is None else None,
                payload=validated_payload,
                field_definitions=field_definitions,
                storage_connection=connection,
                entry_id=entry_id,
            )
            published_at = _resolve_published_at(
                payload.status,
                existing_entry['published_at'],
                timestamp,
            )
            action = _revision_action_for_status_change(
                cast(str, existing_entry['status']),
                payload.status,
            )
            entry_row = update_entry(
                connection=connection,
                entry_id=entry_id,
                slug=slug,
                status=payload.status.value,
                payload=validated_payload,
                seo_metadata=payload.seo_metadata.to_storage(),
                published_at=published_at,
                user_id=user_id,
                updated_at=timestamp,
                expected_version=payload.expected_version,
            )
            if entry_row is None:
                _raise_version_conflict()
            entry_row = {
                **entry_row,
                'content_type_slug': existing_entry['content_type_slug'],
            }
            _create_entry_revision(
                connection,
                entry_row=entry_row,
                action=action,
                user_id=user_id,
                timestamp=timestamp,
            )
            _record_entry_activity(
                connection,
                entry_id=entry_id,
                entry_row=entry_row,
                action=action.value,
                actor_user_id=user_id,
                timestamp=timestamp,
            )
            _run_search_indexing_hook(
                connection,
                operation='entry_update_sync',
                context={
                    'entry_id': str(entry_id),
                    'content_type_id': str(existing_entry['content_type_id']),
                },
                hook=lambda: sync_search_document(
                    connection,
                    entry_row=entry_row,
                    content_type_slug=cast(str, existing_entry['content_type_slug']),
                    field_definitions=field_definitions,
                ),
            )
    except ContentError:
        raise
    except IntegrityError as exc:
        raise ContentError(
            detail='An entry with this slug already exists for the content type',
            code='ENTRY_SLUG_CONFLICT',
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to update content entry',
            code='CONTENT_ENTRY_UPDATE_FAILED',
        ) from exc

    entry_response = ContentEntryResponse.from_record(entry_row)
    publish_content_entry_event(
        event_type='content.entry.updated',
        entry=entry_response,
        actor_id=user_id,
    )
    dispatch_content_entry_event(
        'content.entry.updated',
        {
            'event': 'content.entry.updated',
            'entry': entry_response.model_dump(mode='json'),
        },
    )
    return entry_response


def delete_entry_record(
    storage: DatabasePool,
    entry_id: UUID,
    current_user: Mapping[str, object],
) -> None:
    """Delete a content entry by identifier."""

    from pragma.content.models import ContentEntryActivityAction
    from pragma.modules.service import dispatch_content_entry_event
    from pragma.realtime.service import publish_content_entry_event
    from pragma.search.service import delete_search_document

    user_id = _require_user_id(current_user)
    timestamp = utc_now()
    deleted_entry_response: ContentEntryResponse | None = None
    try:
        with storage.connection() as connection, connection.transaction():
            existing_entry = get_entry_by_id(connection, entry_id)
            if existing_entry is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            deleted_entry_response = ContentEntryResponse.from_record(existing_entry)
            _record_entry_activity(
                connection,
                entry_id=entry_id,
                entry_row=existing_entry,
                action=ContentEntryActivityAction.DELETE.value,
                actor_user_id=user_id,
                timestamp=timestamp,
            )
            _run_search_indexing_hook(
                connection,
                operation='entry_delete_sync',
                context={
                    'entry_id': str(entry_id),
                    'content_type_id': str(existing_entry['content_type_id']),
                },
                hook=lambda: delete_search_document(connection, entry_id),
            )
            delete_entry(connection, entry_id)
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to delete content entry',
            code='CONTENT_ENTRY_DELETE_FAILED',
        ) from exc

    if deleted_entry_response is not None:
        publish_content_entry_event(
            event_type='content.entry.deleted',
            entry=deleted_entry_response,
            actor_id=user_id,
        )
        dispatch_content_entry_event(
            'content.entry.deleted',
            {
                'event': 'content.entry.deleted',
                'entry': deleted_entry_response.model_dump(mode='json'),
            },
        )


def _raise_version_conflict() -> None:
    """Raise a structured optimistic concurrency conflict."""

    raise ContentError(
        detail='Content entry version does not match the current stored version',
        code='CONTENT_ENTRY_VERSION_CONFLICT',
        status_code=HTTPStatus.CONFLICT,
    )


def _revision_action_for_status_change(
    existing_status: str, requested_status: ContentStatus
) -> ContentRevisionAction:
    """Return the revision action label for a status-aware update."""

    if requested_status is ContentStatus.PUBLISHED and existing_status != 'published':
        return ContentRevisionAction.PUBLISH
    if existing_status == 'published' and requested_status is ContentStatus.DRAFT:
        return ContentRevisionAction.UNPUBLISH
    return ContentRevisionAction.UPDATE


def _create_entry_revision(
    connection: Any,
    *,
    entry_row: Mapping[str, Any],
    action: ContentRevisionAction,
    user_id: UUID,
    timestamp: datetime,
    restore_source_revision_id: UUID | None = None,
) -> ContentEntryRevisionResponse:
    """Persist an immutable snapshot for a just-written entry row."""

    revision_row = create_content_entry_revision(
        connection,
        revision_id=uuid4(),
        entry_id=entry_row['id'],
        revision_number=int(entry_row['version']),
        action=action.value,
        slug=cast(str, entry_row['slug']),
        status=cast(str, entry_row['status']),
        payload=cast(dict[str, Any], entry_row['payload']),
        seo_metadata=ContentEntrySeoMetadata.from_record(entry_row).to_storage(),
        published_at=entry_row['published_at'],
        user_id=user_id,
        created_at=timestamp,
        restore_source_revision_id=restore_source_revision_id,
    )
    return ContentEntryRevisionResponse.from_record(revision_row)


def _ensure_publish_transition_allowed(
    current_user: Mapping[str, object],
    *,
    existing_status: str,
    target_status: ContentStatus,
) -> None:
    """Enforce publish permission for publishing and unpublishing transitions."""

    from pragma.auth.permissions import (
        PERMISSION_CONTENT_ENTRIES_PUBLISH,
        ensure_permission,
    )

    if target_status is ContentStatus.PUBLISHED or (
        existing_status == 'published' and target_status is not ContentStatus.PUBLISHED
    ):
        ensure_permission(current_user, PERMISSION_CONTENT_ENTRIES_PUBLISH)


def _invalid_transition(detail: str) -> ContentError:
    """Build a structured invalid workflow transition error."""

    return ContentError(
        detail=detail,
        code='CONTENT_ENTRY_TRANSITION_INVALID',
        status_code=HTTPStatus.CONFLICT,
    )


def _emit_entry_updated(entry_response: ContentEntryResponse, actor_id: UUID) -> None:
    """Emit realtime and module events for content entry changes."""

    from pragma.modules.service import dispatch_content_entry_event
    from pragma.realtime.service import publish_content_entry_event

    publish_content_entry_event(
        event_type='content.entry.updated',
        entry=entry_response,
        actor_id=actor_id,
    )
    dispatch_content_entry_event(
        'content.entry.updated',
        {
            'event': 'content.entry.updated',
            'entry': entry_response.model_dump(mode='json'),
        },
    )


def list_entry_revision_records(
    storage: DatabasePool, entry_id: UUID
) -> ContentEntryRevisionListResponse:
    """List immutable revisions for a content entry."""

    try:
        with storage.connection() as connection:
            if get_entry_by_id(connection, entry_id) is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            revision_rows = list_content_entry_revisions(connection, entry_id)
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to list content entry revisions',
            code='CONTENT_ENTRY_REVISION_LIST_FAILED',
        ) from exc

    return ContentEntryRevisionListResponse(
        items=[ContentEntryRevisionResponse.from_record(row) for row in revision_rows]
    )


def publish_entry_record(
    storage: DatabasePool,
    entry_id: UUID,
    payload: ContentEntryTransitionRequest,
    current_user: Mapping[str, object],
) -> ContentEntryResponse:
    """Publish a draft content entry through an explicit transition endpoint."""

    return _transition_entry_record(
        storage,
        entry_id,
        payload.expected_version,
        ContentStatus.PUBLISHED,
        ContentRevisionAction.PUBLISH,
        current_user,
    )


def unpublish_entry_record(
    storage: DatabasePool,
    entry_id: UUID,
    payload: ContentEntryTransitionRequest,
    current_user: Mapping[str, object],
) -> ContentEntryResponse:
    """Unpublish a published content entry through an explicit endpoint."""

    return _transition_entry_record(
        storage,
        entry_id,
        payload.expected_version,
        ContentStatus.DRAFT,
        ContentRevisionAction.UNPUBLISH,
        current_user,
    )


def _transition_entry_record(
    storage: DatabasePool,
    entry_id: UUID,
    expected_version: int | None,
    target_status: ContentStatus,
    action: ContentRevisionAction,
    current_user: Mapping[str, object],
) -> ContentEntryResponse:
    """Apply an explicit publish/unpublish state transition."""

    from pragma.search.service import sync_search_document

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    try:
        with storage.connection() as connection, connection.transaction():
            existing_entry = get_entry_by_id_for_update(connection, entry_id)
            if existing_entry is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            if target_status is ContentStatus.PUBLISHED and existing_entry['status'] != 'draft':
                raise _invalid_transition('Only draft entries can be published explicitly')
            if target_status is ContentStatus.DRAFT and existing_entry['status'] != 'published':
                raise _invalid_transition('Only published entries can be unpublished explicitly')
            _ensure_publish_transition_allowed(
                current_user,
                existing_status=cast(str, existing_entry['status']),
                target_status=target_status,
            )
            field_definitions = _field_definitions_from_rows(
                get_field_definitions(connection, existing_entry['content_type_id'])
            )
            published_at = _resolve_published_at(
                target_status,
                existing_entry['published_at'],
                timestamp,
            )
            entry_row = update_entry(
                connection=connection,
                entry_id=entry_id,
                slug=cast(str, existing_entry['slug']),
                status=target_status.value,
                payload=cast(dict[str, Any], existing_entry['payload']),
                seo_metadata=ContentEntrySeoMetadata.from_record(existing_entry).to_storage(),
                published_at=published_at,
                user_id=user_id,
                updated_at=timestamp,
                expected_version=expected_version,
            )
            if entry_row is None:
                _raise_version_conflict()
            entry_row = {
                **entry_row,
                'content_type_slug': existing_entry['content_type_slug'],
            }
            _create_entry_revision(
                connection,
                entry_row=entry_row,
                action=action,
                user_id=user_id,
                timestamp=timestamp,
            )
            _record_entry_activity(
                connection,
                entry_id=entry_id,
                entry_row=entry_row,
                action=action.value,
                actor_user_id=user_id,
                timestamp=timestamp,
            )
            _run_search_indexing_hook(
                connection,
                operation='entry_transition_sync',
                context={
                    'entry_id': str(entry_id),
                    'content_type_id': str(existing_entry['content_type_id']),
                },
                hook=lambda: sync_search_document(
                    connection,
                    entry_row=entry_row,
                    content_type_slug=cast(str, existing_entry['content_type_slug']),
                    field_definitions=field_definitions,
                ),
            )
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to transition content entry',
            code='CONTENT_ENTRY_TRANSITION_FAILED',
        ) from exc

    entry_response = ContentEntryResponse.from_record(entry_row)
    _emit_entry_updated(entry_response, user_id)
    return entry_response


def restore_entry_revision_record(
    storage: DatabasePool,
    entry_id: UUID,
    revision_id: UUID,
    payload: ContentEntryRevisionRestoreRequest,
    current_user: Mapping[str, object],
) -> ContentEntryResponse:
    """Restore an immutable revision by writing a new current version."""

    from pragma.content.models import ContentEntryActivityAction
    from pragma.search.service import sync_search_document

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    try:
        with storage.connection() as connection, connection.transaction():
            existing_entry = get_entry_by_id_for_update(connection, entry_id)
            if existing_entry is None:
                raise ContentError(
                    detail='Content entry not found',
                    code='CONTENT_ENTRY_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            revision_row = get_content_entry_revision(connection, entry_id, revision_id)
            if revision_row is None:
                raise ContentError(
                    detail='Content entry revision not found',
                    code='CONTENT_ENTRY_REVISION_NOT_FOUND',
                    status_code=HTTPStatus.NOT_FOUND,
                )
            target_status = ContentStatus(revision_row['status'])
            _ensure_publish_transition_allowed(
                current_user,
                existing_status=cast(str, existing_entry['status']),
                target_status=target_status,
            )
            field_definitions = _field_definitions_from_rows(
                get_field_definitions(connection, existing_entry['content_type_id'])
            )
            restored_payload = _validate_entry_payload(
                cast(dict[str, Any], revision_row['payload']),
                field_definitions,
                existing_payload=cast(dict[str, Any], existing_entry['payload']),
            )
            slug = _resolve_entry_slug(
                content_type_id=existing_entry['content_type_id'],
                content_type_slug=cast(str, existing_entry['content_type_slug']),
                requested_slug=cast(str, revision_row['slug']),
                existing_slug=None,
                payload=restored_payload,
                field_definitions=field_definitions,
                storage_connection=connection,
                entry_id=entry_id,
            )
            entry_row = update_entry(
                connection=connection,
                entry_id=entry_id,
                slug=slug,
                status=target_status.value,
                payload=restored_payload,
                seo_metadata=ContentEntrySeoMetadata.from_record(revision_row).to_storage(),
                published_at=revision_row['published_at'],
                user_id=user_id,
                updated_at=timestamp,
                expected_version=payload.expected_version,
            )
            if entry_row is None:
                _raise_version_conflict()
            entry_row = {
                **entry_row,
                'content_type_slug': existing_entry['content_type_slug'],
            }
            _create_entry_revision(
                connection,
                entry_row=entry_row,
                action=ContentRevisionAction.RESTORE,
                user_id=user_id,
                timestamp=timestamp,
                restore_source_revision_id=revision_id,
            )
            _record_entry_activity(
                connection,
                entry_id=entry_id,
                entry_row=entry_row,
                action=ContentEntryActivityAction.RESTORE.value,
                actor_user_id=user_id,
                timestamp=timestamp,
                details={'restore_source_revision_id': str(revision_id)},
            )
            _run_search_indexing_hook(
                connection,
                operation='entry_restore_sync',
                context={
                    'entry_id': str(entry_id),
                    'content_type_id': str(existing_entry['content_type_id']),
                },
                hook=lambda: sync_search_document(
                    connection,
                    entry_row=entry_row,
                    content_type_slug=cast(str, existing_entry['content_type_slug']),
                    field_definitions=field_definitions,
                ),
            )
    except ContentError:
        raise
    except IntegrityError as exc:
        raise ContentError(
            detail='An entry with this slug already exists for the content type',
            code='ENTRY_SLUG_CONFLICT',
            status_code=HTTPStatus.CONFLICT,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to restore content entry revision',
            code='CONTENT_ENTRY_REVISION_RESTORE_FAILED',
        ) from exc

    entry_response = ContentEntryResponse.from_record(entry_row)
    _emit_entry_updated(entry_response, user_id)
    return entry_response
