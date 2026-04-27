# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Realtime event and ticket models for the Pragma backend.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pragma.auth.security import utc_now

EVENT_SCHEMA_VERSION = 1
MAX_NOTIFY_PAYLOAD_BYTES = 7_500

RealtimeEventType = Literal[
    'content.entry.created',
    'content.entry.updated',
    'content.entry.deleted',
    'realtime.resync_required',
]


@dataclass(frozen=True, slots=True)
class _EventContract:
    """Canonical resource/action pairing for a realtime event type.

    Args:
        resource: Stable resource identifier.
        action: Stable action identifier.

    Returns:
        None.

    Raises:
        None.
    """

    resource: str
    action: str


_EVENT_CONTRACTS: dict[RealtimeEventType, _EventContract] = {
    'content.entry.created': _EventContract(resource='content.entry', action='created'),
    'content.entry.updated': _EventContract(resource='content.entry', action='updated'),
    'content.entry.deleted': _EventContract(resource='content.entry', action='deleted'),
    'realtime.resync_required': _EventContract(resource='realtime', action='resync_required'),
}


class RealtimeEventEnvelope(BaseModel):
    """Structured realtime event payload propagated via PostgreSQL NOTIFY.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If any envelope field is invalid.
    """

    model_config = ConfigDict(extra='forbid')

    version: Literal[1] = EVENT_SCHEMA_VERSION
    id: UUID = Field(default_factory=uuid4)
    type: RealtimeEventType
    resource: str = Field(min_length=1, max_length=64)
    action: str = Field(min_length=1, max_length=64)
    resource_id: UUID | None = None
    occurred_at: datetime = Field(default_factory=utc_now)
    actor_id: UUID | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_contract(self) -> RealtimeEventEnvelope:
        """Validate the resource/action contract for the selected event type.

        Args:
            None.

        Returns:
            RealtimeEventEnvelope: Validated envelope instance.

        Raises:
            ValueError: If resource/action do not match the canonical event contract.
        """

        contract = _EVENT_CONTRACTS[self.type]
        if self.resource != contract.resource or self.action != contract.action:
            raise ValueError(
                'Realtime event contract mismatch for '
                f"{self.type}: expected {contract.resource}/{contract.action}"
            )
        return self


class RealtimeTicketResponse(BaseModel):
    """Response payload for issuing websocket subscription tickets.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    ticket: str = Field(min_length=1)
    expires_at: datetime


def serialize_envelope(envelope: RealtimeEventEnvelope) -> str:
    """Serialize and size-check an event envelope for PostgreSQL NOTIFY.

    Args:
        envelope: Envelope payload to serialize.

    Returns:
        str: Compact JSON payload.

    Raises:
        ValueError: If the encoded payload exceeds the PostgreSQL notify budget.
    """

    payload = envelope.model_dump_json(exclude_none=True)
    payload_size = len(payload.encode('utf-8'))
    if payload_size > MAX_NOTIFY_PAYLOAD_BYTES:
        raise ValueError(
            'Realtime payload exceeds PostgreSQL notify limit: '
            f'{payload_size} bytes > {MAX_NOTIFY_PAYLOAD_BYTES} bytes'
        )
    return payload


def parse_envelope(payload: str) -> RealtimeEventEnvelope:
    """Parse a JSON payload into a realtime event envelope.

    Args:
        payload: JSON payload emitted by PostgreSQL NOTIFY.

    Returns:
        RealtimeEventEnvelope: Parsed event envelope.

    Raises:
        ValidationError: If the payload does not satisfy the envelope contract.
        ValueError: If payload cannot be parsed as JSON.
    """

    return RealtimeEventEnvelope.model_validate_json(payload)


def build_content_entry_event(
    *,
    event_type: Literal['content.entry.created', 'content.entry.updated', 'content.entry.deleted'],
    entry_id: UUID,
    content_type_id: UUID,
    content_type_slug: str,
    slug: str,
    status: str,
    actor_id: UUID | None,
) -> RealtimeEventEnvelope:
    """Build a compact content-entry invalidation envelope.

    Args:
        event_type: Stable event type identifier.
        entry_id: Content-entry identifier.
        content_type_id: Content-type identifier.
        content_type_slug: Content-type slug hint.
        slug: Entry slug hint.
        status: Entry status hint.
        actor_id: Authenticated actor identifier, when known.

    Returns:
        RealtimeEventEnvelope: Content-entry event envelope.

    Raises:
        ValueError: If envelope validation fails.
    """

    contract = _EVENT_CONTRACTS[event_type]
    return RealtimeEventEnvelope(
        type=event_type,
        resource=contract.resource,
        action=contract.action,
        resource_id=entry_id,
        actor_id=actor_id,
        data={
            'entry_id': str(entry_id),
            'content_type_id': str(content_type_id),
            'content_type_slug': content_type_slug,
            'slug': slug,
            'status': status,
        },
    )


def build_resync_required_event(*, reason: str) -> RealtimeEventEnvelope:
    """Build a realtime resync envelope used for recovery signaling.

    Args:
        reason: Stable reason hint for the client.

    Returns:
        RealtimeEventEnvelope: Recovery envelope.

    Raises:
        ValueError: If envelope validation fails.
    """

    contract = _EVENT_CONTRACTS['realtime.resync_required']
    return RealtimeEventEnvelope(
        type='realtime.resync_required',
        resource=contract.resource,
        action=contract.action,
        data={'reason': reason},
    )
