# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Service helpers for Pragma public frontend rendering.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import asdict
from datetime import datetime
from html import escape, unescape
from typing import Any
from urllib.parse import urlencode, urlsplit

import nh3
from fastapi.responses import HTMLResponse

from pragma.blocks.renderer import render_block_document
from pragma.config import Settings
from pragma.content.models import ContentStatus
from pragma.errors import ThemeError
from pragma.public.models import (
    PublicEntryView,
    PublicPagination,
    PublicSeoContext,
    PublicSiteContext,
)
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.content import (
    count_entries,
    get_content_type_by_slug,
    get_entry_by_slug,
    list_entries,
)
from pragma.themes import ThemeRuntime

logger = logging.getLogger(__name__)

_DEFAULT_SITE_NAME = 'Pragma'
_DEFAULT_SITE_DESCRIPTION = 'Commercial-grade publishing and presentation for modern teams.'
_DEFAULT_AUTHOR = 'Editorial Team'
_DEFAULT_CATEGORY = 'Content'
_WORDS_PER_MINUTE = 200
_WHITESPACE_PATTERN = re.compile(r'\s+')
_HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
_MEDIA_UUID_PATTERN = (
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
    r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
)
_MEDIA_API_CONTENT_URL_PATTERN = re.compile(
    rf'^(?:https?://[^/]+)?/api/v1/media/assets/(?P<media_id>{_MEDIA_UUID_PATTERN})/content$'
)
_MEDIA_API_VARIANT_URL_PATTERN = re.compile(
    rf'^(?:https?://[^/]+)?/api/v1/media/assets/'
    rf'(?P<media_id>{_MEDIA_UUID_PATTERN})/variants/(?P<variant_name>[A-Za-z0-9_-]+)$'
)
_RICH_TEXT_FIELD_METADATA_KEY = '__pragma_rich_text_fields'
_PUBLIC_BODY_HTML_TAGS = frozenset(
    {
        'blockquote',
        'br',
        'code',
        'em',
        'h1',
        'h2',
        'h3',
        'h4',
        'h5',
        'h6',
        'hr',
        'li',
        'ol',
        'p',
        'pre',
        's',
        'strong',
        'ul',
    }
)

_BLOCK_DOCUMENT_FIELD_METADATA_KEY = '__pragma_block_document_fields'

def _collapse_whitespace(value: str) -> str:
    """Collapse internal whitespace and trim the result.

    Args:
        value: Raw text value.

    Returns:
        str: Normalized text.

    Raises:
        None.
    """

    return _WHITESPACE_PATTERN.sub(' ', value).strip()


def _slug_to_title(slug: str) -> str:
    """Convert a slug-style value into display text.

    Args:
        slug: Slug-like source text.

    Returns:
        str: Title-cased display text.

    Raises:
        None.
    """

    normalized = _collapse_whitespace(slug.replace('-', ' ').replace('_', ' '))
    return normalized.title() if normalized else 'Untitled'


