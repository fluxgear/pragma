# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Semantic and safety validation for block documents."""

from __future__ import annotations

import re
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import ValidationError

from pragma.blocks.registry import CORE_BLOCK_REGISTRY, BlockDefinition, PropRule
from pragma.blocks.schema import BlockDocument, BlockNode

MAX_BLOCK_DEPTH = 8
MAX_BLOCK_COUNT = 100
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
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
_MARKUP_PATTERN = re.compile(r"[<>]")


class BlockDocumentValidationError(ValueError):
    """Raised when a block document violates the storage contract."""


class _RichTextSafetyValidator(HTMLParser):
    """Validate the same restricted HTML subset used by content rich text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag not in _ALLOWED_RICH_TEXT_TAGS:
            raise BlockDocumentValidationError(
                f"contains unsupported rich-text HTML tag '{tag}'"
            )
        if attrs:
            raise BlockDocumentValidationError(
                f"contains unsupported rich-text HTML attributes on '<{tag}>'"
            )
        if tag not in _VOID_RICH_TEXT_TAGS:
            self._stack.append(tag)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag not in _VOID_RICH_TEXT_TAGS:
            raise BlockDocumentValidationError(
                f"contains unsupported self-closing rich-text HTML tag '{tag}'"
            )
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_RICH_TEXT_TAGS:
            raise BlockDocumentValidationError(
                f"contains an unexpected closing tag '</{tag}>'"
            )
        if not self._stack:
            raise BlockDocumentValidationError(
                f"contains an unexpected closing tag '</{tag}>'"
            )
        expected_tag = self._stack.pop()
        if expected_tag != tag:
            raise BlockDocumentValidationError(
                "contains mismatched rich-text HTML tags: expected "
                f"'</{expected_tag}>' before '</{tag}>'"
            )

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)

    def handle_comment(self, data: str) -> None:
        raise BlockDocumentValidationError("contains unsupported rich-text HTML comments")

    def handle_decl(self, decl: str) -> None:
        raise BlockDocumentValidationError("contains unsupported rich-text HTML declarations")

    def unknown_decl(self, data: str) -> None:
        raise BlockDocumentValidationError("contains unsupported rich-text HTML declarations")

    def handle_pi(self, data: str) -> None:
        raise BlockDocumentValidationError(
            "contains unsupported rich-text processing instructions"
        )

    def close(self) -> None:
        super().close()
        if self._stack:
            unclosed_tag = self._stack[-1]
            raise BlockDocumentValidationError(
                f"contains an unclosed rich-text HTML tag '<{unclosed_tag}>'"
            )


def validate_block_document(value: Any) -> dict[str, Any]:
    """Validate and normalize a versioned block document.

    Args:
        value: Raw JSON-compatible value from content entry payload/defaults.

    Returns:
        dict[str, Any]: Deterministic JSON-ready block document.

    Raises:
        BlockDocumentValidationError: If validation fails.
    """

    if not isinstance(value, Mapping):
        raise BlockDocumentValidationError("block document must be an object")
    version = value.get("version")
    if version != 1:
        raise BlockDocumentValidationError(
            f"unsupported block document version '{version}'"
        )
    try:
        document = BlockDocument.model_validate(value)
    except ValidationError as exc:
        raise BlockDocumentValidationError("block document shape is invalid") from exc

    state = {"count": 0}
    _validate_node(document.root, depth=1, parent_type=None, state=state)
    if document.root.type != "section":
        raise BlockDocumentValidationError("block document root must be a section block")
    return document.model_dump(mode="json", exclude_none=True)


def _validate_node(
    node: BlockNode,
    *,
    depth: int,
    parent_type: str | None,
    state: dict[str, int],
) -> None:
    if depth > MAX_BLOCK_DEPTH:
        raise BlockDocumentValidationError("block document exceeds maximum tree depth")
    state["count"] += 1
    if state["count"] > MAX_BLOCK_COUNT:
        raise BlockDocumentValidationError("block document exceeds maximum block count")

    definition = CORE_BLOCK_REGISTRY.get(node.type)
    if definition is None:
        raise BlockDocumentValidationError(f"unknown block type '{node.type}'")
    if parent_type is not None:
        parent = CORE_BLOCK_REGISTRY[parent_type]
        if node.type not in parent.allowed_children:
            raise BlockDocumentValidationError(
                f"block '{node.type}' is not allowed inside '{parent_type}'"
            )

    _validate_named_values("props", node.props, definition.props, node.type)
    _validate_named_values("settings", node.settings, definition.settings, node.type)
    _validate_children(node, definition, state=state, depth=depth)


def _validate_children(
    node: BlockNode,
    definition: BlockDefinition,
    *,
    state: dict[str, int],
    depth: int,
) -> None:
    child_count = len(node.children)
    if child_count < definition.min_children:
        raise BlockDocumentValidationError(
            f"block '{node.type}' requires at least {definition.min_children} child blocks"
        )
    if child_count > definition.max_children:
        raise BlockDocumentValidationError(
            f"block '{node.type}' allows at most {definition.max_children} child blocks"
        )
    if child_count and not definition.allowed_children:
        raise BlockDocumentValidationError(f"block '{node.type}' cannot have child blocks")
    if node.type == "columns":
        expected = node.props.get("columns")
        if child_count != expected:
            raise BlockDocumentValidationError(
                "columns block child count must match its columns prop"
            )
    for child in node.children:
        _validate_node(child, depth=depth + 1, parent_type=node.type, state=state)


def _validate_named_values(
    value_name: str,
    values: Mapping[str, Any],
    rules: Mapping[str, PropRule],
    block_type: str,
) -> None:
    unknown = sorted(set(values) - set(rules))
    if unknown:
        names = ", ".join(unknown)
        raise BlockDocumentValidationError(
            f"block '{block_type}' has unsupported {value_name}: {names}"
        )
    missing = sorted(name for name, rule in rules.items() if rule.required and name not in values)
    if missing:
        names = ", ".join(missing)
        raise BlockDocumentValidationError(
            f"block '{block_type}' is missing required {value_name}: {names}"
        )
    for name, raw_value in values.items():
        _validate_rule(raw_value, rules[name], block_type=block_type, name=name)
    if (
        block_type == "image"
        and value_name == "props"
        and "media_id" not in values
        and "src" not in values
    ):
        raise BlockDocumentValidationError(
            "image block requires either media_id or src"
        )


def _validate_rule(
    value: Any,
    rule: PropRule,
    *,
    block_type: str,
    name: str,
) -> None:
    if rule.kind in {"string", "plain_text", "rich_text", "url", "uuid"}:
        if not isinstance(value, str):
            raise BlockDocumentValidationError(
                f"block '{block_type}' value '{name}' must be a string"
            )
        if rule.kind == "plain_text":
            _validate_plain_text(value, block_type=block_type, name=name)
        elif rule.kind == "rich_text":
            _validate_rich_text(value, block_type=block_type, name=name)
        elif rule.kind == "url":
            _validate_url(value, block_type=block_type, name=name)
        elif rule.kind == "uuid":
            _validate_uuid(value, block_type=block_type, name=name)
        _validate_string_bounds(value, rule, block_type=block_type, name=name)
        return

    if rule.kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise BlockDocumentValidationError(
                f"block '{block_type}' value '{name}' must be an integer"
            )
        if rule.minimum is not None and value < rule.minimum:
            raise BlockDocumentValidationError(
                f"block '{block_type}' value '{name}' is below minimum"
            )
        if rule.maximum is not None and value > rule.maximum:
            raise BlockDocumentValidationError(
                f"block '{block_type}' value '{name}' is above maximum"
            )
        return

    if rule.kind == "enum":
        if not isinstance(value, str) or value not in rule.choices:
            raise BlockDocumentValidationError(
                f"block '{block_type}' value '{name}' must be a supported option"
            )
        return

    if rule.kind == "string_list":
        _validate_string_list(value, rule, block_type=block_type, name=name)
        return

    raise BlockDocumentValidationError(
        f"block '{block_type}' value '{name}' uses unsupported validation"
    )


def _validate_string_bounds(
    value: str,
    rule: PropRule,
    *,
    block_type: str,
    name: str,
) -> None:
    if rule.min_length is not None and len(value.strip()) < rule.min_length:
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' is too short"
        )
    if rule.max_length is not None and len(value) > rule.max_length:
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' is too long"
        )


def _validate_plain_text(value: str, *, block_type: str, name: str) -> None:
    if _CONTROL_CHAR_PATTERN.search(value) or _MARKUP_PATTERN.search(value):
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' contains unsafe text"
        )


def _validate_rich_text(value: str, *, block_type: str, name: str) -> None:
    parser = _RichTextSafetyValidator()
    try:
        parser.feed(value)
        parser.close()
    except BlockDocumentValidationError as exc:
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' {exc}"
        ) from exc
    text_length = len(re.sub(r"\s+", " ", "".join(parser.text_parts)).strip())
    if text_length < 1:
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' is too short"
        )


def _validate_url(value: str, *, block_type: str, name: str) -> None:
    if _CONTROL_CHAR_PATTERN.search(value) or _MARKUP_PATTERN.search(value):
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' contains an unsafe URL"
        )
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme not in {"http", "https", "mailto", "tel"}:
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' uses an unsupported URL scheme"
        )
    if not parsed.scheme and not value.startswith(("/", "#")):
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' must be absolute or site-relative"
        )


def _validate_uuid(value: str, *, block_type: str, name: str) -> None:
    try:
        UUID(value)
    except ValueError as exc:
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' must be a UUID"
        ) from exc


def _validate_string_list(
    value: Any,
    rule: PropRule,
    *,
    block_type: str,
    name: str,
) -> None:
    if not isinstance(value, list):
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' must be a list"
        )
    if rule.max_items is not None and len(value) > rule.max_items:
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' has too many items"
        )
    if rule.min_length is not None and not value:
        raise BlockDocumentValidationError(
            f"block '{block_type}' value '{name}' must not be empty"
        )
    for item in value:
        if not isinstance(item, str):
            raise BlockDocumentValidationError(
                f"block '{block_type}' value '{name}' items must be strings"
            )
        _validate_plain_text(item, block_type=block_type, name=name)
        _validate_string_bounds(item, rule, block_type=block_type, name=name)
