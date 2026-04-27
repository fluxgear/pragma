# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Request-scoped dependencies for realtime runtime components.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from pragma.config import Settings, get_settings
from pragma.errors import ConfigError
from pragma.realtime.hub import RealtimeHub
from pragma.realtime.publisher import RealtimePublisher


def get_realtime_hub(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RealtimeHub | None:
    """Return the initialized realtime hub from application state.

    Args:
        request: FastAPI request object.
        settings: Application settings.

    Returns:
        RealtimeHub | None: Active realtime hub when configured.

    Raises:
        ConfigError: If realtime is enabled but runtime hub is unavailable.
    """

    hub = getattr(request.app.state, 'realtime_hub', None)
    if hub is None and settings.realtime_enabled:
        raise ConfigError(
            detail='Realtime hub is not initialized',
            code='REALTIME_RUNTIME_UNAVAILABLE',
            status_code=503,
        )
    return cast(RealtimeHub | None, hub)


def get_realtime_publisher(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RealtimePublisher | None:
    """Return the initialized realtime publisher from application state.

    Args:
        request: FastAPI request object.
        settings: Application settings.

    Returns:
        RealtimePublisher | None: Active realtime publisher when configured.

    Raises:
        ConfigError: If realtime is enabled but publisher runtime is unavailable.
    """

    publisher = getattr(request.app.state, 'realtime_publisher', None)
    if publisher is None and settings.realtime_enabled:
        raise ConfigError(
            detail='Realtime publisher is not initialized',
            code='REALTIME_RUNTIME_UNAVAILABLE',
            status_code=503,
        )
    return cast(RealtimePublisher | None, publisher)