def _extract_text(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """Return the first non-empty string value from payload keys.

    Args:
        payload: Entry payload dictionary.
        keys: Candidate field names in preference order.

    Returns:
        str | None: Normalized text when found.

    Raises:
        None.
    """

    for key in keys:
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        normalized = _collapse_whitespace(value)
        if normalized:
            return normalized
    return None


def _normalize_rich_text_field_names(value: Any) -> tuple[str, ...]:
    """Normalize rich-text field names from metadata payloads.

    Args:
        value: Candidate metadata payload value.

    Returns:
        tuple[str, ...]: Deduplicated normalized rich-text field names.

    Raises:
        None.
    """

    if not isinstance(value, (list, tuple, set)):
        return ()

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        field_name = _collapse_whitespace(item)
        if not field_name:
            continue
        if field_name in seen:
            continue
        seen.add(field_name)
        normalized.append(field_name)
    return tuple(normalized)


def _extract_rich_text_field_names(field_definitions: list[dict[str, Any]]) -> tuple[str, ...]:
    """Extract declared rich-text field names from a content-type schema.

    Args:
        field_definitions: Storage-layer field definition rows.

    Returns:
        tuple[str, ...]: Rich-text field names declared for the content type.

    Raises:
        None.
    """

    rich_text_names = [
        row.get('name')
        for row in field_definitions
        if str(row.get('field_type') or '') == 'rich_text'
    ]
    return _normalize_rich_text_field_names(rich_text_names)


def _extract_block_document_field_names(
    field_definitions: list[dict[str, Any]],
) -> tuple[str, ...]:
    """Extract declared block-document field names from a content-type schema.

    Args:
        field_definitions: Storage-layer field definition rows.

    Returns:
        tuple[str, ...]: Block-document field names declared for the content type.

    Raises:
        None.
    """

    block_document_names: list[Any] = []
    for row in field_definitions:
        config = row.get('config')
        config_kind = config.get('kind') if isinstance(config, dict) else None
        if str(row.get('field_type') or '') == 'block_document' or config_kind == 'block_document':
            block_document_names.append(row.get('name'))
    return _normalize_rich_text_field_names(block_document_names)


def _load_rich_text_field_names(connection: Any, content_type_id: Any) -> tuple[str, ...]:
    """Load rich-text field names for one content type.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier.

    Returns:
        tuple[str, ...]: Rich-text field names for the content type.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    from pragma.storage.queries.content import get_field_definitions

    field_definitions = get_field_definitions(connection, content_type_id)
    return _extract_rich_text_field_names(field_definitions)


def _load_block_document_field_names(connection: Any, content_type_id: Any) -> tuple[str, ...]:
    """Load block-document field names for one content type.

    Args:
        connection: Open PostgreSQL connection.
        content_type_id: Content-type identifier.

    Returns:
        tuple[str, ...]: Block-document field names for the content type.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    from pragma.storage.queries.content import get_field_definitions

    field_definitions = get_field_definitions(connection, content_type_id)
    return _extract_block_document_field_names(field_definitions)


def _sanitize_public_body_html(value: str) -> str:
    """Sanitize public rich-text HTML before template safe rendering.

    Args:
        value: Candidate rich-text HTML fragment.

    Returns:
        str: Sanitized HTML fragment that only contains public rich-text tags.

    Raises:
        None.
    """

    return nh3.clean(
        value,
        tags=_PUBLIC_BODY_HTML_TAGS,
        attributes={},
        strip_comments=True,
    )


def _escape_body_text(value: str) -> str:
    """Escape an untrusted body string for safe HTML display.

    Args:
        value: Untrusted body text.

    Returns:
        str: Escaped HTML with newlines preserved as line breaks.

    Raises:
        None.
    """

    return escape(value).replace('\n', '<br>\n')


def _extract_block_document_body_html(payload: dict[str, Any]) -> str | None:
    """Render the first declared block-document body field in public priority order.

    Args:
        payload: Entry payload dictionary with block-document metadata.

    Returns:
        str | None: Rendered block-document HTML when available.

    Raises:
        None.
    """

    block_document_fields = _normalize_rich_text_field_names(
        payload.get(_BLOCK_DOCUMENT_FIELD_METADATA_KEY)
    )
    if not block_document_fields:
        return None

    preferred_keys = tuple(
        key
        for key in ('body', 'content', 'body_html', 'blocks')
        if key in block_document_fields
    )
    fallback_keys = tuple(
        key for key in block_document_fields if key not in preferred_keys
    )
    for key in (*preferred_keys, *fallback_keys):
        value = payload.get(key)
        if not isinstance(value, dict):
            continue
        rendered = render_block_document(
            value,
            media_url_resolver=build_public_media_url,
        )
        if rendered:
            return rendered
    return None


def _extract_body_html(payload: dict[str, Any]) -> str:
    """Resolve rich body HTML while avoiding unsafe raw text rendering.

    Args:
        payload: Entry payload dictionary.

    Returns:
        str: HTML-safe body string sanitized for template safe rendering.

    Raises:
        None.
    """

    block_body_html = _extract_block_document_body_html(payload)
    if block_body_html is not None:
        return block_body_html

    rich_text_fields = set(
        _normalize_rich_text_field_names(payload.get(_RICH_TEXT_FIELD_METADATA_KEY))
    )
    trusted_keys = tuple(
        key for key in ('body_html', 'body', 'content') if key in rich_text_fields
    )
    if trusted_keys:
        trusted_body_html = _extract_text(payload, trusted_keys)
        if trusted_body_html is not None:
            return _sanitize_public_body_html(trusted_body_html)

    fallback = _extract_text(payload, ('body', 'content', 'body_html'))
    if fallback is None:
        return ''
    return _sanitize_public_body_html(_escape_body_text(fallback))


def _strip_html(value: str) -> str:
    """Strip markup tags from an HTML-like fragment.

    Args:
        value: HTML source text.

    Returns:
        str: Plain text representation.

    Raises:
        None.
    """

    stripped = _HTML_TAG_PATTERN.sub(' ', value)
    return _collapse_whitespace(unescape(stripped))


def _build_body_summary(body_html: str, title: str) -> str:
    """Build a fallback summary from body text.

    Args:
        body_html: Body HTML fragment.
        title: Entry title fallback.

    Returns:
        str: Summary text.

    Raises:
        None.
    """

    source = _strip_html(body_html) if body_html else title
    if len(source) <= 180:
        return source
    return f"{source[:179].rstrip()}…"


def _format_published_at(value: Any) -> str:
    """Format publish timestamps for template display.

    Args:
        value: Raw publish timestamp value.

    Returns:
        str: Display timestamp text.

    Raises:
        None.
    """

    if isinstance(value, datetime):
        return value.strftime('%b %d, %Y')
    if isinstance(value, str):
        return _collapse_whitespace(value)
    return ''


def _estimate_reading_time(body_html: str, summary: str, title: str) -> str:
    """Estimate reading-time label from entry text.

    Args:
        body_html: Entry body HTML fragment.
        summary: Entry summary text.
        title: Entry title text.

    Returns:
        str: Reading-time label.

    Raises:
        None.
    """

    source_text = _strip_html(body_html) if body_html else _collapse_whitespace(summary or title)
    word_count = len(source_text.split())
    minutes = max(1, math.ceil(word_count / _WORDS_PER_MINUTE))
    return f'{minutes} min read'


def normalize_pagination(page: int, per_page: int) -> tuple[int, int]:
    """Normalize pagination inputs to supported bounds.

    Args:
        page: Requested one-based page number.
        per_page: Requested page size.

    Returns:
        tuple[int, int]: Normalized page and page size.

    Raises:
        None.
    """

    normalized_page = page if page >= 1 else 1
    normalized_per_page = max(1, min(per_page, 100))
    return normalized_page, normalized_per_page


def _build_query_url(path: str, query_params: dict[str, str]) -> str:
    """Build a URL with encoded query parameters.

    Args:
        path: URL path.
        query_params: Query string key/value pairs.

    Returns:
        str: URL with encoded query string.

    Raises:
        None.
    """

    if not query_params:
        return path
    return f'{path}?{urlencode(query_params)}'


def build_page_url(slug: str) -> str:
    """Return public URL for a page entry.

    Args:
        slug: Entry slug.

    Returns:
        str: Public page URL.

    Raises:
        None.
    """

    return f'/pages/{slug}'


def build_post_url(slug: str) -> str:
    """Return public URL for a post entry.

    Args:
        slug: Entry slug.

    Returns:
        str: Public post URL.

    Raises:
        None.
    """

    return f'/posts/{slug}'


def build_archive_url(
    *,
    page: int | None = None,
    per_page: int | None = None,
    content_type: str | None = None,
) -> str:
    """Return archive URL with optional pagination and filters.

    Args:
        page: Optional page number.
        per_page: Optional page size.
        content_type: Optional content-type filter slug.

    Returns:
        str: Archive URL.

    Raises:
        None.
    """

    query_params: dict[str, str] = {}
    if page is not None:
        query_params['page'] = str(page)
    if per_page is not None:
        query_params['per_page'] = str(per_page)
    if content_type:
        query_params['content_type'] = content_type
    return _build_query_url('/archive', query_params)


def build_search_url(
    *,
    query: str | None = None,
    page: int | None = None,
    per_page: int | None = None,
) -> str:
    """Return search URL with optional query and pagination values.

    Args:
        query: Optional search text.
        page: Optional page number.
        per_page: Optional page size.

    Returns:
        str: Search URL.

    Raises:
        None.
    """

    query_params: dict[str, str] = {}
    if query:
        query_params['q'] = query
    if page is not None:
        query_params['page'] = str(page)
    if per_page is not None:
        query_params['per_page'] = str(per_page)
    return _build_query_url('/search', query_params)


def build_theme_static_url(asset_path: str) -> str:
    """Return route URL for theme static assets.

    Args:
        asset_path: Relative asset path under static root.

    Returns:
        str: Public asset URL.

    Raises:
        None.
    """

    normalized = asset_path.lstrip('/')
    return f'/theme/static/{normalized}'


def build_public_media_url(value: str | None) -> str | None:
    """Convert authenticated media-library URLs to public media routes.

    Args:
        value: Candidate media URL from published content payloads.

    Returns:
        str | None: Public media URL when recognized, original URL otherwise.

    Raises:
        None.
    """

    if value is None:
        return None

    normalized = _collapse_whitespace(value)
    if not normalized:
        return None

    content_match = _MEDIA_API_CONTENT_URL_PATTERN.fullmatch(normalized)
    if content_match is not None:
        return f'/media/{content_match.group("media_id")}/content'

    variant_match = _MEDIA_API_VARIANT_URL_PATTERN.fullmatch(normalized)
    if variant_match is not None:
        return (
            f'/media/{variant_match.group("media_id")}/variants/'
            f'{variant_match.group("variant_name")}'
        )

    return normalized


def build_entry_url(content_type_slug: str, slug: str) -> str:
    """Return public URL for an entry slug and content type.

    Args:
        content_type_slug: Owning content-type slug.
        slug: Entry slug.

    Returns:
        str: Public entry URL.

    Raises:
        None.
    """

    if content_type_slug == 'page':
        return build_page_url(slug)
    if content_type_slug == 'post':
        return build_post_url(slug)
    return build_archive_url(content_type=content_type_slug)


def _absolute_url(settings: Settings, route_path: str) -> str:
    """Return canonical absolute URL for a route path.

    Args:
        settings: Application settings.
        route_path: Relative route path with optional query.

    Returns:
        str: Absolute canonical URL.

    Raises:
        None.
    """

    base = settings.base_url.rstrip('/')
    path = route_path if route_path.startswith('/') else f'/{route_path}'
    return f'{base}{path}'


def build_site_context(settings: Settings, theme_runtime: ThemeRuntime) -> PublicSiteContext:
    """Build site-level context for public templates.

    Args:
        settings: Application settings.
        theme_runtime: Active theme runtime instance.

    Returns:
        PublicSiteContext: Public site context payload.

    Raises:
        None.
    """

    try:
        active_theme = theme_runtime.resolve_active_theme()
        name = active_theme.manifest.name
        description = active_theme.manifest.description or _DEFAULT_SITE_DESCRIPTION
    except ThemeError:
        name = _DEFAULT_SITE_NAME
        description = _DEFAULT_SITE_DESCRIPTION

    fallback_navigation = [
        {'label': 'Home', 'href': '/'},
        {'label': 'Archive', 'href': '/archive'},
        {'label': 'Search', 'href': '/search'},
    ]
    navigation = list(fallback_navigation)

    storage = getattr(theme_runtime, '_navigation_storage', None)
    if storage is not None:
        from psycopg import Error as PsycopgError
        from psycopg_pool import PoolTimeout

        from pragma.errors import StorageError
        from pragma.storage.queries.navigation import (
            PRIMARY_MENU_KEY,
            get_navigation_menu_by_key,
            list_navigation_menu_items,
        )

        try:
            with storage.connection() as connection:
                menu_row = get_navigation_menu_by_key(connection, PRIMARY_MENU_KEY)
                menu_rows = (
                    list_navigation_menu_items(connection, menu_row['id'])
                    if menu_row is not None
                    else []
                )
        except (StorageError, PsycopgError, PoolTimeout):
            logger.warning('Public navigation menu unavailable', exc_info=True)
        else:
            if menu_row is not None:
                navigation = []
                for row in menu_rows:
                    if not row.get('enabled'):
                        continue
                    label = str(row['label'])
                    if str(row['link_type']) == 'custom_url':
                        navigation.append({'label': label, 'href': str(row['custom_url'])})
                        continue
                    if str(row.get('entry_status')) != ContentStatus.PUBLISHED.value:
                        continue
                    content_type_slug = row.get('content_type_slug')
                    entry_slug = row.get('entry_slug')
                    if content_type_slug is None or entry_slug is None:
                        continue
                    navigation.append(
                        {
                            'label': label,
                            'href': build_entry_url(
                                str(content_type_slug),
                                str(entry_slug),
                            ),
                        }
                    )

    return PublicSiteContext(
        name=name,
        description=description,
        base_url=settings.base_url.rstrip('/'),
        design=theme_runtime.design_settings.model_dump(),
        navigation=navigation,
        footer_links=list(navigation),
    )


def build_seo_context(
    *,
    settings: Settings,
    site: PublicSiteContext,
    page_title: str,
    page_description: str,
    route_path: str,
    robots: str,
    og_type: str = 'website',
    og_image: str | None = None,
    entry_seo: Any = None,
    force_noindex: bool = False,
) -> PublicSeoContext:
    """Build SEO context for public template rendering.

    Args:
        settings: Application settings.
        site: Site-level public context.
        page_title: Route-specific title text.
        page_description: Route-specific description text.
        route_path: Route path for canonical URL generation.
        robots: Robots directive text.
        og_type: OpenGraph content type.
        og_image: Optional OpenGraph image URL.
        entry_seo: Optional stored entry SEO/social metadata row or model.
        force_noindex: Whether to force preview/noindex behavior regardless of
            stored metadata.

    Returns:
        PublicSeoContext: SEO metadata context.

    Raises:
        None.
    """

    seo_metadata = None
    if entry_seo is not None:
        from pragma.content.models import ContentEntrySeoMetadata

        if isinstance(entry_seo, ContentEntrySeoMetadata):
            seo_metadata = entry_seo
        elif isinstance(entry_seo, dict):
            seo_metadata = ContentEntrySeoMetadata.from_record(entry_seo)

    metadata_title = seo_metadata.title if seo_metadata is not None else None
    metadata_description = (
        seo_metadata.description if seo_metadata is not None else None
    )
    normalized_title = _collapse_whitespace(metadata_title or page_title)
    normalized_description = _collapse_whitespace(
        metadata_description or page_description or site.description
    )
    full_title = site.name if not normalized_title else f'{normalized_title} · {site.name}'

    metadata_canonical_url = (
        seo_metadata.canonical_url
        if seo_metadata is not None and not force_noindex
        else None
    )
    canonical_source = metadata_canonical_url or route_path
    parsed_canonical = urlsplit(canonical_source)
    canonical_url = (
        canonical_source
        if parsed_canonical.scheme and parsed_canonical.netloc
        else _absolute_url(settings, canonical_source)
    )

    robots_directive = robots
    if seo_metadata is not None and str(seo_metadata.robots.value) == 'noindex':
        robots_directive = 'noindex,follow'
    if force_noindex:
        robots_directive = 'noindex,nofollow'

    metadata_og_title = seo_metadata.og_title if seo_metadata is not None else None
    metadata_og_description = (
        seo_metadata.og_description if seo_metadata is not None else None
    )
    metadata_og_image = seo_metadata.og_image if seo_metadata is not None else None
    normalized_og_title = (
        _collapse_whitespace(metadata_og_title) if metadata_og_title else full_title
    )
    normalized_og_description = _collapse_whitespace(
        metadata_og_description or normalized_description
    )
    normalized_og_image = build_public_media_url(metadata_og_image or og_image)
    if normalized_og_image is not None:
        parsed_og_image = urlsplit(normalized_og_image)
        if not (parsed_og_image.scheme and parsed_og_image.netloc):
            normalized_og_image = _absolute_url(settings, normalized_og_image)

    return PublicSeoContext(
        title=normalized_title,
        description=normalized_description,
        canonical_url=canonical_url,
        robots=robots_directive,
        og_type=og_type,
        og_title=normalized_og_title,
        og_description=normalized_og_description,
        og_url=canonical_url,
        og_image=normalized_og_image,
    )


def build_common_context(site: PublicSiteContext, seo: PublicSeoContext) -> dict[str, Any]:
    """Build common template context shared by all public routes.

    Args:
        site: Site-level public context.
        seo: Route-level SEO metadata context.

    Returns:
        dict[str, Any]: Shared template context dictionary.

    Raises:
        None.
    """

    site_data = asdict(site)
    return {
        'site': site_data,
        'navigation': site_data['navigation'],
        'footer_links': site_data['footer_links'],
        'design_settings': site_data['design'],
        'theme_static': '/theme/static',
        'home_url': '/',
        'archive_url': '/archive',
        'search_url': '/search',
        'seo': asdict(seo),
        'page_title': seo.title,
        'page_description': seo.description,
    }


def get_published_entry(
    storage: DatabasePool,
    content_type_slug: str,
    slug: str,
) -> dict[str, Any] | None:
    """Return one published content entry by content type and slug.

    Args:
        storage: Initialized database pool manager.
        content_type_slug: Content-type slug filter.
        slug: Entry slug filter.

    Returns:
        dict[str, Any] | None: Published entry row with content type slug, or None.

    Raises:
        StorageError: If PostgreSQL access fails.
    """

    normalized_type = _collapse_whitespace(content_type_slug).lower()
    normalized_slug = _collapse_whitespace(slug).lower()

    with storage.connection() as connection:
        content_type_row = get_content_type_by_slug(connection, normalized_type)
        if content_type_row is None:
            return None
        rich_text_fields = _load_rich_text_field_names(connection, content_type_row['id'])
        block_document_fields = _load_block_document_field_names(
            connection,
            content_type_row['id'],
        )
        entry_row = get_entry_by_slug(connection, content_type_row['id'], normalized_slug)

    if entry_row is None:
        return None
    if str(entry_row['status']) != ContentStatus.PUBLISHED.value:
        return None

    merged = dict(entry_row)
    merged['content_type_slug'] = str(content_type_row['slug'])
    merged['rich_text_fields'] = rich_text_fields
    merged['block_document_fields'] = block_document_fields
    return merged


def get_preview_entry(storage: DatabasePool, entry_id: Any) -> dict[str, Any] | None:
    """Return one content entry by signed-preview target identifier.

    Args:
        storage: Initialized database pool manager.
        entry_id: Content-entry identifier from a validated preview token.

    Returns:
        dict[str, Any] | None: Entry row with content type and render metadata.

    Raises:
        StorageError: If PostgreSQL access fails.
    """

    from pragma.storage.queries.content import get_entry_by_id

    with storage.connection() as connection:
        entry_row = get_entry_by_id(connection, entry_id)
        if entry_row is None:
            return None
        rich_text_fields = _load_rich_text_field_names(
            connection,
            entry_row['content_type_id'],
        )
        block_document_fields = _load_block_document_field_names(
            connection,
            entry_row['content_type_id'],
        )

    merged = dict(entry_row)
    merged['rich_text_fields'] = rich_text_fields
    merged['block_document_fields'] = block_document_fields
    return merged


def list_published_entries(
    storage: DatabasePool,
    content_type_slug: str,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], int]:
    """List published entries for one content type with pagination.

    Args:
        storage: Initialized database pool manager.
        content_type_slug: Content-type slug filter.
        page: Requested one-based page number.
        per_page: Requested page size.

    Returns:
        tuple[list[dict[str, Any]], int]: Rows for the current page and total count.

    Raises:
        StorageError: If PostgreSQL access fails.
    """

    normalized_page, normalized_per_page = normalize_pagination(page, per_page)
    normalized_type = _collapse_whitespace(content_type_slug).lower()
    offset = (normalized_page - 1) * normalized_per_page

    with storage.connection() as connection:
        content_type_row = get_content_type_by_slug(connection, normalized_type)
        if content_type_row is None:
            return [], 0

        rich_text_fields = _load_rich_text_field_names(connection, content_type_row['id'])
        block_document_fields = _load_block_document_field_names(
            connection,
            content_type_row['id'],
        )
        total = count_entries(
            connection=connection,
            content_type_id=content_type_row['id'],
            content_type_slug=None,
            status=ContentStatus.PUBLISHED.value,
        )
        rows = list_entries(
            connection=connection,
            limit=normalized_per_page,
            offset=offset,
            order_by='published_at',
            content_type_id=content_type_row['id'],
            content_type_slug=None,
            status=ContentStatus.PUBLISHED.value,
        )

    serialized_rows: list[dict[str, Any]] = []
    for row in rows:
        serialized_row = dict(row)
        serialized_row['rich_text_fields'] = rich_text_fields
        serialized_row['block_document_fields'] = block_document_fields
        serialized_rows.append(serialized_row)
    return serialized_rows, total


