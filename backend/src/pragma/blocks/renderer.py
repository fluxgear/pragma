# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Safe public HTML renderer for validated block documents."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from html import escape
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import nh3

_ALLOWED_RICH_TEXT_TAGS = frozenset(
    {
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
)
_SCRIPT_STYLE_PATTERN = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>",
    flags=re.IGNORECASE | re.DOTALL,
)
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
_MEDIA_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

MediaUrlResolver = Callable[[str | None], str | None]


def render_block_document(
    document: Mapping[str, Any],
    *,
    media_url_resolver: MediaUrlResolver | None = None,
) -> str:
    """Render a block document to safe public HTML.

    Args:
        document: Versioned block-document payload loaded from storage.
        media_url_resolver: Optional callback for converting stored media URLs.

    Returns:
        str: Safe HTML fragment. Unknown or malformed blocks are omitted.

    Raises:
        None.
    """

    if not isinstance(document, Mapping):
        return ""
    root = document.get("root")
    if not isinstance(root, Mapping):
        return ""
    return _render_node(root, media_url_resolver=media_url_resolver)


def _render_node(
    node: Mapping[str, Any],
    *,
    media_url_resolver: MediaUrlResolver | None,
) -> str:
    block_type = node.get("type")
    if not isinstance(block_type, str):
        return ""
    props = _mapping(node.get("props"))
    settings = _mapping(node.get("settings"))
    children = _children(node.get("children"))
    rendered_children = "".join(
        _render_node(child, media_url_resolver=media_url_resolver) for child in children
    )

    if block_type == "section":
        classes = _classes(
            "pragma-block",
            "pragma-block--section",
            _choice_class("pragma-block--width", settings.get("width")),
            _choice_class("pragma-block--background", settings.get("background")),
        )
        return f'<section class="{classes}">{rendered_children}</section>'
    if block_type == "container":
        classes = _classes(
            "pragma-block",
            "pragma-block--container",
            _choice_class("pragma-block--width", settings.get("width")),
            _choice_class("pragma-block--background", settings.get("background")),
        )
        return f'<div class="{classes}">{rendered_children}</div>'
    if block_type == "columns":
        columns = props.get("columns")
        column_count = columns if isinstance(columns, int) and 2 <= columns <= 4 else len(children)
        column_class = f"pragma-block--columns-{max(1, min(column_count, 4))}"
        classes = _classes("pragma-block", "pragma-block--columns", column_class)
        return f'<div class="{classes}">{rendered_children}</div>'
    if block_type == "heading":
        text = _text(props.get("text"))
        if not text:
            return ""
        level = props.get("level")
        heading_level = level if isinstance(level, int) and 1 <= level <= 6 else 2
        classes = _classes(
            "pragma-block",
            "pragma-block--heading",
            _choice_class("pragma-block--align", settings.get("align")),
        )
        return f'<h{heading_level} class="{classes}">{escape(text)}</h{heading_level}>'
    if block_type == "paragraph":
        rich_text = _rich_text(props.get("html"))
        if not rich_text:
            return ""
        classes = _classes(
            "pragma-block",
            "pragma-block--paragraph",
            _choice_class("pragma-block--align", settings.get("align")),
        )
        return f'<div class="{classes}">{rich_text}</div>'
    if block_type == "image":
        return _render_image(props, settings, media_url_resolver=media_url_resolver)
    if block_type == "button":
        return _render_button(props, settings)
    if block_type == "divider":
        return '<hr class="pragma-block pragma-block--divider">'
    if block_type == "spacer":
        size = _choice_class("pragma-block--spacer", props.get("size"))
        classes = _classes("pragma-block", "pragma-block--spacer", size)
        return f'<div class="{classes}" aria-hidden="true"></div>'
    if block_type == "quote":
        return _render_quote(props)
    if block_type == "list":
        return _render_list(props)
    if block_type == "card":
        variant = _choice_class("pragma-block--card", settings.get("variant"))
        classes = _classes("pragma-block", "pragma-block--card", variant)
        return f'<article class="{classes}">{rendered_children}</article>'

    return ""


