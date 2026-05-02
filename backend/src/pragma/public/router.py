# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Public HTML routes for Pragma.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from psycopg import Error as PsycopgError
from psycopg_pool import PoolTimeout

from pragma.config import Settings, get_settings
from pragma.errors import SearchError, StorageError, ThemeError
from pragma.public.service import (
    build_archive_url,
    build_common_context,
    build_entry_url,
    build_pagination,
    build_public_entry_card,
    build_public_entry_view,
    build_search_url,
    build_seo_context,
    build_site_context,
    get_published_entry,
    list_published_entries,
    normalize_pagination,
    render_public_template,
)
from pragma.search.models import SearchQueryParams
from pragma.search.service import search_public_entries
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool
from pragma.themes import ThemeRuntime

logger = logging.getLogger(__name__)

_PUBLIC_SEARCH_QUERY_MAX_LENGTH = 200
router = APIRouter(include_in_schema=False)

_RESERVED_PUBLIC_404_PATHS = {'openapi.json'}


def get_theme_runtime(request: Request) -> ThemeRuntime:
    """Return the initialized theme runtime from application state.

    Args:
        request: FastAPI request object.

    Returns:
        ThemeRuntime: Initialized theme runtime.

    Raises:
        AttributeError: If the application state does not hold a theme runtime.
    """

    return cast(ThemeRuntime, request.app.state.theme_runtime)


def _request_path_with_query(request: Request) -> str:
    """Return request path including query string when present.

    Args:
        request: FastAPI request object.

    Returns:
        str: Request path and query string.

    Raises:
        None.
    """

    query = request.url.query
    if not query:
        return request.url.path
    return f'{request.url.path}?{query}'


def _render_not_found(
    request: Request,
    settings: Settings,
    theme_runtime: ThemeRuntime,
    site_context: Any,
) -> HTMLResponse:
    """Render themed public 404 with visitor-safe fallback.

    Args:
        request: FastAPI request object.
        settings: Application settings.
        theme_runtime: Active theme runtime instance.
        site_context: Public site context payload.

    Returns:
        HTMLResponse: HTTP 404 themed response or visitor-safe fallback.

    Raises:
        None.
    """

    seo_context = build_seo_context(
        settings=settings,
        site=site_context,
        page_title='Not Found',
        page_description='The requested page could not be found.',
        route_path=_request_path_with_query(request),
        robots='noindex,follow',
    )
    context = build_common_context(site_context, seo_context)
    return render_public_template(
        theme_runtime=theme_runtime,
        template_name='404.html',
        context=context,
        status_code=status.HTTP_404_NOT_FOUND,
        error_status_code=status.HTTP_404_NOT_FOUND,
    )


def _render_storage_unavailable(
    request: Request,
    settings: Settings,
    theme_runtime: ThemeRuntime,
    site_context: Any,
    exc: StorageError | PsycopgError | PoolTimeout,
) -> HTMLResponse:
    """Render a visitor-safe public outage response for storage failures.

    Args:
        request: FastAPI request object.
        settings: Application settings.
        theme_runtime: Active theme runtime instance.
        site_context: Public site context payload.
        exc: Storage-layer failure being handled for the public route.

    Returns:
        HTMLResponse: Themed 503 response or visitor-safe fallback HTML.

    Raises:
        None.
    """

    logger.warning(
        'Public route storage unavailable',
        extra={'path': str(request.url.path), 'error_type': type(exc).__name__},
        exc_info=True,
    )
    seo_context = build_seo_context(
        settings=settings,
        site=site_context,
        page_title='Temporarily unavailable',
        page_description='This page is temporarily unavailable. Please try again in a moment.',
        route_path=_request_path_with_query(request),
        robots='noindex,follow',
    )
    context = build_common_context(site_context, seo_context)
    return render_public_template(
        theme_runtime=theme_runtime,
        template_name='503.html',
        context=context,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        error_status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )

def _normalize_content_type_slug(content_type: str | None) -> str:
    """Normalize archive content-type filter values.

    Args:
        content_type: Raw content-type query value.

    Returns:
        str: Normalized content-type slug.

    Raises:
        None.
    """

    normalized = (content_type or 'post').strip().lower()
    return normalized or 'post'