def build_public_entry_view(entry_row: dict[str, Any]) -> PublicEntryView:
    """Map a storage-layer entry row into a public template projection.

    Args:
        entry_row: Storage-layer entry row.

    Returns:
        PublicEntryView: Public-facing entry projection.

    Raises:
        None.
    """

    payload = dict(entry_row.get('payload') or {})
    rich_text_fields = _normalize_rich_text_field_names(entry_row.get('rich_text_fields'))
    if rich_text_fields:
        payload[_RICH_TEXT_FIELD_METADATA_KEY] = rich_text_fields
    block_document_fields = _normalize_rich_text_field_names(
        entry_row.get('block_document_fields')
    )
    if block_document_fields:
        payload[_BLOCK_DOCUMENT_FIELD_METADATA_KEY] = block_document_fields

    slug = str(entry_row['slug'])
    content_type_slug = str(entry_row.get('content_type_slug') or '')

    title = _extract_text(payload, ('title', 'name')) or _slug_to_title(slug)
    subtitle = _extract_text(payload, ('subtitle',)) or ''
    body_html = _extract_body_html(payload)
    summary = _extract_text(payload, ('summary', 'excerpt')) or _build_body_summary(
        body_html, title
    )
    author = _extract_text(payload, ('author',)) or _DEFAULT_AUTHOR
    category = _extract_text(payload, ('category',)) or _slug_to_title(
        content_type_slug or _DEFAULT_CATEGORY
    )

    return PublicEntryView(
        content_type_slug=content_type_slug,
        slug=slug,
        url=build_entry_url(content_type_slug, slug),
        title=title,
        subtitle=subtitle,
        summary=summary,
        body_html=body_html,
        author=author,
        category=category,
        published_at=_format_published_at(entry_row.get('published_at')),
        reading_time=_estimate_reading_time(body_html, summary, title),
        featured_image_url=build_public_media_url(_extract_text(payload, ('featured_image_url',))),
        featured_image_alt=_extract_text(payload, ('featured_image_alt',)),
    )


