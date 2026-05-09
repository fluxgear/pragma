# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Theme administration service logic."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID

from psycopg import Error as PsycopgError

from pragma.errors import AuthError, StorageError, ThemeError
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.themes import (
    delete_theme_settings,
    get_theme_settings,
    upsert_theme_settings,
)
from pragma.themes.models import (
    ThemeDesignSettings,
    ThemeManifestResponse,
    ThemeSettingsResponse,
    ThemeSettingsUpdateRequest,
    design_settings_from_mapping,
    merge_design_settings,
)
from pragma.themes.runtime import ThemeRuntime


def _require_user_id(current_user: Mapping[str, object]) -> UUID:
    """Return a validated UUID for the authenticated user context."""

    raw_value = current_user.get('id')
    if isinstance(raw_value, UUID):
        return raw_value
    if isinstance(raw_value, str):
        try:
            return UUID(raw_value)
        except ValueError as exc:
            raise AuthError(
                detail='Authenticated user identifier is invalid',
                code='AUTH_USER_INVALID',
            ) from exc
    raise AuthError(detail='Authenticated user identifier is missing', code='AUTH_USER_INVALID')


def build_theme_settings_response(
    runtime: ThemeRuntime,
    *,
    persisted_active_theme_id: str | None = None,
    design_settings: ThemeDesignSettings | None = None,
) -> ThemeSettingsResponse:
    """Build the admin theme-settings response from runtime state."""

    selected_design = design_settings or runtime.design_settings
    effective_active_theme_id = persisted_active_theme_id or runtime.configured_active_theme_id
    try:
        current_theme_id = runtime.resolve_active_theme().manifest.id
    except ThemeError:
        current_theme_id = None

    themes = [
        ThemeManifestResponse(
            id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            description=manifest.description,
            author=manifest.author,
            active=manifest.id == effective_active_theme_id,
            default=manifest.id == runtime.default_theme_id,
            current=manifest.id == current_theme_id,
            available=True,
        )
        for manifest in runtime.list_themes()
    ]

    return ThemeSettingsResponse(
        active_theme_id=effective_active_theme_id,
        default_theme_id=runtime.default_theme_id,
        current_theme_id=current_theme_id,
        persisted_active_theme_id=persisted_active_theme_id,
        design_settings=selected_design,
        design_warnings=selected_design.warning_messages(),
        themes=themes,
    )


def get_theme_settings_snapshot(
    storage: DatabasePool,
    runtime: ThemeRuntime,
) -> ThemeSettingsResponse:
    """Return discovered themes plus persisted settings with env fallback."""

    try:
        with storage.connection() as connection:
            row = get_theme_settings(connection)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to load theme settings',
            code='THEME_SETTINGS_LOAD_FAILED',
        ) from exc

    if row is None:
        runtime.apply_settings(active_theme_id=None, design_settings=ThemeDesignSettings())
        return build_theme_settings_response(runtime)

    try:
        design_settings = design_settings_from_mapping(row.get('design_settings'))
    except ValueError as exc:
        raise ThemeError(
            detail='Stored theme design settings are invalid',
            code='THEME_SETTINGS_INVALID',
            status_code=HTTPStatus.BAD_REQUEST,
        ) from exc

    active_theme_id = row.get('active_theme_id')
    persisted_active_theme_id = str(active_theme_id) if active_theme_id else None
    runtime.apply_settings(
        active_theme_id=persisted_active_theme_id,
        design_settings=design_settings,
    )
    return build_theme_settings_response(
        runtime,
        persisted_active_theme_id=persisted_active_theme_id,
        design_settings=design_settings,
    )


def update_theme_settings_snapshot(
    storage: DatabasePool,
    runtime: ThemeRuntime,
    payload: ThemeSettingsUpdateRequest,
    current_user: Mapping[str, object],
) -> ThemeSettingsResponse:
    """Persist active theme and design settings, then refresh runtime state."""

    user_id = _require_user_id(current_user)
    requested_active_theme_id = (
        payload.active_theme_id
        if 'active_theme_id' in payload.model_fields_set
        else runtime.persisted_active_theme_id
    )
    if requested_active_theme_id is not None and not runtime.has_theme(requested_active_theme_id):
        raise ThemeError(
            detail='Requested active theme is not installed',
            code='THEME_ACTIVE_NOT_FOUND',
            status_code=HTTPStatus.BAD_REQUEST,
        )

    existing_design = runtime.design_settings
    try:
        with storage.connection() as connection, connection.transaction():
            existing_row = get_theme_settings(connection)
            if existing_row is not None:
                existing_design = design_settings_from_mapping(existing_row.get('design_settings'))
                if 'active_theme_id' not in payload.model_fields_set:
                    existing_active = existing_row.get('active_theme_id')
                    requested_active_theme_id = str(existing_active) if existing_active else None
            next_design = merge_design_settings(existing_design, payload.design_settings)
            row = upsert_theme_settings(
                connection,
                active_theme_id=requested_active_theme_id,
                design_settings=next_design.model_dump(),
                updated_by_user_id=user_id,
                updated_at=datetime.now(UTC),
            )
    except ThemeError:
        raise
    except ValueError as exc:
        raise ThemeError(
            detail='Theme design settings are invalid',
            code='THEME_SETTINGS_INVALID',
            status_code=HTTPStatus.BAD_REQUEST,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to update theme settings',
            code='THEME_SETTINGS_UPDATE_FAILED',
        ) from exc

    persisted_active_theme_id = row.get('active_theme_id')
    persisted_active_theme_id = (
        str(persisted_active_theme_id) if persisted_active_theme_id else None
    )
    design_settings = design_settings_from_mapping(row.get('design_settings'))
    runtime.apply_settings(
        active_theme_id=persisted_active_theme_id,
        design_settings=design_settings,
    )
    return build_theme_settings_response(
        runtime,
        persisted_active_theme_id=persisted_active_theme_id,
        design_settings=design_settings,
    )


def reset_theme_settings_snapshot(
    storage: DatabasePool,
    runtime: ThemeRuntime,
    current_user: Mapping[str, object],
) -> ThemeSettingsResponse:
    """Delete persisted theme settings and restore environment/default behavior."""

    _ = _require_user_id(current_user)
    try:
        with storage.connection() as connection, connection.transaction():
            delete_theme_settings(connection)
    except PsycopgError as exc:
        raise StorageError(
            detail='Unable to reset theme settings',
            code='THEME_SETTINGS_RESET_FAILED',
        ) from exc

    runtime.apply_settings(active_theme_id=None, design_settings=ThemeDesignSettings())
    return build_theme_settings_response(runtime)


def row_to_runtime_settings(row: dict[str, Any] | None) -> tuple[str | None, ThemeDesignSettings]:
    """Convert a storage row into runtime settings with safe defaults."""

    if row is None:
        return None, ThemeDesignSettings()
    active_theme_id = row.get('active_theme_id')
    return (
        str(active_theme_id) if active_theme_id else None,
        design_settings_from_mapping(row.get('design_settings')),
    )
