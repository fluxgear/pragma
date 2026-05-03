# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""JWT ticket helpers for realtime websocket authentication.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock
from uuid import UUID, uuid4

import jwt

from pragma.auth.security import decode_token, utc_now
from pragma.config import Settings
from pragma.errors import AuthError

WEBSOCKET_TICKET_TOKEN_TYPE = 'ws'
REALTIME_TICKET_SUBPROTOCOL_PREFIX = 'pragma.realtime.ticket.'
_USED_REALTIME_TICKET_IDS: dict[str, int] = {}
_USED_REALTIME_TICKET_LOCK = Lock()


def create_realtime_ticket(
    settings: Settings,
    user_id: UUID,
) -> tuple[str, datetime]:
    """Create a short-lived signed ticket for websocket authentication.

    Args:
        settings: Application settings.
        user_id: Authenticated user identifier.

    Returns:
        tuple[str, datetime]: Encoded ticket and expiry timestamp.

    Raises:
        None.
    """

    issued_at = utc_now()
    expires_at = issued_at + timedelta(seconds=settings.realtime_ticket_ttl_seconds)
    payload = {
        'sub': str(user_id),
        'typ': WEBSOCKET_TICKET_TOKEN_TYPE,
        'jti': str(uuid4()),
        'iat': int(issued_at.timestamp()),
        'exp': int(expires_at.timestamp()),
        'iss': settings.jwt_issuer,
        'aud': settings.jwt_audience,
    }
    ticket = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return ticket, expires_at


def decode_realtime_ticket(settings: Settings, ticket: str) -> UUID:
    """Decode and validate a signed realtime websocket ticket.

    Args:
        settings: Application settings.
        ticket: Signed websocket ticket.

    Returns:
        UUID: Parsed user identifier from the ticket subject claim.

    Raises:
        AuthError: If the ticket is invalid, expired, or has an invalid subject.
    """

    payload = _decode_realtime_ticket_payload(settings, ticket)
    return _parse_realtime_ticket_subject(payload)


def consume_realtime_ticket(settings: Settings, ticket: str) -> UUID:
    """Decode, validate, and mark a realtime websocket ticket as consumed.

    Args:
        settings: Application settings.
        ticket: Signed websocket ticket.

    Returns:
        UUID: Parsed user identifier from the ticket subject claim.

    Raises:
        AuthError: If the ticket is invalid, expired, replayed, or has invalid claims.
    """

    payload = _decode_realtime_ticket_payload(settings, ticket)
    ticket_id = payload.get('jti')
    expires_at = payload.get('exp')
    if not isinstance(ticket_id, str) or ticket_id == '':
        raise AuthError(detail='Token identifier is missing', code='TOKEN_INVALID')
    if not isinstance(expires_at, int):
        raise AuthError(detail='Token expiry is invalid', code='TOKEN_INVALID')

    now = int(utc_now().timestamp())
    with _USED_REALTIME_TICKET_LOCK:
        _purge_consumed_realtime_tickets(now)
        if ticket_id in _USED_REALTIME_TICKET_IDS:
            raise AuthError(
                detail='Realtime ticket has already been used',
                code='REALTIME_TICKET_REPLAYED',
            )
        _USED_REALTIME_TICKET_IDS[ticket_id] = expires_at

    return _parse_realtime_ticket_subject(payload)


def _decode_realtime_ticket_payload(settings: Settings, ticket: str) -> dict[str, str | int]:
    """Decode a realtime ticket into a validated JWT payload.

    Args:
        settings: Application settings.
        ticket: Signed websocket ticket.

    Returns:
        dict[str, str | int]: Decoded ticket payload.

    Raises:
        AuthError: If JWT validation fails.
    """

    return decode_token(
        settings=settings,
        token=ticket,
        expected_token_type=WEBSOCKET_TICKET_TOKEN_TYPE,
    )


def _parse_realtime_ticket_subject(payload: dict[str, str | int]) -> UUID:
    """Parse the realtime ticket subject as a user identifier.

    Args:
        payload: Decoded realtime ticket payload.

    Returns:
        UUID: Parsed user identifier.

    Raises:
        AuthError: If the subject claim is missing or invalid.
    """

    subject = payload.get('sub')
    if not isinstance(subject, str):
        raise AuthError(detail='Token subject is missing', code='TOKEN_INVALID')

    try:
        return UUID(subject)
    except ValueError as exc:
        raise AuthError(detail='Token subject is invalid', code='TOKEN_INVALID') from exc


def _purge_consumed_realtime_tickets(now: int) -> None:
    """Remove expired consumed-ticket identifiers from process memory.

    Args:
        now: Current Unix timestamp in seconds.

    Returns:
        None.

    Raises:
        None.
    """

    expired_ticket_ids = [
        ticket_id
        for ticket_id, expires_at in _USED_REALTIME_TICKET_IDS.items()
        if expires_at <= now
    ]
    for ticket_id in expired_ticket_ids:
        del _USED_REALTIME_TICKET_IDS[ticket_id]