def _render_image(
    props: Mapping[str, Any],
    settings: Mapping[str, Any],
    *,
    media_url_resolver: MediaUrlResolver | None,
) -> str:
    raw_src = _image_src(props, media_url_resolver=media_url_resolver)
    src = _safe_url(raw_src) if raw_src is not None else None
    alt = _text(props.get("alt"))
    if src is None or alt is None:
        return ""
    align = _choice_class("pragma-block--align", settings.get("align"))
    classes = _classes("pragma-block", "pragma-block--image", align)
    image_html = (
        f'<img src="{escape(src, quote=True)}" alt="{escape(alt, quote=True)}" loading="lazy">'
    )
    caption = _text(props.get("caption"))
    caption_html = f'<figcaption>{escape(caption)}</figcaption>' if caption else ""
    return f'<figure class="{classes}">{image_html}{caption_html}</figure>'


def _render_button(props: Mapping[str, Any], settings: Mapping[str, Any]) -> str:
    label = _text(props.get("label"))
    if not label:
        return ""
    href = _safe_url(_text(props.get("href")))
    variant = _choice_class("pragma-block--button", settings.get("variant"))
    classes = _classes("pragma-block", "pragma-block--button", variant)
    escaped_label = escape(label)
    if href is None:
        return f'<span class="{classes}">{escaped_label}</span>'
    return f'<a class="{classes}" href="{escape(href, quote=True)}">{escaped_label}</a>'


def _render_quote(props: Mapping[str, Any]) -> str:
    text = _text(props.get("text"))
    if not text:
        return ""
    citation = _text(props.get("citation"))
    citation_html = f'<cite>{escape(citation)}</cite>' if citation else ""
    return (
        '<blockquote class="pragma-block pragma-block--quote">'
        f'<p>{escape(text)}</p>{citation_html}</blockquote>'
    )


def _render_list(props: Mapping[str, Any]) -> str:
    items = props.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return ""
    rendered_items = [
        f'<li>{escape(item)}</li>'
        for item in (_text(item) for item in items)
        if item
    ]
    if not rendered_items:
        return ""
    tag = "ol" if props.get("style") == "ordered" else "ul"
    return (
        f'<{tag} class="pragma-block pragma-block--list">'
        f'{"".join(rendered_items)}</{tag}>'
    )


def _image_src(
    props: Mapping[str, Any],
    *,
    media_url_resolver: MediaUrlResolver | None,
) -> str | None:
    media_id = _text(props.get("media_id"))
    if media_id and _MEDIA_UUID_PATTERN.fullmatch(media_id):
        try:
            normalized_media_id = str(UUID(media_id))
        except ValueError:
            return None
        return f"/media/{normalized_media_id}/content"

    src = _text(props.get("src"))
    if src is None:
        return None
    if media_url_resolver is None:
        return src
    return media_url_resolver(src)


def _rich_text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    without_executable_blocks = _SCRIPT_STYLE_PATTERN.sub("", value)
    return nh3.clean(
        without_executable_blocks,
        tags=_ALLOWED_RICH_TEXT_TAGS,
        attributes={},
        strip_comments=True,
    )


def _safe_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if (
        not normalized
        or _CONTROL_CHAR_PATTERN.search(normalized)
        or "<" in normalized
        or ">" in normalized
    ):
        return None
    parsed = urlsplit(normalized)
    if parsed.scheme and parsed.scheme not in {"http", "https", "mailto", "tel"}:
        return None
    if not parsed.scheme and not normalized.startswith(("/", "#")):
        return None
    return normalized


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _children(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if (
        _CONTROL_CHAR_PATTERN.search(normalized)
        or "<" in normalized
        or ">" in normalized
    ):
        return None
    return normalized


def _choice_class(prefix: str, value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("_", "-")
    if not normalized or not re.fullmatch(r"[a-z0-9-]+", normalized):
        return None
    return f"{prefix}-{normalized}"


def _classes(*values: str | None) -> str:
    return " ".join(value for value in values if value)
