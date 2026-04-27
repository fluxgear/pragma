# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""PostgreSQL LISTEN/NOTIFY bridge for realtime event fanout.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import psycopg
from psycopg import Error as PsycopgError
from psycopg import Notify, sql
from pydantic import ValidationError

from pragma.config import Settings
from pragma.realtime.models import (
    RealtimeEventEnvelope,
    build_resync_required_event,
    parse_envelope,
)

logger = logging.getLogger(__name__)


class PostgresRealtimeListener:
    """Dedicated PostgreSQL listener that bridges NOTIFY events to a callback.

    Args:
        settings: Application settings.
        on_event: Async callback receiving validated envelopes.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        settings: Settings,
        on_event: Callable[[RealtimeEventEnvelope], Awaitable[None]],
    ) -> None:
        self._settings = settings
        self._on_event = on_event
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the listener background task when realtime is enabled.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        if not self._settings.realtime_enabled:
            return
        if self._task is not None and not self._task.done():
            return

        self._task = asyncio.create_task(self._run(), name='pragma-realtime-listener')

    async def stop(self) -> None:
        """Stop the listener background task.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        if self._task is None:
            return

        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def _run(self) -> None:
        """Maintain a resilient LISTEN loop with bounded reconnect backoff.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        backoff_seconds = self._settings.realtime_reconnect_min_seconds
        has_connected = False
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    self._settings.database_dsn,
                    autocommit=True,
                ) as connection:
                    await connection.execute(
                        sql.SQL('LISTEN {}').format(
                            sql.Identifier(self._settings.realtime_channel)
                        )
                    )

                    if has_connected:
                        await self._on_event(
                            build_resync_required_event(reason='listener_reconnected')
                        )
                    has_connected = True
                    backoff_seconds = self._settings.realtime_reconnect_min_seconds

                    async for notify in connection.notifies():
                        await self._handle_notify(notify)
            except asyncio.CancelledError:
                raise
            except (PsycopgError, OSError):
                logger.warning(
                    'Realtime listener disconnected; scheduling reconnect',
                    extra={
                        'channel': self._settings.realtime_channel,
                        'backoff_seconds': backoff_seconds,
                    },
                    exc_info=True,
                )
                await self._on_event(
                    build_resync_required_event(reason='listener_disconnected')
                )
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(
                    backoff_seconds * 2,
                    self._settings.realtime_reconnect_max_seconds,
                )

    async def _handle_notify(self, notify: Notify) -> None:
        """Parse and dispatch a PostgreSQL notification payload.

        Args:
            notify: PostgreSQL notification payload.

        Returns:
            None.

        Raises:
            None.
        """

        try:
            envelope = parse_envelope(notify.payload)
        except (ValidationError, ValueError):
            logger.warning(
                'Realtime listener dropped malformed notification payload',
                extra={
                    'channel': notify.channel,
                    'payload': notify.payload,
                },
                exc_info=True,
            )
            return

        await self._on_event(envelope)
