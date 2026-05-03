# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Authenticated realtime ticket and websocket transport routes.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, status
from psycopg import Error as PsycopgError
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocketDisconnect

from pragma.auth.dependencies import require_permission
from pragma.auth.permissions import PERMISSION_CONTENT_ENTRIES_READ
from pragma.config import Settings, get_settings
from pragma.errors import AuthError, ConfigError, StorageError
from pragma.realtime.dependencies import get_realtime_hub
from pragma.realtime.hub import RealtimeHub
from pragma.realtime.models import RealtimeTicketResponse, build_resync_required_event
from pragma.realtime.security import (
    REALTIME_TICKET_SUBPROTOCOL_PREFIX,
    consume_realtime_ticket,
    create_realtime_ticket,
)
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.users import get_user_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/realtime', tags=['realtime'])


@router.post(
    '/ticket',
    response_model=RealtimeTicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def issue_realtime_ticket(
    current_user: Annotated[
        dict[str, object], Depends(require_permission(PERMISSION_CONTENT_ENTRIES_READ))
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    hub: Annotated[RealtimeHub | None, Depends(get_realtime_hub)],
) -> RealtimeTicketResponse:
    """Issue a short-lived websocket ticket for authenticated admin clients.

    Args:
        current_user: Authenticated user context with content read permission.
        settings: Application settings.
        hub: Active realtime hub dependency.

    Returns:
        RealtimeTicketResponse: Signed websocket ticket and expiry timestamp.

    Raises:
        AuthError: If authenticated user context is invalid.
        ConfigError: If realtime is disabled or unavailable.
    """

    _ = hub
    if not settings.realtime_enabled:
        raise ConfigError(
            detail='Realtime is disabled',
            code='REALTIME_DISABLED',
            status_code=503,
        )

    if bool(current_user.get('force_password_change')):
        raise AuthError(
            detail='Password change is required before accessing this resource',
            code='AUTH_PASSWORD_CHANGE_REQUIRED',
            status_code=403,
        )

    raw_user_id = current_user.get('id')
    if not isinstance(raw_user_id, UUID):
        raise AuthError(detail='Authenticated user context is invalid', code='AUTH_USER_INVALID')

    ticket, expires_at = create_realtime_ticket(settings, raw_user_id)
    return RealtimeTicketResponse(ticket=ticket, expires_at=expires_at)


@router.websocket('/stream')
async def realtime_stream(
    websocket: WebSocket,
    ticket: Annotated[str | None, Query(min_length=1)] = None,
) -> None:
    """Accept an authenticated websocket and bridge realtime envelopes.

    Args:
        websocket: Incoming websocket connection.
        ticket: Optional legacy signed websocket ticket query parameter.

    Returns:
        None.

    Raises:
        None.
    """

    settings = websocket.app.state.settings
    if not settings.realtime_enabled:
        await websocket.close(code=1008, reason='realtime disabled')
        return

    hub = getattr(websocket.app.state, 'realtime_hub', None)
    storage = getattr(websocket.app.state, 'storage', None)
    if hub is None or storage is None:
        await websocket.close(code=1011, reason='realtime unavailable')
        return

    websocket_ticket = _extract_websocket_ticket(websocket, ticket)
    if websocket_ticket is None:
        await websocket.close(code=1008)
        return

    try:
        user = await run_in_threadpool(
            _authenticate_websocket_user,
            websocket_ticket,
            settings,
            storage,
        )
    except (AuthError, StorageError):
        await websocket.close(code=1008)
        return

    client_id = await hub.connect(websocket, user['id'])
    await hub.send_to_client(client_id, build_resync_required_event(reason='connected'))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.debug('Realtime websocket disconnected', extra={'client_id': client_id})
    finally:
        await hub.disconnect(client_id)


def _authenticate_websocket_user(
    ticket: str,
    settings: Settings,
    storage: DatabasePool,
) -> dict[str, Any]:
    """Authenticate a websocket ticket and resolve an authorized user record.

    Args:
        ticket: Signed websocket ticket.
        settings: Application settings.
        storage: Initialized database pool manager.

    Returns:
        dict[str, Any]: Authenticated user record.

    Raises:
        AuthError: If the ticket or user authorization is invalid.
        StorageError: If user lookup fails.
    """

    user_id = consume_realtime_ticket(settings, ticket)

    try:
        with storage.connection() as connection:
            user = get_user_by_id(connection, user_id)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load the authenticated user',
            code='AUTH_USER_LOOKUP_FAILED',
        ) from exc

    if user is None or not bool(user.get('is_active')):
        raise AuthError(detail='Authenticated user is invalid', code='AUTH_USER_INVALID')

    expires_in_force_change = bool(user.get('force_password_change'))
    if expires_in_force_change:
        raise AuthError(
            detail='Password change is required before accessing this resource',
            code='AUTH_PASSWORD_CHANGE_REQUIRED',
            status_code=403,
        )

    if not _has_content_read_permission(user):
        raise AuthError(
            detail=f'Permission {PERMISSION_CONTENT_ENTRIES_READ} is required',
            code='AUTH_PERMISSION_DENIED',
            status_code=403,
        )

    return user


def _extract_websocket_ticket(websocket: WebSocket, query_ticket: str | None) -> str | None:
    """Extract a websocket ticket from subprotocols or legacy query transport.

    Args:
        websocket: Incoming websocket connection.
        query_ticket: Optional legacy query-parameter ticket.

    Returns:
        str | None: Signed websocket ticket when one is present.

    Raises:
        None.
    """

    subprotocol_ticket = _extract_subprotocol_ticket(websocket.scope.get('subprotocols'))
    if subprotocol_ticket is not None:
        return subprotocol_ticket
    return query_ticket


def _extract_subprotocol_ticket(raw_subprotocols: object) -> str | None:
    """Extract a realtime ticket from offered websocket subprotocol values.

    Args:
        raw_subprotocols: ASGI subprotocol list from the websocket scope.

    Returns:
        str | None: Signed websocket ticket when offered by the client.

    Raises:
        None.
    """

    if not isinstance(raw_subprotocols, (list, tuple)):
        return None

    for subprotocol in raw_subprotocols:
        if not isinstance(subprotocol, str):
            continue
        if not subprotocol.startswith(REALTIME_TICKET_SUBPROTOCOL_PREFIX):
            continue

        ticket = subprotocol.removeprefix(REALTIME_TICKET_SUBPROTOCOL_PREFIX)
        if ticket != '':
            return ticket

    return None


def _has_content_read_permission(user: dict[str, Any]) -> bool:
    """Return whether the user can consume realtime content invalidation events.

    Args:
        user: Authenticated user record.

    Returns:
        bool: True when content read permission is granted.

    Raises:
        None.
    """

    if bool(user.get('is_superuser')):
        return True

    permissions = user.get('permissions')
    if not isinstance(permissions, list):
        return False
    return PERMISSION_CONTENT_ENTRIES_READ in permissions
