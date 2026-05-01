# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Realtime integration and resilience tests for M12.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from threading import Event
from time import perf_counter
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect, WebSocketState

from pragma.app import create_app
from pragma.config import get_settings
from pragma.realtime.hub import RealtimeHub
from pragma.realtime.listener import PostgresRealtimeListener
from pragma.realtime.models import (
    MAX_NOTIFY_PAYLOAD_BYTES,
    RealtimeEventEnvelope,
    build_content_entry_event,
    build_resync_required_event,
    parse_envelope,
    serialize_envelope,
)
from pragma.realtime.publisher import RealtimePublisher
from pragma.realtime.security import WEBSOCKET_TICKET_TOKEN_TYPE, create_realtime_ticket


class _ExplodingPublisher:
    """Test-double publisher that raises on every publish call.

    Args:
        None.

    Returns:
        None.

    Raises:
        RuntimeError: Always, during ``publish``.
    """

    enabled = True

    def publish(self, envelope: RealtimeEventEnvelope) -> bool:
        """Raise to simulate an unexpected post-commit publication failure.

        Args:
            envelope: Realtime envelope payload.

        Returns:
            bool: Never returns.

        Raises:
            RuntimeError: Always.
        """

        _ = envelope
        raise RuntimeError('publisher failed')


class _FakeWebSocket:
    """Minimal websocket transport double for hub fanout tests.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self) -> None:
        """Initialize an accepted websocket double with a sent-frame queue.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        self.application_state = WebSocketState.CONNECTED
        self.sent: asyncio.Queue[str] = asyncio.Queue()

    async def accept(self) -> None:
        """Mark the fake websocket as accepted.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        self.application_state = WebSocketState.CONNECTED

    async def send_text(self, payload: str) -> None:
        """Capture a websocket text frame.

        Args:
            payload: Serialized websocket payload.

        Returns:
            None.

        Raises:
            None.
        """

        await self.sent.put(payload)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        """Mark the fake websocket as disconnected.

        Args:
            code: Websocket close code.
            reason: Optional close reason.

        Returns:
            None.

        Raises:
            None.
        """

        _ = code, reason
        self.application_state = WebSocketState.DISCONNECTED


def _bootstrap_admin(client: TestClient, bootstrap_payload: dict[str, str]) -> None:
    """Bootstrap the first administrator account for realtime tests.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap payload.

    Returns:
        None.

    Raises:
        AssertionError: If bootstrap fails unexpectedly.
    """

    response = client.post('/api/v1/install/bootstrap', json=bootstrap_payload)
    assert response.status_code == 201


def _auth_headers(client: TestClient, bootstrap_payload: dict[str, str]) -> dict[str, str]:
    """Return bearer auth headers for the bootstrapped admin.

    Args:
        client: FastAPI test client.
        bootstrap_payload: Bootstrap payload.

    Returns:
        dict[str, str]: Bearer authorization headers.

    Raises:
        AssertionError: If login fails unexpectedly.
    """

    _bootstrap_admin(client, bootstrap_payload)
    response = client.post(
        '/api/v1/auth/login',
        json={
            'identity': bootstrap_payload['email'],
            'password': bootstrap_payload['password'],
        },
    )
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _create_user(
    client: TestClient,
    admin_headers: dict[str, str],
    *,
    email: str,
    username: str,
    password: str,
    role_keys: list[str],
    force_password_change: bool,
    is_active: bool = True,
) -> dict[str, object]:
    """Create a managed user through the administrative API.

    Args:
        client: FastAPI test client.
        admin_headers: Administrator bearer headers.
        email: New user email address.
        username: New user username.
        password: Initial user password.
        role_keys: Assigned role identifiers.
        force_password_change: Forced-password-change flag.
        is_active: Whether the account is active.

    Returns:
        dict[str, object]: Created user payload.

    Raises:
        AssertionError: If the user cannot be created.
    """

    response = client.post(
        '/api/v1/users',
        headers=admin_headers,
        json={
            'email': email,
            'username': username,
            'full_name': 'Realtime User',
            'password': password,
            'is_active': is_active,
            'role_keys': role_keys,
            'force_password_change': force_password_change,
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_content_type(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    """Create a reusable content type for realtime CRUD-isolation tests.

    Args:
        client: FastAPI test client.
        headers: Bearer authentication headers.

    Returns:
        dict[str, object]: Created content-type payload.

    Raises:
        AssertionError: If creation fails.
    """

    response = client.post(
        '/api/v1/content/types',
        headers=headers,
        json={
            'name': 'Realtime Entries',
            'description': 'Realtime test content type',
            'field_definitions': [
                {
                    'name': 'title',
                    'label': 'Title',
                    'kind': 'text',
                    'required': True,
                    'min_length': 3,
                    'max_length': 120,
                },
                {
                    'name': 'body',
                    'label': 'Body',
                    'kind': 'rich_text',
                    'required': True,
                    'min_length': 1,
                },
                {
                    'name': 'views',
                    'label': 'Views',
                    'kind': 'integer',
                    'required': True,
                    'minimum': 0,
                },
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_realtime_envelope_round_trip_and_payload_guard() -> None:
    """Verify realtime envelope serialization, parsing, and payload-size enforcement.

    Args:
        None.

    Returns:
        None.

    Raises:
        None.
    """

    envelope = build_content_entry_event(
        event_type='content.entry.updated',
        entry_id=uuid4(),
        content_type_id=uuid4(),
        content_type_slug='articles',
        slug='hello-world',
        status='published',
        actor_id=uuid4(),
    )

    payload = serialize_envelope(envelope)
    parsed = parse_envelope(payload)
    assert parsed.type == envelope.type
    assert parsed.resource_id == envelope.resource_id
    assert parsed.data['content_type_slug'] == 'articles'

    oversized_envelope = build_resync_required_event(reason='x' * (MAX_NOTIFY_PAYLOAD_BYTES + 64))
    with pytest.raises(ValueError):
        serialize_envelope(oversized_envelope)

    with pytest.raises(ValidationError):
        parse_envelope(
            '{"version":2,"id":"11111111-1111-1111-1111-111111111111",'
            '"type":"content.entry.created","resource":"content.entry",'
            '"action":"created","occurred_at":"2026-04-27T19:00:00Z",'
            '"data":{}}'
        )

    with pytest.raises(ValidationError):
        parse_envelope(
            '{"version":1,"id":"11111111-1111-1111-1111-111111111111",'
            '"type":"content.entry.unknown","resource":"content.entry",'
            '"action":"updated","occurred_at":"2026-04-27T19:00:00Z",'
            '"data":{}}'
        )


def test_realtime_listener_and_publisher_round_trip(migrated_database: dict[str, str]) -> None:
    """Verify PostgreSQL LISTEN/NOTIFY publish and consume round-trip.

    Args:
        migrated_database: Runtime environment values for the migrated test database.

    Returns:
        None.

    Raises:
        None.
    """

    _ = migrated_database
    settings = get_settings()
    publisher = RealtimePublisher(settings)

    async def _exercise() -> RealtimeEventEnvelope:
        queue: asyncio.Queue[RealtimeEventEnvelope] = asyncio.Queue()
        listener = PostgresRealtimeListener(settings, queue.put)
        await listener.start()

        envelope = build_resync_required_event(reason='round_trip')
        received: RealtimeEventEnvelope | None = None
        try:
            for _ in range(20):
                publisher.publish(envelope)
                try:
                    received = await asyncio.wait_for(queue.get(), timeout=0.25)
                    break
                except TimeoutError:
                    await asyncio.sleep(0.1)
        finally:
            await listener.stop()
            publisher.close()

        if received is None:
            raise AssertionError('Realtime listener did not receive a published NOTIFY payload')
        return received

    received_envelope = asyncio.run(_exercise())
    assert received_envelope.type == 'realtime.resync_required'
    assert received_envelope.data['reason'] == 'round_trip'


def test_realtime_publisher_publish_is_bounded_when_connect_is_slow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify slow PostgreSQL connects do not block publish callers unboundedly.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    class _SlowConnectConnection:
        """Connection double returned after the fake slow connect releases.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        def __init__(self) -> None:
            """Initialize the fake connection as open.

            Args:
                None.

            Returns:
                None.

            Raises:
                None.
            """

            self.closed = False

        def execute(self, query: str, params: tuple[str, str]) -> None:
            """Accept a pg_notify statement without touching PostgreSQL.

            Args:
                query: SQL statement text.
                params: SQL parameters.

            Returns:
                None.

            Raises:
                None.
            """

            _ = query, params

        def close(self) -> None:
            """Mark the fake connection closed.

            Args:
                None.

            Returns:
                None.

            Raises:
                None.
            """

            self.closed = True

    connect_started = Event()
    release_connect = Event()
    connect_timeout_seconds: list[int] = []

    def _slow_connect(
        dsn: str,
        *,
        autocommit: bool,
        connect_timeout: int,
    ) -> _SlowConnectConnection:
        """Block in connect until the test releases the fake connection attempt.

        Args:
            dsn: Database DSN.
            autocommit: Requested autocommit mode.
            connect_timeout: Requested connection timeout in seconds.

        Returns:
            _SlowConnectConnection: Fake open connection.

        Raises:
            None.
        """

        _ = dsn, autocommit
        connect_timeout_seconds.append(connect_timeout)
        connect_started.set()
        release_connect.wait(timeout=2)
        return _SlowConnectConnection()

    monkeypatch.setattr('pragma.realtime.publisher.psycopg.connect', _slow_connect)
    settings = get_settings().model_copy(update={'realtime_queue_size': 1})
    publisher = RealtimePublisher(settings)

    try:
        started_at = perf_counter()
        assert publisher.publish(build_resync_required_event(reason='slow_connect')) is True
        assert perf_counter() - started_at < 0.5
        assert connect_started.wait(timeout=2)
        assert connect_timeout_seconds == [1]

        assert publisher.publish(build_resync_required_event(reason='queued')) is True
        started_at = perf_counter()
        assert publisher.publish(build_resync_required_event(reason='queue_full')) is False
        assert perf_counter() - started_at < 0.5
    finally:
        release_connect.set()
        publisher.close()


