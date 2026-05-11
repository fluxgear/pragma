# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Navigation menu application service."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID

from psycopg import Error as PsycopgError

from pragma.content.models import ContentStatus
from pragma.errors import PragmaError, StorageError
from pragma.navigation.models import (
    NavigationContentOptionListResponse,
    NavigationContentOptionResponse,
    NavigationLinkType,
    NavigationMenuItemRequest,
    NavigationMenuItemResponse,
    NavigationMenuReplaceRequest,
    NavigationMenuResponse,
    NavigationWarningResponse,
)
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.content import get_entry_by_id
from pragma.storage.queries.navigation import (
    PRIMARY_MENU_KEY,
    count_navigation_content_options,
    get_navigation_menu_by_key,
    list_navigation_content_options,
    list_navigation_menu_items,
    replace_navigation_menu_items,
    upsert_navigation_menu,
)


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def _require_user_id(current_user: Mapping[str, object]) -> UUID:
    """Return the authenticated user id from dependency context."""

    user_id = current_user.get('id')
    if not isinstance(user_id, UUID):
        raise PragmaError(
            detail='Authenticated user context is invalid',
            code='NAVIGATION_AUTH_CONTEXT_INVALID',
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
    return user_id


def _build_entry_href(content_type_slug: str, slug: str) -> str:
    """Return the public route for a linked content entry."""

    if content_type_slug == 'page':
        return f'/pages/{slug}'
    if content_type_slug == 'post':
        return f'/posts/{slug}'
    return f'/archive?content_type={content_type_slug}'


def _build_item_response(row: dict[str, Any]) -> NavigationMenuItemResponse:
    """Map one storage row to an API item projection."""

    link_type = str(row['link_type'])
    content_type_slug = (
        str(row['content_type_slug']) if row.get('content_type_slug') is not None else None
    )
    entry_slug = str(row['entry_slug']) if row.get('entry_slug') is not None else None
    href = None
    url = None
    if link_type == NavigationLinkType.CUSTOM_URL.value:
        url = str(row['custom_url']) if row.get('custom_url') is not None else None
        href = url
    elif content_type_slug and entry_slug:
        href = _build_entry_href(content_type_slug, entry_slug)

    return NavigationMenuItemResponse(
        id=row['id'],
        parent_item_id=row.get('parent_item_id'),
        position=int(row['position']),
        label=str(row['label']),
        link_type=NavigationLinkType(link_type),
        enabled=bool(row['enabled']),
        content_entry_id=row.get('content_entry_id'),
        url=url,
        href=href,
        content_type_slug=content_type_slug,
        entry_slug=entry_slug,
        entry_status=str(row['entry_status']) if row.get('entry_status') is not None else None,
    )


def _build_warnings(rows: list[dict[str, Any]]) -> list[NavigationWarningResponse]:
    """Build non-blocking warnings for stored menu targets."""

    warnings: list[NavigationWarningResponse] = []
    for row in rows:
        if str(row['link_type']) != NavigationLinkType.CONTENT_ENTRY.value:
            continue
        if str(row.get('entry_status')) == ContentStatus.PUBLISHED.value:
            continue
        warnings.append(
            NavigationWarningResponse(
                code='NAVIGATION_TARGET_NOT_PUBLISHED',
                detail='Internal navigation target is not currently published.',
                item_position=int(row['position']),
                item_label=str(row['label']),
                content_entry_id=row.get('content_entry_id'),
            )
        )
    return warnings


def _build_menu_response(rows: list[dict[str, Any]]) -> NavigationMenuResponse:
    """Build the API response for the primary menu."""

    items_by_id = {row['id']: _build_item_response(row) for row in rows}
    top_level_items: list[NavigationMenuItemResponse] = []

    for row in sorted(rows, key=lambda item: (int(item['position']), str(item['id']))):
        item = items_by_id[row['id']]
        parent_item_id = row.get('parent_item_id')
        if parent_item_id is None or parent_item_id not in items_by_id:
            top_level_items.append(item)
            continue
        items_by_id[parent_item_id].children.append(item)

    def sort_children(item: NavigationMenuItemResponse) -> None:
        item.children.sort(key=lambda child: (child.position, str(child.id)))
        for child in item.children:
            sort_children(child)

    top_level_items.sort(key=lambda item: (item.position, str(item.id)))
    for item in top_level_items:
        sort_children(item)

    return NavigationMenuResponse(
        key=PRIMARY_MENU_KEY,
        items=top_level_items,
        warnings=_build_warnings(rows),
    )


def get_primary_menu_snapshot(storage: DatabasePool) -> NavigationMenuResponse:
    """Return the current primary navigation menu, if configured."""

    try:
        with storage.connection() as connection:
            menu_row = get_navigation_menu_by_key(connection, PRIMARY_MENU_KEY)
            rows = (
                list_navigation_menu_items(connection, menu_row['id'])
                if menu_row is not None
                else []
            )
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load navigation menu',
            code='NAVIGATION_MENU_LOAD_FAILED',
        ) from exc

    return _build_menu_response(rows)