def build_public_entry_card(entry_row: dict[str, Any]) -> dict[str, str | None]:
    """Map a storage entry row directly into the public card contract.

    Args:
        entry_row: Storage-layer entry row.

    Returns:
        dict[str, str | None]: Card payload consumed by public list templates.

    Raises:
        None.
    """

    payload = dict(entry_row.get('payload') or {})
    block_document_fields = _normalize_rich_text_field_names(
        entry_row.get('block_document_fields')
    )
    if block_document_fields:
        payload[_BLOCK_DOCUMENT_FIELD_METADATA_KEY] = block_document_fields
    slug = str(entry_row['slug'])
    content_type_slug = str(entry_row.get('content_type_slug') or '')

    title = _extract_text(payload, ('title', 'name')) or _slug_to_title(slug)
    summary = _extract_text(payload, ('summary', 'excerpt'))
    body_text = ''
    if summary is None:
        block_body_html = _extract_block_document_body_html(payload)
        if block_body_html is not None:
            body_text = _strip_html(block_body_html)
        else:
            body_source = _extract_text(payload, ('body', 'content', 'body_html'))
            body_text = _strip_html(body_source) if body_source else ''
        summary = _build_body_summary(body_text, title) if body_text else title

    reading_source = body_text or summary or title
    word_count = len(_collapse_whitespace(reading_source).split())
    reading_minutes = max(1, math.ceil(word_count / _WORDS_PER_MINUTE))

    return {
        'url': build_entry_url(content_type_slug, slug),
        'title': title,
        'excerpt': summary,
        'category': _extract_text(payload, ('category',))
        or _slug_to_title(content_type_slug or _DEFAULT_CATEGORY),
        'author': _extract_text(payload, ('author',)) or _DEFAULT_AUTHOR,
        'published_at': _format_published_at(entry_row.get('published_at')),
        'reading_time': f'{reading_minutes} min read',
        'image_url': build_public_media_url(_extract_text(payload, ('featured_image_url',))),
        'image_alt': _extract_text(payload, ('featured_image_alt',)),
    }