def test_postgresql_notifications_reach_websocket_transport(
    migrated_database: dict[str, str],
) -> None:
    """Verify PostgreSQL notifications fan out through the websocket transport.

    Args:
        migrated_database: Runtime environment values for the migrated test database.

    Returns:
        None.

    Raises:
        None.
    """

    _ = migrated_database
    settings = get_settings()
    publisher = RealtimePublisher(settings)

    async def _exercise() -> RealtimeEventEnvelope:
        hub = RealtimeHub(settings)
        websocket = _FakeWebSocket()
        client_id = await hub.connect(websocket, uuid4())
        listener = PostgresRealtimeListener(settings, hub.broadcast)
        await listener.start()

        envelope = build_content_entry_event(
            event_type='content.entry.updated',
            entry_id=uuid4(),
            content_type_id=uuid4(),
            content_type_slug='articles',
            slug='transport-check',
            status='published',
            actor_id=uuid4(),
        )
        received: RealtimeEventEnvelope | None = None
        try:
            for _ in range(20):
                publisher.publish(envelope)
                try:
                    payload = await asyncio.wait_for(websocket.sent.get(), timeout=0.25)
                except TimeoutError:
                    await asyncio.sleep(0.1)
                    continue

                candidate = parse_envelope(payload)
                if candidate.id == envelope.id:
                    received = candidate
                    break
        finally:
            await listener.stop()
            await hub.disconnect(client_id)
            await hub.shutdown()
            publisher.close()

        if received is None:
            raise AssertionError('PostgreSQL NOTIFY payload did not reach websocket transport')
        return received

    received_envelope = asyncio.run(_exercise())
    assert received_envelope.type == 'content.entry.updated'
    assert received_envelope.resource == 'content.entry'
    assert received_envelope.action == 'updated'
    assert received_envelope.data['slug'] == 'transport-check'


