# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""PostgreSQL NOTIFY publisher for realtime envelopes.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging

import psycopg
from psycopg import Error as PsycopgError

from pragma.config import Settings
from pragma.realtime.models import RealtimeEventEnvelope, serialize_envelope

logger = logging.getLogger(__name__)


class RealtimePublisher:
    """Best-effort PostgreSQL realtime event publisher.

    Args:
        settings: Application settings.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        """Return whether realtime publishing is enabled.

        Args:
            None.

        Returns:
            bool: True when realtime is enabled in settings.

        Raises:
            None.
        """

        return self._settings.realtime_enabled

    def publish(self, envelope: RealtimeEventEnvelope) -> bool:
        """Publish an event envelope using PostgreSQL ``pg_notify``.

        Args:
            envelope: Realtime envelope to publish.

        Returns:
            bool: True when notification is sent successfully, otherwise False.

        Raises:
            None.
        """

        if not self.enabled:
            return False

        try:
            payload = serialize_envelope(envelope)
        except ValueError:
            logger.warning(
                'Realtime publish skipped because payload validation failed',
                extra={'event_type': envelope.type},
                exc_info=True,
            )
            return False

        try:
            with psycopg.connect(self._settings.database_dsn, autocommit=True) as connection:
                connection.execute(
                    'SELECT pg_notify(%s, %s)',
                    (self._settings.realtime_channel, payload),
                )
        except (PsycopgError, OSError):
            logger.warning(
                'Realtime publish failed',
                extra={
                    'channel': self._settings.realtime_channel,
                    'event_type': envelope.type,
                },
                exc_info=True,
            )
            return False

        return True
