# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Fail-closed registry for core block types and capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pragma.blocks.schema import STABLE_BLOCK_TYPES

type PropKind = Literal[
    "string",
    "plain_text",
    "rich_text",
    "integer",
    "enum",
    "url",
    "uuid",
    "string_list",
]


@dataclass(frozen=True)
class PropRule:
    """Validation rule for a block prop or setting."""

    kind: PropKind
    required: bool = False
    min_length: int | None = None
    max_length: int | None = None
    minimum: int | None = None
    maximum: int | None = None
    choices: tuple[str, ...] = ()
    max_items: int | None = None


@dataclass(frozen=True)
class BlockDefinition:
    """Registry definition for one stable core block type."""

    type: str
    allowed_children: tuple[str, ...] = ()
    min_children: int = 0
    max_children: int = 0
    props: dict[str, PropRule] = field(default_factory=dict)
    settings: dict[str, PropRule] = field(default_factory=dict)


TEXT_CHILDREN = (
    "heading",
    "paragraph",
    "image",
    "button",
    "divider",
    "spacer",
    "quote",
    "list",
    "card",
)
LAYOUT_CHILDREN = ("container", "columns", *TEXT_CHILDREN)
SECTION_SETTINGS = {
    "background": PropRule("enum", choices=("none", "muted", "accent")),
    "width": PropRule("enum", choices=("full", "wide", "narrow")),
}
TEXT_ALIGN_SETTING = {
    "align": PropRule("enum", choices=("left", "center", "right")),
}

CORE_BLOCK_REGISTRY: dict[str, BlockDefinition] = {
    "section": BlockDefinition(
        type="section",
        allowed_children=LAYOUT_CHILDREN,
        max_children=24,
        settings=SECTION_SETTINGS,
    ),
    "container": BlockDefinition(
        type="container",
        allowed_children=LAYOUT_CHILDREN,
        max_children=24,
        settings=SECTION_SETTINGS,
    ),
    "columns": BlockDefinition(
        type="columns",
        allowed_children=("container",),
        min_children=2,
        max_children=4,
        props={"columns": PropRule("integer", required=True, minimum=2, maximum=4)},
    ),
    "heading": BlockDefinition(
        type="heading",
        props={
            "text": PropRule("plain_text", required=True, min_length=1, max_length=200),
            "level": PropRule("integer", required=True, minimum=1, maximum=6),
        },
        settings=TEXT_ALIGN_SETTING,
    ),
    "paragraph": BlockDefinition(
        type="paragraph",
        props={
            "html": PropRule("rich_text", required=True, min_length=1, max_length=6000)
        },
        settings=TEXT_ALIGN_SETTING,
    ),
    "image": BlockDefinition(
        type="image",
        props={
            "media_id": PropRule("uuid"),
            "src": PropRule("url", max_length=2000),
            "alt": PropRule("plain_text", required=True, max_length=200),
            "caption": PropRule("plain_text", max_length=300),
        },
        settings={
            "align": PropRule(
                "enum",
                choices=("left", "center", "right", "wide"),
            )
        },
    ),
    "button": BlockDefinition(
        type="button",
        props={
            "label": PropRule("plain_text", required=True, min_length=1, max_length=80),
            "href": PropRule("url", required=True, max_length=2000),
        },
        settings={"variant": PropRule("enum", choices=("primary", "secondary", "link"))},
    ),
    "divider": BlockDefinition(type="divider"),
    "spacer": BlockDefinition(
        type="spacer",
        props={"size": PropRule("enum", required=True, choices=("small", "medium", "large"))},
    ),
    "quote": BlockDefinition(
        type="quote",
        props={
            "text": PropRule("plain_text", required=True, min_length=1, max_length=800),
            "citation": PropRule("plain_text", max_length=200),
        },
    ),
    "list": BlockDefinition(
        type="list",
        props={
            "style": PropRule("enum", required=True, choices=("unordered", "ordered")),
            "items": PropRule(
                "string_list",
                required=True,
                min_length=1,
                max_length=240,
                max_items=24,
            ),
        },
    ),
    "card": BlockDefinition(
        type="card",
        allowed_children=TEXT_CHILDREN[:-1],
        max_children=12,
        settings={"variant": PropRule("enum", choices=("plain", "outlined", "elevated"))},
    ),
}

if tuple(CORE_BLOCK_REGISTRY) != STABLE_BLOCK_TYPES:
    raise RuntimeError("Core block registry keys must match stable block type order")