def test_realtime_ticket_endpoint_requires_content_read_permission(
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify ticket issuance enforces content read permission.

    Args:
        migrated_database: Runtime environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _ = migrated_database
    with TestClient(create_app()) as client:
        admin_headers = _auth_headers(client, bootstrap_payload)
        _create_user(
            client,
            admin_headers,
            email='realtime-no-read@example.com',
            username='realtime-no-read',
            password='RealtimeUserPassword123',
            role_keys=[],
            force_password_change=False,
        )

        user_login = client.post(
            '/api/v1/auth/login',
            json={
                'identity': 'realtime-no-read@example.com',
                'password': 'RealtimeUserPassword123',
            },
        )
        assert user_login.status_code == 200

        response = client.post(
            '/api/v1/realtime/ticket',
            headers={'Authorization': f"Bearer {user_login.json()['access_token']}"},
        )

    assert response.status_code == 403
    assert response.json() == {
        'detail': 'Permission content.entries.read is required',
        'code': 'AUTH_PERMISSION_DENIED',
    }


def test_realtime_websocket_connect_disconnect_and_reconnect(
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify websocket subscription connect/disconnect and reconnect behavior.

    Args:
        migrated_database: Runtime environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _ = migrated_database
    with TestClient(create_app()) as client:
        headers = _auth_headers(client, bootstrap_payload)

        first_ticket_response = client.post('/api/v1/realtime/ticket', headers=headers)
        assert first_ticket_response.status_code == 201
        first_ticket = first_ticket_response.json()['ticket']

        with client.websocket_connect(
            f'/api/v1/realtime/stream?ticket={first_ticket}'
        ) as websocket:
            event = websocket.receive_json()
            assert event['version'] == 1
            assert event['type'] == 'realtime.resync_required'
            assert event['data']['reason'] == 'connected'
            assert client.app.state.realtime_hub.client_count == 1

        assert client.app.state.realtime_hub.client_count == 0

        second_ticket_response = client.post('/api/v1/realtime/ticket', headers=headers)
        assert second_ticket_response.status_code == 201
        second_ticket = second_ticket_response.json()['ticket']

        with client.websocket_connect(
            f'/api/v1/realtime/stream?ticket={second_ticket}'
        ) as websocket:
            event = websocket.receive_json()
            assert event['type'] == 'realtime.resync_required'


def test_realtime_websocket_rejects_invalid_and_expired_ticket(
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify websocket authentication rejects invalid and expired tickets.

    Args:
        migrated_database: Runtime environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _ = migrated_database
    settings = get_settings()

    with TestClient(create_app()) as client:
        headers = _auth_headers(client, bootstrap_payload)
        me_response = client.get('/api/v1/auth/me', headers=headers)
        assert me_response.status_code == 200
        user_id = me_response.json()['id']

        expired_ticket = jwt.encode(
            {
                'sub': user_id,
                'typ': WEBSOCKET_TICKET_TOKEN_TYPE,
                'jti': str(uuid4()),
                'iat': int(datetime(2020, 1, 1, tzinfo=UTC).timestamp()),
                'exp': int(datetime(2020, 1, 1, tzinfo=UTC).timestamp()),
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        with pytest.raises(WebSocketDisconnect) as invalid_exc, client.websocket_connect(
            '/api/v1/realtime/stream?ticket=invalid-ticket'
        ):
            pass

        with pytest.raises(WebSocketDisconnect) as expired_exc, client.websocket_connect(
            f'/api/v1/realtime/stream?ticket={expired_ticket}'
        ):
            pass

    assert invalid_exc.value.code == 1008
    assert expired_exc.value.code == 1008


def test_realtime_websocket_rejects_unauthorized_and_force_password_change_users(
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
) -> None:
    """Verify websocket authentication blocks unauthorized and forced-change users.

    Args:
        migrated_database: Runtime environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.

    Returns:
        None.

    Raises:
        None.
    """

    _ = migrated_database
    settings = get_settings()

    with TestClient(create_app()) as client:
        admin_headers = _auth_headers(client, bootstrap_payload)
        no_permission_user = _create_user(
            client,
            admin_headers,
            email='ws-no-permission@example.com',
            username='ws-no-permission',
            password='RealtimeUserPassword123',
            role_keys=[],
            force_password_change=False,
        )
        forced_change_user = _create_user(
            client,
            admin_headers,
            email='ws-force-change@example.com',
            username='ws-force-change',
            password='RealtimeUserPassword123',
            role_keys=['viewer'],
            force_password_change=True,
        )

        no_permission_ticket, _ = create_realtime_ticket(
            settings,
            UUID(str(no_permission_user['id'])),
        )
        forced_change_ticket, _ = create_realtime_ticket(
            settings,
            UUID(str(forced_change_user['id'])),
        )

        with (
            pytest.raises(WebSocketDisconnect) as no_permission_exc,
            client.websocket_connect(
                f'/api/v1/realtime/stream?ticket={no_permission_ticket}'
            ),
        ):
            pass

        with (
            pytest.raises(WebSocketDisconnect) as forced_change_exc,
            client.websocket_connect(
                f'/api/v1/realtime/stream?ticket={forced_change_ticket}'
            ),
        ):
            pass

    assert no_permission_exc.value.code == 1008
    assert forced_change_exc.value.code == 1008


def test_content_crud_isolated_when_realtime_publication_fails(
    migrated_database: dict[str, str],
    bootstrap_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify realtime publication failures do not break content CRUD flows.

    Args:
        migrated_database: Runtime environment values for the migrated test database.
        bootstrap_payload: Bootstrap request payload.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    _ = migrated_database
    from pragma.realtime import service as realtime_service

    monkeypatch.setattr(
        realtime_service,
        'get_active_realtime_publisher',
        lambda: _ExplodingPublisher(),
    )

    with TestClient(create_app()) as client:
        headers = _auth_headers(client, bootstrap_payload)
        content_type = _create_content_type(client, headers)

        create_response = client.post(
            '/api/v1/content/entries',
            headers=headers,
            json={
                'content_type_id': content_type['id'],
                'status': 'published',
                'payload': {
                    'title': 'Realtime Isolation Create',
                    'body': '<p>Create</p>',
                    'views': 1,
                },
            },
        )
        assert create_response.status_code == 201
        entry_id = create_response.json()['id']

        update_response = client.put(
            f'/api/v1/content/entries/{entry_id}',
            headers=headers,
            json={
                'status': 'published',
                'payload': {
                    'title': 'Realtime Isolation Update',
                    'body': '<p>Update</p>',
                    'views': 2,
                },
            },
        )
        assert update_response.status_code == 200

        delete_response = client.delete(
            f'/api/v1/content/entries/{entry_id}',
            headers=headers,
        )
        assert delete_response.status_code == 204
