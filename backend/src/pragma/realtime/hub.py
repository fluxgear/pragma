# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Realtime websocket fanout hub with bounded per-client queues.

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
from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from pragma.config import Settings
from pragma.realtime.models import (
    RealtimeEventEnvelope,
    build_resync_required_event,
    serialize_envelope,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _HubClient:
    """Runtime websocket client state tracked by the realtime hub.

    Args:
        client_id: Stable hub client identifier.
        user_id: Authenticated user identifier.
        websocket: Accepted websocket transport.
        queue: Bounded outgoing queue for this client.
        sender_task: Task draining queue and sending websocket frames.

    Returns:
        None.

    Raises:
        None.
    """

    client_id: str
    user_id: UUID
    websocket: WebSocket
    queue: asyncio.Queue[RealtimeEventEnvelope]
    sender_task: asyncio.Task[None]


class RealtimeHub:
    """Bounded websocket fanout hub for realtime event envelopes.

    Args:
        settings: Application settings.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._clients: dict[str, _HubClient] = {}
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        """Return the number of active websocket clients.

        Args:
            None.

        Returns:
            int: Active client count.

        Raises:
            None.
        """

        return len(self._clients)

    async def connect(self, websocket: WebSocket, user_id: UUID) -> str:
        """Accept and register a websocket client with a bounded queue.

        Args:
            websocket: Authenticated websocket transport.
            user_id: Authenticated user identifier.

        Returns:
            str: Assigned hub client identifier.

        Raises:
            RuntimeError: If websocket acceptance fails unexpectedly.
        """

        await websocket.accept()
        client_id = uuid4().hex
        queue: asyncio.Queue[RealtimeEventEnvelope] = asyncio.Queue(
            maxsize=self._settings.realtime_queue_size
        )
        sender_task = asyncio.create_task(
            self._sender_loop(client_id, websocket, queue),
            name=f'realtime-sender-{client_id}',
        )
        client = _HubClient(
            client_id=client_id,
            user_id=user_id,
            websocket=websocket,
            queue=queue,
            sender_task=sender_task,
        )
        async with self._lock:
            self._clients[client_id] = client
        return client_id

    async def disconnect(self, client_id: str) -> None:
        """Disconnect and remove a websocket client from the hub.

        Args:
            client_id: Hub client identifier.

        Returns:
            None.

        Raises:
            None.
        """

        client = await self._pop_client(client_id)
        if client is None:
            return

        current_task = asyncio.current_task()
        if client.sender_task is not current_task:
            client.sender_task.cancel()
            await asyncio.gather(client.sender_task, return_exceptions=True)

        if client.websocket.application_state is WebSocketState.CONNECTED:
            try:
                await client.websocket.close(code=1000)
            except RuntimeError:
                logger.debug(
                    'Realtime websocket close skipped for disconnected client',
                    extra={'client_id': client_id},
                )

    async def send_to_client(self, client_id: str, envelope: RealtimeEventEnvelope) -> bool:
        """Queue an envelope for a single websocket client.

        Args:
            client_id: Hub client identifier.
            envelope: Event envelope to queue.

        Returns:
            bool: True when the envelope is queued.

        Raises:
            None.
        """

        async with self._lock:
            client = self._clients.get(client_id)

        if client is None:
            return False

        try:
            client.queue.put_nowait(envelope)
            return True
        except asyncio.QueueFull:
            await self._drop_overflow_client(client_id, envelope.type)
            return False

    async def broadcast(self, envelope: RealtimeEventEnvelope) -> None:
        """Broadcast an envelope to all active websocket clients.

        Args:
            envelope: Event envelope to distribute.

        Returns:
            None.

        Raises:
            None.
        """

        async with self._lock:
            clients = list(self._clients.values())

        overflowed_client_ids: list[str] = []
        for client in clients:
            try:
                client.queue.put_nowait(envelope)
            except asyncio.QueueFull:
                overflowed_client_ids.append(client.client_id)

        for client_id in overflowed_client_ids:
            await self._drop_overflow_client(client_id, envelope.type)

        if overflowed_client_ids and envelope.type != 'realtime.resync_required':
            await self.broadcast(build_resync_required_event(reason='fanout_queue_overflow'))

    async def shutdown(self) -> None:
        """Disconnect all clients and release websocket resources.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        async with self._lock:
            client_ids = list(self._clients.keys())

        for client_id in client_ids:
            await self.disconnect(client_id)

    async def _sender_loop(
        self,
        client_id: str,
        websocket: WebSocket,
        queue: asyncio.Queue[RealtimeEventEnvelope],
    ) -> None:
        """Drain a client queue and write envelopes to websocket frames.

        Args:
            client_id: Hub client identifier.
            websocket: Websocket transport.
            queue: Bounded outgoing queue.

        Returns:
            None.

        Raises:
            None.
        """

        while True:
            envelope = await queue.get()
            try:
                await websocket.send_text(serialize_envelope(envelope))
            except (WebSocketDisconnect, RuntimeError):
                logger.debug(
                    'Realtime websocket sender stopped after disconnect',
                    extra={
                        'client_id': client_id,
                        'event_type': envelope.type,
                    },
                )
                break
            finally:
                queue.task_done()

        await self.disconnect(client_id)

    async def _drop_overflow_client(self, client_id: str, event_type: str) -> None:
        """Drop a client whose outgoing queue exceeded the configured bound.

        Args:
            client_id: Hub client identifier.
            event_type: Event type that overflowed the queue.

        Returns:
            None.

        Raises:
            None.
        """

        logger.warning(
            'Realtime fanout queue overflow; dropping websocket client',
            extra={
                'client_id': client_id,
                'event_type': event_type,
            },
        )
        client = await self._pop_client(client_id)
        if client is None:
            return

        current_task = asyncio.current_task()
        if client.sender_task is not current_task:
            client.sender_task.cancel()
            await asyncio.gather(client.sender_task, return_exceptions=True)

        if client.websocket.application_state is WebSocketState.CONNECTED:
            try:
                await client.websocket.close(code=1013, reason='realtime queue overflow')
            except RuntimeError:
                logger.debug(
                    'Realtime overflow close skipped for disconnected client',
                    extra={'client_id': client_id},
                )

    async def _pop_client(self, client_id: str) -> _HubClient | None:
        """Pop a client entry from the hub registry.

        Args:
            client_id: Hub client identifier.

        Returns:
            _HubClient | None: Removed client state when present.

        Raises:
            None.
        """

        async with self._lock:
            return self._clients.pop(client_id, None)