def _entry_option_label(row: Mapping[str, Any]) -> str:
    """Return a readable picker label for a generic content entry row."""

    payload = row.get('payload')
    if isinstance(payload, Mapping):
        for key in ('title', 'name'):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return ' '.join(value.split())
    return str(row['slug'])


def _build_content_option(row: Mapping[str, Any]) -> NavigationContentOptionResponse:
    """Map one entry row to a navigation picker option."""

    content_type_slug = str(row['content_type_slug'])
    slug = str(row['slug'])
    return NavigationContentOptionResponse(
        id=row['id'],
        label=_entry_option_label(row),
        content_type_slug=content_type_slug,
        slug=slug,
        status=str(row['status']),
        href=_build_entry_href(content_type_slug, slug),
    )


def list_navigation_content_picker_options(
    storage: DatabasePool,
    *,
    limit: int,
    offset: int,
) -> NavigationContentOptionListResponse:
    """Return content entries that can be selected as navigation targets."""

    try:
        with storage.connection() as connection:
            rows = list_navigation_content_options(
                connection,
                limit=limit,
                offset=offset,
            )
            total = count_navigation_content_options(connection)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load navigation content options',
            code='NAVIGATION_CONTENT_OPTIONS_LOAD_FAILED',
        ) from exc

    return NavigationContentOptionListResponse(
        items=[_build_content_option(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def _serialize_request_item(
    item: NavigationMenuItemRequest,
    *,
    position: int,
) -> dict[str, Any]:
    """Convert a validated request item into storage values."""

    link_type = str(item.link_type)
    return {
        'position': position,
        'label': item.label,
        'link_type': link_type,
        'content_entry_id': (
            item.content_entry_id
            if link_type == NavigationLinkType.CONTENT_ENTRY.value
            else None
        ),
        'custom_url': item.url if link_type == NavigationLinkType.CUSTOM_URL.value else None,
        'enabled': item.enabled,
        'children': [
            _serialize_request_item(child, position=child_index)
            for child_index, child in enumerate(item.children, start=1)
        ],
    }


def _flatten_serialized_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a pre-order flattened list of serialized menu items."""

    flattened: list[dict[str, Any]] = []
    for item in items:
        flattened.append(item)
        children = item.get('children')
        if isinstance(children, list):
            flattened.extend(_flatten_serialized_items(children))
    return flattened


def replace_primary_menu(
    storage: DatabasePool,
    payload: NavigationMenuReplaceRequest,
    current_user: Mapping[str, object],
) -> NavigationMenuResponse:
    """Replace the primary navigation menu items in request order."""

    user_id = _require_user_id(current_user)
    timestamp = _utc_now()
    serialized_items = [
        _serialize_request_item(item, position=index)
        for index, item in enumerate(payload.items, start=1)
    ]

    try:
        with storage.connection() as connection, connection.transaction():
            for item in _flatten_serialized_items(serialized_items):
                entry_id = item.get('content_entry_id')
                if entry_id is None:
                    continue
                if get_entry_by_id(connection, entry_id) is None:
                    raise PragmaError(
                        detail='Navigation content entry target was not found',
                        code='NAVIGATION_TARGET_NOT_FOUND',
                        status_code=HTTPStatus.BAD_REQUEST,
                    )

            menu_row = upsert_navigation_menu(
                connection,
                key=PRIMARY_MENU_KEY,
                user_id=user_id,
                updated_at=timestamp,
            )
            rows = replace_navigation_menu_items(
                connection,
                menu_id=menu_row['id'],
                items=serialized_items,
                updated_at=timestamp,
            )
    except PragmaError:
        raise
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to save navigation menu',
            code='NAVIGATION_MENU_SAVE_FAILED',
        ) from exc

    return _build_menu_response(rows)
