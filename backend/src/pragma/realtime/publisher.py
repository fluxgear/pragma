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
from contextlib import suppress
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread, current_thread
from typing import Final

import psycopg
from psycopg import Error as PsycopgError

from pragma.config import Settings
from pragma.realtime.models import RealtimeEventEnvelope, serialize_envelope

logger = logging.getLogger(__name__)

_PUBLISH_CONNECT_TIMEOUT_SECONDS: Final = 1
_PUBLISH_QUEUE_GET_TIMEOUT_SECONDS: Final = 0.25
_PUBLISH_WORKER_JOIN_TIMEOUT_SECONDS: Final = 1.0


@dataclass(frozen=True)
class _RealtimePublishJob:
    """Serialized realtime notification awaiting background publication.

    Args:
        payload: Serialized realtime envelope.
        event_type: Realtime event type for diagnostics.

    Returns:
        None.

    Raises:
        None.
    """

    payload: str
    event_type: str


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
        self._queue: Queue[_RealtimePublishJob | None] = Queue(
            maxsize=settings.realtime_queue_size
        )
        self._stop_event = Event()
        self._worker_lock = Lock()
        self._worker: Thread | None = None

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
        """Queue an event envelope for best-effort PostgreSQL ``pg_notify``.

        Args:
            envelope: Realtime envelope to publish.

        Returns:
            bool: True when notification is accepted by the bounded background queue,
            otherwise False.

        Raises:
            None.
        """

        if not self.enabled or self._stop_event.is_set():
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

        self._ensure_worker()
        try:
            self._queue.put_nowait(
                _RealtimePublishJob(payload=payload, event_type=envelope.type)
            )
        except Full:
            logger.warning(
                'Realtime publish skipped because the bounded queue is full',
                extra={
                    'channel': self._settings.realtime_channel,
                    'event_type': envelope.type,
                    'queue_size': self._settings.realtime_queue_size,
                },
            )
            return False

        return True

    def close(self) -> None:
        """Stop the background publisher worker if it has been started.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        self._stop_event.set()
        with self._worker_lock:
            worker = self._worker

        if worker is None:
            return

        with suppress(Full):
            self._queue.put_nowait(None)

        worker.join(timeout=_PUBLISH_WORKER_JOIN_TIMEOUT_SECONDS)
        if worker.is_alive():
            logger.warning(
                'Realtime publisher worker did not stop before the shutdown timeout',
                extra={'channel': self._settings.realtime_channel},
            )
            return

        with self._worker_lock:
            if self._worker is worker:
                self._worker = None

    def _ensure_worker(self) -> None:
        """Start the publisher worker once, lazily.

        Args:
            None.

        Returns:
            None.

        Raises:
            RuntimeError: If the background thread cannot be started.
        """

        with self._worker_lock:
            if self._worker is not None and self._worker.is_alive():
                return

            self._stop_event.clear()
            self._worker = Thread(
                target=self._run,
                name='pragma-realtime-publisher',
                daemon=True,
            )
            self._worker.start()

    def _run(self) -> None:
        """Publish queued jobs through one reusable PostgreSQL connection.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        connection: psycopg.Connection | None = None
        try:
            while not self._stop_event.is_set():
                try:
                    job = self._queue.get(timeout=_PUBLISH_QUEUE_GET_TIMEOUT_SECONDS)
                except Empty:
                    continue

                try:
                    if job is None:
                        break
                    connection = self._publish_job(job, connection)
                finally:
                    self._queue.task_done()
        finally:
            self._close_connection(connection)
            with self._worker_lock:
                if self._worker is current_thread():
                    self._worker = None

    def _publish_job(
        self,
        job: _RealtimePublishJob,
        connection: psycopg.Connection | None,
    ) -> psycopg.Connection | None:
        """Publish a queued job and keep a healthy connection for reuse.

        Args:
            job: Serialized notification job.
            connection: Existing reusable PostgreSQL connection, when available.

        Returns:
            psycopg.Connection | None: Connection to reuse for later jobs, or ``None``
            after a failed publication.

        Raises:
            None.
        """

        try:
            if connection is None or connection.closed:
                connection = psycopg.connect(
                    self._settings.database_dsn,
                    autocommit=True,
                    connect_timeout=_PUBLISH_CONNECT_TIMEOUT_SECONDS,
                )
            connection.execute(
                'SELECT pg_notify(%s, %s)',
                (self._settings.realtime_channel, job.payload),
            )
        except (PsycopgError, OSError):
            logger.warning(
                'Realtime publish failed',
                extra={
                    'channel': self._settings.realtime_channel,
                    'event_type': job.event_type,
                },
                exc_info=True,
            )
            self._close_connection(connection)
            return None

        return connection

    def _close_connection(self, connection: psycopg.Connection | None) -> None:
        """Close a publisher connection without raising during best-effort cleanup.

        Args:
            connection: PostgreSQL connection to close, when available.

        Returns:
            None.

        Raises:
            None.
        """

        if connection is None or connection.closed:
            return

        try:
            connection.close()
        except (PsycopgError, OSError):
            logger.warning(
                'Realtime publisher connection cleanup failed',
                extra={'channel': self._settings.realtime_channel},
                exc_info=True,
            )