def to_post_card(entry: PublicEntryView) -> dict[str, str | None]:
    """Convert a public entry view into the default blog-card contract.

    Args:
        entry: Public entry projection.

    Returns:
        dict[str, str | None]: Card payload consumed by the default theme.

    Raises:
        None.
    """

    return {
        'url': entry.url,
        'title': entry.title,
        'excerpt': entry.summary,
        'category': entry.category,
        'author': entry.author,
        'published_at': entry.published_at,
        'reading_time': entry.reading_time,
        'image_url': entry.featured_image_url,
        'image_alt': entry.featured_image_alt,
    }


def build_pagination(
    *,
    page: int,
    per_page: int,
    total: int,
    path: str,
    query_params: dict[str, str] | None = None,
) -> PublicPagination:
    """Build pagination metadata with previous/next links.

    Args:
        page: Requested one-based page number.
        per_page: Requested page size.
        total: Total matching records.
        path: Base route path for generated links.
        query_params: Optional stable query parameters for generated links.

    Returns:
        PublicPagination: Pagination metadata for templates.

    Raises:
        None.
    """

    normalized_page, normalized_per_page = normalize_pagination(page, per_page)
    total_pages = max(1, math.ceil(total / normalized_per_page) if total else 1)
    params = dict(query_params or {})

    def _page_url(page_number: int) -> str:
        values = dict(params)
        values['page'] = str(page_number)
        values['per_page'] = str(normalized_per_page)
        return _build_query_url(path, values)

    has_previous = normalized_page > 1
    has_next = normalized_page < total_pages
    return PublicPagination(
        page=normalized_page,
        per_page=normalized_per_page,
        total=total,
        total_pages=total_pages,
        has_previous=has_previous,
        has_next=has_next,
        prev_url=_page_url(normalized_page - 1) if has_previous else None,
        next_url=_page_url(normalized_page + 1) if has_next else None,
    )


