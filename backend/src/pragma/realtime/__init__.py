# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Realtime runtime factories and exports for Pragma.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from pragma.config import Settings
from pragma.realtime.hub import RealtimeHub
from pragma.realtime.listener import PostgresRealtimeListener
from pragma.realtime.publisher import RealtimePublisher
from pragma.realtime.service import (
    get_active_realtime_publisher,
    publish_content_entry_event,
    set_active_realtime_publisher,
)


def build_realtime_publisher(settings: Settings) -> RealtimePublisher:
    """Build a realtime publisher from application settings.

    Args:
        settings: Application settings.

    Returns:
        RealtimePublisher: Configured realtime publisher.

    Raises:
        None.
    """

    return RealtimePublisher(settings)


def build_realtime_hub(settings: Settings) -> RealtimeHub:
    """Build a realtime websocket hub from application settings.

    Args:
        settings: Application settings.

    Returns:
        RealtimeHub: Configured realtime websocket hub.

    Raises:
        None.
    """

    return RealtimeHub(settings)


def build_realtime_listener(
    settings: Settings,
    hub: RealtimeHub,
) -> PostgresRealtimeListener:
    """Build a PostgreSQL listener that fans out events through the hub.

    Args:
        settings: Application settings.
        hub: Active realtime hub.

    Returns:
        PostgresRealtimeListener: Configured realtime listener.

    Raises:
        None.
    """

    return PostgresRealtimeListener(settings, hub.broadcast)


__all__ = [
    'PostgresRealtimeListener',
    'RealtimeHub',
    'RealtimePublisher',
    'build_realtime_hub',
    'build_realtime_listener',
    'build_realtime_publisher',
    'get_active_realtime_publisher',
    'publish_content_entry_event',
    'set_active_realtime_publisher',
]
