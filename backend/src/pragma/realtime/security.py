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
from uuid import UUID, uuid4

import jwt

from pragma.auth.security import decode_token, utc_now
from pragma.config import Settings
from pragma.errors import AuthError

WEBSOCKET_TICKET_TOKEN_TYPE = 'ws'


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

    payload = decode_token(
        settings=settings,
        token=ticket,
        expected_token_type=WEBSOCKET_TICKET_TOKEN_TYPE,
    )
    subject = payload.get('sub')
    if not isinstance(subject, str):
        raise AuthError(detail='Token subject is missing', code='TOKEN_INVALID')

    try:
        return UUID(subject)
    except ValueError as exc:
        raise AuthError(detail='Token subject is invalid', code='TOKEN_INVALID') from exc
