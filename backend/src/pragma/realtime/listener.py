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
    """Dedicated PostgreSQL listener that bridges NOTIFY events to a callback."""

    def __init__(
        self,
        settings: Settings,
        on_event: Callable[[RealtimeEventEnvelope], Awaitable[None]],
    ) -> None:
        self._settings = settings
        self._on_event = on_event
        self._task: asyncio.Task[None] | None = None
        self._callback_failure_count = 0

    @property
    def task_healthy(self) -> bool:
        """Return whether the listener background task is currently healthy."""

        if not self._settings.realtime_enabled:
            return True
        return not (self._task is None or self._task.done())

    @property
    def callback_failure_count(self) -> int:
        """Return the number of isolated callback failures seen by this listener."""

        return self._callback_failure_count

    async def start(self) -> None:
        """Start the listener background task when realtime is enabled."""

        if not self._settings.realtime_enabled:
            return
        if self._task is not None and not self._task.done():
            return

        self._task = asyncio.create_task(self._run(), name='pragma-realtime-listener')
        self._task.add_done_callback(self._log_task_done)

    async def stop(self) -> None:
        """Stop the listener background task."""

        if self._task is None:
            return

        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    def _log_task_done(self, task: asyncio.Task[None]) -> None:
        """Log unexpected listener task termination."""

        if task.cancelled():
            return
        exception = task.exception()
        if exception is None:
            return
        logger.error(
            'Realtime listener task terminated unexpectedly',
            extra={
                'channel': self._settings.realtime_channel,
                'listener_code': 'REALTIME_LISTENER_TASK_FAILED',
            },
            exc_info=(type(exception), exception, exception.__traceback__),
        )

    async def _dispatch_event(self, envelope: RealtimeEventEnvelope) -> None:
        """Dispatch an event callback without letting failures stop listening."""

        try:
            await self._on_event(envelope)
        except Exception:
            self._callback_failure_count += 1
            logger.warning(
                'Realtime listener callback failed',
                extra={
                    'event_type': envelope.type,
                    'event_id': str(envelope.id),
                    'callback_failure_count': self._callback_failure_count,
                    'listener_code': 'REALTIME_LISTENER_CALLBACK_FAILED',
                },
                exc_info=True,
            )

    async def _run(self) -> None:
        """Maintain a resilient LISTEN loop with bounded reconnect backoff."""

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
                        await self._dispatch_event(
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
                await self._dispatch_event(
                    build_resync_required_event(reason='listener_disconnected')
                )
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(
                    backoff_seconds * 2,
                    self._settings.realtime_reconnect_max_seconds,
                )

    async def _handle_notify(self, notify: Notify) -> None:
        """Parse and dispatch a PostgreSQL notification payload."""

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

        await self._dispatch_event(envelope)
