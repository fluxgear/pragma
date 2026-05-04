# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Install-state and bootstrap routes.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from pragma.config import Settings, get_settings
from pragma.errors import ApiError
from pragma.install.models import BootstrapRequest, BootstrapResponse, InstallStatusResponse
from pragma.install.service import bootstrap_install, get_install_snapshot
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

_INSTALL_STATUS_ERROR_RESPONSES = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ApiError,
        "description": "Install status storage is unavailable",
    },
}
_INSTALL_BOOTSTRAP_ERROR_RESPONSES = {
    status.HTTP_403_FORBIDDEN: {
        "model": ApiError,
        "description": "Install setup secret is invalid",
    },
    status.HTTP_409_CONFLICT: {
        "model": ApiError,
        "description": "Install bootstrap has already completed",
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ApiError,
        "description": "Request validation failed",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ApiError,
        "description": "Install bootstrap storage or configuration is unavailable",
    },
}

router = APIRouter(prefix="/install", tags=["install"])


@router.get(
    "/status",
    response_model=InstallStatusResponse,
    responses=_INSTALL_STATUS_ERROR_RESPONSES,
)
def install_status(
    storage: Annotated[DatabasePool, Depends(get_storage)],
) -> InstallStatusResponse:
    """Return the current install state and PostgreSQL capability snapshot.

    Args:
        storage: Initialized database pool manager.

    Returns:
        InstallStatusResponse: Install-state payload.

    Raises:
        StorageError: If PostgreSQL access fails.
    """

    return InstallStatusResponse.model_validate(get_install_snapshot(storage))


@router.post(
    "/bootstrap",
    response_model=BootstrapResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_INSTALL_BOOTSTRAP_ERROR_RESPONSES,
)
def bootstrap(
    payload: BootstrapRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    setup_secret: Annotated[
        str | None, Header(alias="X-Pragma-Setup-Secret")
    ] = None,
) -> BootstrapResponse:
    """Create the first super-admin and mark the install complete.

    Args:
        payload: Bootstrap request payload.
        storage: Initialized database pool manager.
        settings: Application settings.
        setup_secret: Operator-controlled bootstrap setup secret.

    Returns:
        BootstrapResponse: Bootstrap completion payload.

    Raises:
        ConfigError: If bootstrap is not allowed.
        StorageError: If PostgreSQL access fails.
    """

    result = bootstrap_install(storage, settings, payload, setup_secret)
    return BootstrapResponse(installed=True, user=result["user"])