def _build_fallback_html(status_code: int) -> str:
    """Build a visitor-safe HTML fallback for theme render failures.

    Args:
        status_code: HTTP status code to represent.

    Returns:
        str: Safe fallback HTML.

    Raises:
        None.
    """

    if status_code == 404:
        title = 'Not Found'
        heading = 'The requested page could not be found.'
        detail = 'Please return to the homepage or try another link.'
    else:
        title = 'Temporarily unavailable'
        heading = 'This page is temporarily unavailable.'
        detail = 'Please try again in a moment.'

    return (
        '<!doctype html>'
        '<html lang="en">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex,follow">'
        f'<title>{escape(title)}</title>'
        '</head>'
        '<body>'
        f'<h1>{escape(heading)}</h1>'
        f'<p>{escape(detail)}</p>'
        '<p><a href="/">Return home</a></p>'
        '</body>'
        '</html>'
    )


def render_public_template(
    theme_runtime: ThemeRuntime,
    template_name: str,
    context: dict[str, Any],
    *,
    status_code: int,
    error_status_code: int,
) -> HTMLResponse:
    """Render a theme template with visitor-safe fallback behavior.

    Args:
        theme_runtime: Active theme runtime instance.
        template_name: Template name to render.
        context: Template context payload.
        status_code: HTTP status code for successful render.
        error_status_code: HTTP status code for fallback render failures.

    Returns:
        HTMLResponse: Rendered template response or safe fallback response.

    Raises:
        None.
    """

    try:
        rendered = theme_runtime.render_template(template_name, context)
        return HTMLResponse(content=rendered, status_code=status_code)
    except ThemeError:
        logger.exception('Public template render failed', extra={'template': template_name})

    return HTMLResponse(
        content=_build_fallback_html(error_status_code),
        status_code=error_status_code,
    )