def _is_reserved_public_path(path: str) -> bool:
    """Return whether a catch-all path should preserve API/docs behavior.

    Args:
        path: Catch-all path value without leading slash.

    Returns:
        bool: True when the path should preserve default FastAPI 404 behavior.

    Raises:
        None.
    """

    if path in _RESERVED_PUBLIC_404_PATHS:
        return True
    if path in {'api', 'docs', 'redoc'}:
        return True
    return path.startswith('api/') or path.startswith('docs/') or path.startswith('redoc/')


@router.get('/', response_class=HTMLResponse)
def render_home(
    request: Request,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    theme_runtime: Annotated[ThemeRuntime, Depends(get_theme_runtime)],
) -> HTMLResponse:
    """Render the public homepage with latest published posts.

    Args:
        request: FastAPI request object.
        storage: Initialized database pool manager.
        settings: Application settings.
        theme_runtime: Active theme runtime instance.

    Returns:
        HTMLResponse: Rendered homepage response.

    Raises:
        None.
    """

    site_context = build_site_context(settings, theme_runtime)
    seo_context = build_seo_context(
        settings=settings,
        site=site_context,
        page_title='',
        page_description=site_context.description,
        route_path=_request_path_with_query(request),
        robots='index,follow',
    )
    try:
        entry_rows, _ = list_published_entries(storage, 'post', page=1, per_page=3)
    except (StorageError, PsycopgError, PoolTimeout) as exc:
        return _render_storage_unavailable(
            request,
            settings,
            theme_runtime,
            site_context,
            exc,
        )

    featured_posts = [build_public_entry_card(entry_row) for entry_row in entry_rows]

    context = build_common_context(site_context, seo_context)
    context['featured_posts'] = featured_posts
    context['archive_url'] = build_archive_url()
    return render_public_template(
        theme_runtime=theme_runtime,
        template_name='home.html',
        context=context,
        status_code=status.HTTP_200_OK,
        error_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@router.get('/pages/{slug}', response_class=HTMLResponse)
def render_page(
    slug: str,
    request: Request,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    theme_runtime: Annotated[ThemeRuntime, Depends(get_theme_runtime)],
) -> HTMLResponse:
    """Render a published public page.

    Args:
        slug: Page slug.
        request: FastAPI request object.
        storage: Initialized database pool manager.
        settings: Application settings.
        theme_runtime: Active theme runtime instance.

    Returns:
        HTMLResponse: Rendered page response, themed 404, or outage fallback.

    Raises:
        None.
    """

    site_context = build_site_context(settings, theme_runtime)
    try:
        entry_row = get_published_entry(storage, 'page', slug)
    except (StorageError, PsycopgError, PoolTimeout) as exc:
        return _render_storage_unavailable(
            request,
            settings,
            theme_runtime,
            site_context,
            exc,
        )

    if entry_row is None:
        return _render_not_found(request, settings, theme_runtime, site_context)

    page_view = build_public_entry_view(entry_row)
    seo_context = build_seo_context(
        settings=settings,
        site=site_context,
        page_title=page_view.title,
        page_description=page_view.summary or site_context.description,
        route_path=page_view.url,
        robots='index,follow',
        og_type='article',
    )

    context = build_common_context(site_context, seo_context)
    context['page'] = asdict(page_view)
    return render_public_template(
        theme_runtime=theme_runtime,
        template_name='page.html',
        context=context,
        status_code=status.HTTP_200_OK,
        error_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@router.get('/posts/{slug}', response_class=HTMLResponse)
def render_post(
    slug: str,
    request: Request,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    theme_runtime: Annotated[ThemeRuntime, Depends(get_theme_runtime)],
) -> HTMLResponse:
    """Render a published public post with related published posts.

    Args:
        slug: Post slug.
        request: FastAPI request object.
        storage: Initialized database pool manager.
        settings: Application settings.
        theme_runtime: Active theme runtime instance.

    Returns:
        HTMLResponse: Rendered post response, themed 404, or outage fallback.

    Raises:
        None.
    """

    site_context = build_site_context(settings, theme_runtime)
    try:
        entry_row = get_published_entry(storage, 'post', slug)
        if entry_row is None:
            return _render_not_found(request, settings, theme_runtime, site_context)

        post_view = build_public_entry_view(entry_row)
        related_rows, _ = list_published_entries(storage, 'post', page=1, per_page=6)
    except (StorageError, PsycopgError, PoolTimeout) as exc:
        return _render_storage_unavailable(
            request,
            settings,
            theme_runtime,
            site_context,
            exc,
        )

    seo_context = build_seo_context(
        settings=settings,
        site=site_context,
        page_title=post_view.title,
        page_description=post_view.summary or site_context.description,
        route_path=post_view.url,
        robots='index,follow',
        og_type='article',
        og_image=post_view.featured_image_url,
    )

    related_posts: list[dict[str, str | None]] = []
    for related_row in related_rows:
        if str(related_row['slug']) == post_view.slug:
            continue
        related_posts.append(build_public_entry_card(related_row))
        if len(related_posts) == 3:
            break

    context = build_common_context(site_context, seo_context)
    context.update({'post': asdict(post_view), 'related_posts': related_posts})
    return render_public_template(
        theme_runtime=theme_runtime,
        template_name='post.html',
        context=context,
        status_code=status.HTTP_200_OK,
        error_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@router.get('/archive', response_class=HTMLResponse)
def render_archive(
    request: Request,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    theme_runtime: Annotated[ThemeRuntime, Depends(get_theme_runtime)],
    page: Annotated[int, Query()] = 1,
    per_page: Annotated[int, Query()] = 12,
    content_type: Annotated[str | None, Query()] = 'post',
) -> HTMLResponse:
    """Render the public archive list for published entries.

    Args:
        request: FastAPI request object.
        storage: Initialized database pool manager.
        settings: Application settings.
        theme_runtime: Active theme runtime instance.
        page: Requested archive page number.
        per_page: Requested archive page size.
        content_type: Optional content-type slug filter.

    Returns:
        HTMLResponse: Rendered archive response or outage fallback.

    Raises:
        None.
    """

    site_context = build_site_context(settings, theme_runtime)
    normalized_content_type = _normalize_content_type_slug(content_type)
    normalized_page, normalized_per_page = normalize_pagination(page, per_page)

    try:
        entry_rows, total = list_published_entries(
            storage,
            normalized_content_type,
            page=normalized_page,
            per_page=normalized_per_page,
        )
    except (StorageError, PsycopgError, PoolTimeout) as exc:
        return _render_storage_unavailable(
            request,
            settings,
            theme_runtime,
            site_context,
            exc,
        )

    items = [build_public_entry_card(entry_row) for entry_row in entry_rows]

    canonical_path = build_archive_url(
        page=normalized_page if normalized_page != 1 else None,
        per_page=normalized_per_page if normalized_per_page != 12 else None,
        content_type=(
            normalized_content_type if normalized_content_type != 'post' else None
        ),
    )
    query_params = (
        {'content_type': normalized_content_type}
        if normalized_content_type != 'post'
        else None
    )
    pagination = build_pagination(
        page=normalized_page,
        per_page=normalized_per_page,
        total=total,
        path='/archive',
        query_params=query_params,
    )
    seo_context = build_seo_context(
        settings=settings,
        site=site_context,
        page_title='Archive',
        page_description='Browse published entries from the archive.',
        route_path=canonical_path,
        robots='index,follow',
    )

    context = build_common_context(site_context, seo_context)
    context.update(
        {
            'archive': {
                'title': 'Browse the publication archive.',
                'description': 'Published entries are shown below.',
            },
            'items': items,
            'filters': [{'label': normalized_content_type.title()}],
            'pagination': asdict(pagination),
            'archive_url': build_archive_url(
                content_type=(
                    normalized_content_type if normalized_content_type != 'post' else None
                ),
            ),
        }
    )
    return render_public_template(
        theme_runtime=theme_runtime,
        template_name='archive.html',
        context=context,
        status_code=status.HTTP_200_OK,
        error_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@router.get('/search', response_class=HTMLResponse)
def render_search(
    request: Request,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    theme_runtime: Annotated[ThemeRuntime, Depends(get_theme_runtime)],
    q: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query()] = 1,
    per_page: Annotated[int, Query()] = 20,
) -> HTMLResponse:
    """Render the public search view with query/no-query/error states.

    Args:
        request: FastAPI request object.
        storage: Initialized database pool manager.
        settings: Application settings.
        theme_runtime: Active theme runtime instance.
        q: Optional raw search query string.
        page: Requested search page number.
        per_page: Requested search page size.

    Returns:
        HTMLResponse: Rendered search response.

    Raises:
        StorageError: If PostgreSQL access fails.
    """

    site_context = build_site_context(settings, theme_runtime)
    normalized_page, normalized_per_page = normalize_pagination(page, per_page)
    query = (q or '').strip()

    results: list[dict[str, str]] = []
    search_error = ''
    search_enabled = True
    total = 0

    if query and len(query) > _PUBLIC_SEARCH_QUERY_MAX_LENGTH:
        search_enabled = False
        search_error = (
            f'Search queries must be {_PUBLIC_SEARCH_QUERY_MAX_LENGTH} characters or fewer.'
        )
    elif query:
        params = SearchQueryParams(
            query=query,
            limit=normalized_per_page,
            offset=(normalized_page - 1) * normalized_per_page,
        )
        try:
            response = search_public_entries(
                storage, settings, params, allow_provider_embeddings=False
            )
            total = response.total
            results = [
                {
                    'type': item.content_type_slug.title(),
                    'title': item.title,
                    'url': build_entry_url(item.content_type_slug, item.slug),
                    'excerpt': item.excerpt,
                }
                for item in response.items
            ]
        except SearchError:
            search_enabled = False
            search_error = 'Search is temporarily unavailable.'

    pagination = build_pagination(
        page=normalized_page,
        per_page=normalized_per_page,
        total=total,
        path='/search',
        query_params={'q': query} if query else None,
    )
    seo_context = build_seo_context(
        settings=settings,
        site=site_context,
        page_title='Search',
        page_description='Search published pages and posts.',
        route_path=_request_path_with_query(request),
        robots='noindex,follow',
    )

    context = build_common_context(site_context, seo_context)
    context.update(
        {
            'query': query,
            'results': results,
            'search_enabled': search_enabled,
            'search_error': search_error,
            'pagination': asdict(pagination),
            'search_url': build_search_url(),
        }
    )
    return render_public_template(
        theme_runtime=theme_runtime,
        template_name='search.html',
        context=context,
        status_code=status.HTTP_200_OK,
        error_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@router.get('/theme/static/{asset_path:path}')
def render_theme_asset(
    asset_path: str,
    theme_runtime: Annotated[ThemeRuntime, Depends(get_theme_runtime)],
) -> FileResponse:
    """Serve active/default theme static assets from runtime resolution.

    Args:
        asset_path: Relative asset path.
        theme_runtime: Active theme runtime instance.

    Returns:
        FileResponse: Theme static asset response.

    Raises:
        HTTPException: If the asset path is invalid or missing.
    """

    try:
        resolved_asset = theme_runtime.resolve_asset_path(asset_path)
    except ThemeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not Found') from exc

    if not resolved_asset.filesystem_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not Found')

    return FileResponse(
        path=resolved_asset.filesystem_path,
        headers={'Cache-Control': 'public, max-age=300, must-revalidate'},
    )


@router.get('/{path:path}', response_class=HTMLResponse)
def render_public_not_found(
    path: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    theme_runtime: Annotated[ThemeRuntime, Depends(get_theme_runtime)],
) -> HTMLResponse:
    """Render a themed 404 for unmatched public paths.

    Args:
        path: Unmatched request path without leading slash.
        request: FastAPI request object.
        settings: Application settings.
        theme_runtime: Active theme runtime instance.

    Returns:
        HTMLResponse: Rendered themed 404 response.

    Raises:
        HTTPException: To preserve JSON 404 behavior for API/docs/openapi paths.
    """

    if _is_reserved_public_path(path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not Found')

    site_context = build_site_context(settings, theme_runtime)
    return _render_not_found(request, settings, theme_runtime, site_context)
