# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Typed block-document JSON schema models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BLOCK_DOCUMENT_VERSION = 1
SUPPORTED_BLOCK_DOCUMENT_VERSIONS = frozenset({BLOCK_DOCUMENT_VERSION})
STABLE_BLOCK_TYPES = (
    "section",
    "container",
    "columns",
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


class BlockNode(BaseModel):
    """Single typed node in a block-document tree."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: str = Field(min_length=1, max_length=64)
    props: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)
    children: list[BlockNode] = Field(default_factory=list, max_length=32)


class BlockDocument(BaseModel):
    """Versioned JSON block document rooted at a block node."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    root: BlockNode
