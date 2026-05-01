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
from pragma.content.models import (
    BooleanFieldDefinition,
    ContentEntryCreateRequest,
    ContentEntryListParams,
    ContentEntryListResponse,
    ContentEntryResponse,
    ContentEntryUpdateRequest,
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
    count_entries_for_content_type,
    create_content_type,
    create_entry,
    delete_content_type_if_unused,
    delete_entry,
    get_content_type_by_id,
    get_content_type_by_id_for_key_share,
    get_content_type_by_id_for_update,
    get_content_type_by_slug,
    get_entry_by_id,
    get_entry_by_slug,
    get_field_definitions,
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
    return {
        "name": dumped["name"],
        "label": dumped["label"],
        "kind": dumped["kind"],
        "required": dumped["required"],
        "config": {
            key: value
            for key, value in dumped.items()
            if key not in {"name", "label", "kind", "required"} and value is not None
        },
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
            continue

        if isinstance(field_definition, IntegerFieldDefinition | NumberFieldDefinition) and (
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


def _build_content_type_response(
    content_type_row: Mapping[str, Any],
    field_rows: Sequence[Mapping[str, Any]],
) -> ContentTypeResponse:
    """Build a content-type response from storage rows.

    Args:
        content_type_row: Content-type storage row.
        field_rows: Field-definition storage rows for the content type.

    Returns:
        ContentTypeResponse: Serialized content-type response model.

    Raises:
        ValidationError: If the stored data cannot be parsed.
    """

    return ContentTypeResponse.from_record(
        content_type_row,
        _field_definitions_from_rows(field_rows),
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

    return _build_content_type_response(content_type_row, field_rows)


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
            fields_by_content_type = list_field_definitions(
                connection, [row["id"] for row in content_type_rows]
            )
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to list content types",
            code="CONTENT_TYPE_LIST_FAILED",
        ) from exc

    items = [
        _build_content_type_response(
            row,
            fields_by_content_type.get(cast(UUID, row["id"]), []),
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
    except ContentError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to load content type",
            code="CONTENT_TYPE_LOOKUP_FAILED",
        ) from exc

    return _build_content_type_response(content_type_row, field_rows)


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
            existing_type = get_content_type_by_id(connection, content_type_id)
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

            for entry_row in list_entries_for_content_type_validation(connection, content_type_id):
                entry_payload = cast(dict[str, Any], entry_row["payload"])
                try:
                    _validate_entry_payload(
                        entry_payload,
                        field_definitions,
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
            _run_search_indexing_hook(
                connection,
                operation="content_type_rebuild",
                context={"content_type_id": str(content_type_id)},
                hook=lambda: rebuild_search_documents_for_content_type(
                    connection,
                    content_type_id=content_type_id,
                    field_rows=field_rows,
                ),
            )
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

    return _build_content_type_response(content_type_row, field_rows)


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
    """Create a content entry within a content type.

    Args:
        storage: Initialized database pool manager.
        payload: Content-entry creation payload.
        current_user: Authenticated user context.

    Returns:
        ContentEntryResponse: Created content-entry response.

    Raises:
        ContentError: If the entry payload is invalid.
        StorageError: If PostgreSQL access fails.
    """

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
            entry_row = create_entry(
                connection=connection,
                entry_id=uuid4(),
                content_type_id=payload.content_type_id,
                slug=slug,
                status=payload.status.value,
                payload=validated_payload,
                published_at=published_at,
                user_id=user_id,
                created_at=timestamp,
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

    entry_response = ContentEntryResponse.from_record(
        {**entry_row, 'content_type_slug': content_type_row['slug']}
    )
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


def update_entry_record(
    storage: DatabasePool,
    entry_id: UUID,
    payload: ContentEntryUpdateRequest,
    current_user: Mapping[str, object],
) -> ContentEntryResponse:
    """Update an existing content entry.

    Args:
        storage: Initialized database pool manager.
        entry_id: Content-entry identifier to update.
        payload: Content-entry update payload.
        current_user: Authenticated user context.

    Returns:
        ContentEntryResponse: Updated content-entry response.

    Raises:
        ContentError: If the entry payload is invalid.
        StorageError: If PostgreSQL access fails.
    """

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
            existing_entry = get_entry_by_id(connection, entry_id)
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
            entry_row = update_entry(
                connection=connection,
                entry_id=entry_id,
                slug=slug,
                status=payload.status.value,
                payload=validated_payload,
                published_at=published_at,
                user_id=user_id,
                updated_at=timestamp,
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

    entry_response = ContentEntryResponse.from_record(
        {**entry_row, 'content_type_slug': existing_entry['content_type_slug']}
    )
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


def delete_entry_record(storage: DatabasePool, entry_id: UUID) -> None:
    """Delete a content entry by identifier.

    Args:
        storage: Initialized database pool manager.
        entry_id: Content-entry identifier to delete.

    Returns:
        None.

    Raises:
        ContentError: If the entry does not exist.
        StorageError: If PostgreSQL access fails.
    """

    from pragma.modules.service import dispatch_content_entry_event
    from pragma.realtime.service import publish_content_entry_event
    from pragma.search.service import delete_search_document

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
            actor_id=None,
        )
        dispatch_content_entry_event(
            'content.entry.deleted',
            {
                'event': 'content.entry.deleted',
                'entry': deleted_entry_response.model_dump(mode='json'),
            },
        )
