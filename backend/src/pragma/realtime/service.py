# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Realtime publication service helpers and active publisher registry.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
from threading import Lock
from uuid import UUID

from psycopg import Error as PsycopgError

from pragma.content.models import ContentEntryResponse
from pragma.realtime.models import build_content_entry_event
from pragma.realtime.publisher import RealtimePublisher

logger = logging.getLogger(__name__)

_active_publisher_lock = Lock()
_active_publisher: RealtimePublisher | None = None


def set_active_realtime_publisher(publisher: RealtimePublisher | None) -> None:
    """Set or clear the process-local active realtime publisher.

    Args:
        publisher: Publisher instance, or ``None`` to clear the active publisher.

    Returns:
        None.

    Raises:
        None.
    """

    global _active_publisher
    with _active_publisher_lock:
        _active_publisher = publisher


def get_active_realtime_publisher() -> RealtimePublisher | None:
    """Return the process-local active realtime publisher.

    Args:
        None.

    Returns:
        RealtimePublisher | None: Active publisher when available.

    Raises:
        None.
    """

    with _active_publisher_lock:
        return _active_publisher


def publish_content_entry_event(
    *,
    event_type: str,
    entry: ContentEntryResponse,
    actor_id: UUID | None,
) -> None:
    """Best-effort post-commit publication of content-entry invalidation events.

    Args:
        event_type: Stable content-entry event type.
        entry: Serialized content-entry payload.
        actor_id: Authenticated user identifier, when known.

    Returns:
        None.

    Raises:
        None.
    """

    publisher = get_active_realtime_publisher()
    if publisher is None or not publisher.enabled:
        return

    try:
        envelope = build_content_entry_event(
            event_type=event_type,
            entry_id=entry.id,
            content_type_id=entry.content_type_id,
            content_type_slug=entry.content_type_slug,
            slug=entry.slug,
            status=entry.status.value,
            actor_id=actor_id,
        )
        publisher.publish(envelope)
    except (PsycopgError, RuntimeError, ValueError):
        logger.warning(
            'Realtime publication failure was isolated from content CRUD',
            extra={
                'event_type': event_type,
                'entry_id': str(entry.id),
            },
            exc_info=True,
        )
