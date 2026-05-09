# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Public frontend view-model contracts.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PublicSiteContext:
    """Site-level context used by all public templates.

    Args:
        name: Public site name.
        description: Public site description.
        base_url: Canonical base URL for SEO metadata.
        lang: Public site language tag.
        design: Sanitized public design settings for theme templates.
        navigation: Primary navigation link entries.
        footer_links: Footer navigation link entries.

    Returns:
        None.

    Raises:
        None.
    """

    name: str
    description: str
    base_url: str
    lang: str = 'en'
    design: dict[str, object] = field(default_factory=dict)
    navigation: list[dict[str, str]] = field(default_factory=list)
    footer_links: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class PublicSeoContext:
    """SEO metadata context for public pages.

    Args:
        title: Rendered title text.
        description: Rendered description text.
        canonical_url: Canonical absolute URL.
        robots: Robots meta directive.
        og_type: OpenGraph content type.
        og_title: OpenGraph title.
        og_description: OpenGraph description.
        og_url: OpenGraph canonical URL.
        og_image: Optional OpenGraph image URL.

    Returns:
        None.

    Raises:
        None.
    """

    title: str
    description: str
    canonical_url: str
    robots: str
    og_type: str
    og_title: str
    og_description: str
    og_url: str
    og_image: str | None = None


@dataclass(slots=True)
class PublicEntryView:
    """Public-facing entry projection for page/post/archive/search templates.

    Args:
        content_type_slug: Owning content-type slug.
        slug: Entry slug.
        url: Public URL for the entry.
        title: Display title.
        subtitle: Display subtitle or dek.
        summary: Summary or excerpt text.
        body_html: Rich content HTML payload.
        author: Author display name.
        category: Category display label.
        published_at: Display publish timestamp text.
        reading_time: Estimated reading-time label.
        featured_image_url: Optional featured image URL.
        featured_image_alt: Optional featured image alt text.

    Returns:
        None.

    Raises:
        None.
    """

    content_type_slug: str
    slug: str
    url: str
    title: str
    subtitle: str
    summary: str
    body_html: str
    author: str
    category: str
    published_at: str
    reading_time: str
    featured_image_url: str | None = None
    featured_image_alt: str | None = None


@dataclass(slots=True)
class PublicPagination:
    """Pagination metadata for public list views.

    Args:
        page: Current one-based page.
        per_page: Entries per page.
        total: Total matching entries.
        total_pages: Total available pages.
        has_previous: Whether a previous page exists.
        has_next: Whether a next page exists.
        prev_url: Previous-page URL when available.
        next_url: Next-page URL when available.

    Returns:
        None.

    Raises:
        None.
    """

    page: int
    per_page: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool
    prev_url: str | None = None
    next_url: str | None = None
