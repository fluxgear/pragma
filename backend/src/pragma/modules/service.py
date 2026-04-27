# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Service-layer operations for module state and dispatch management.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from http import HTTPStatus
from uuid import UUID

from psycopg import Error as PsycopgError

from pragma.auth.security import utc_now
from pragma.errors import AuthError, ModuleError
from pragma.modules.manifest import normalize_module_id
from pragma.modules.models import ModuleListResponse, ModuleStateResponse, ModuleStateUpdateRequest
from pragma.modules.runtime import ModuleRuntime, get_active_module_runtime
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.modules import upsert_module_state

logger = logging.getLogger(__name__)


def _require_user_id(current_user: Mapping[str, object]) -> UUID:
    """Extract and validate a UUID user identifier from auth context.

    Args:
        current_user: Authenticated user context mapping.

    Returns:
        UUID: Parsed authenticated user identifier.

    Raises:
        AuthError: If a valid UUID identifier is unavailable.
    """

    raw_user_id = current_user.get('id')
    if isinstance(raw_user_id, UUID):
        return raw_user_id
    if isinstance(raw_user_id, str):
        try:
            return UUID(raw_user_id)
        except ValueError as exc:
            raise AuthError(
                detail='Authenticated user identifier is invalid',
                code='AUTH_USER_INVALID',
            ) from exc
    raise AuthError(detail='Authenticated user identifier is missing', code='AUTH_USER_INVALID')


def list_module_snapshots(
    storage: DatabasePool,
    runtime: ModuleRuntime,
) -> ModuleListResponse:
    """Return discovered modules with persisted enable/disable state.

    Args:
        storage: Initialized database pool manager.
        runtime: Initialized module runtime instance.

    Returns:
        ModuleListResponse: Ordered module snapshot response payload.

    Raises:
        ModuleError: If runtime state refresh fails.
    """

    runtime.refresh(storage)
    snapshots = [
        ModuleStateResponse.from_snapshot(snapshot)
        for snapshot in runtime.list_snapshots()
    ]
    return ModuleListResponse(items=snapshots, total=len(snapshots))


def update_module_state(
    storage: DatabasePool,
    runtime: ModuleRuntime,
    module_id: str,
    payload: ModuleStateUpdateRequest,
    current_user: Mapping[str, object],
) -> ModuleStateResponse:
    """Persist and apply module enable/disable state changes.

    Args:
        storage: Initialized database pool manager.
        runtime: Initialized module runtime instance.
        module_id: Target module identifier from the API path.
        payload: Desired module state update payload.
        current_user: Authenticated superuser context.

    Returns:
        ModuleStateResponse: Updated module state payload.

    Raises:
        ModuleError: If module state persistence or lookup fails.
        AuthError: If authenticated user context is invalid.
    """

    try:
        normalized_module_id = normalize_module_id(module_id)
    except ValueError as exc:
        raise ModuleError(
            detail=str(exc),
            code='MODULE_ID_INVALID',
            status_code=HTTPStatus.BAD_REQUEST,
        ) from exc

    runtime.refresh(storage)
    if not runtime.has_module(normalized_module_id):
        raise ModuleError(
            detail='Module not found',
            code='MODULE_NOT_FOUND',
            status_code=HTTPStatus.NOT_FOUND,
        )

    timestamp = utc_now()
    user_id = _require_user_id(current_user)
    try:
        with storage.connection() as connection, connection.transaction():
            upsert_module_state(
                connection,
                module_id=normalized_module_id,
                enabled=payload.enabled,
                updated_by_user_id=user_id,
                updated_at=timestamp,
            )
    except PsycopgError as exc:
        raise ModuleError(
            detail='Unable to persist module state',
            code='MODULE_STATE_UPDATE_FAILED',
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        ) from exc

    runtime.refresh(storage)
    snapshot = runtime.get_snapshot(normalized_module_id)
    if snapshot is None:
        raise ModuleError(
            detail='Module not found',
            code='MODULE_NOT_FOUND',
            status_code=HTTPStatus.NOT_FOUND,
        )

    return ModuleStateResponse.from_snapshot(snapshot)


def dispatch_content_entry_event(event: str, payload: Mapping[str, object]) -> None:
    """Dispatch a content-entry module event when runtime is initialized.

    Args:
        event: Stable module hook event identifier.
        payload: Event payload provided to each module hook.

    Returns:
        None.

    Raises:
        None.
    """

    runtime = get_active_module_runtime()
    if runtime is None:
        return

    try:
        runtime.dispatch(event, payload)
    except ModuleError as exc:
        logger.warning(
            'Module dispatch skipped due to invalid event payload',
            extra={
                'event': event,
                'module_code': exc.code,
            },
        )
