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

from fastapi import APIRouter, Depends, status

from pragma.config import Settings, get_settings
from pragma.install.models import BootstrapRequest, BootstrapResponse, InstallStatusResponse
from pragma.install.service import bootstrap_install, get_install_snapshot
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

router = APIRouter(prefix="/install", tags=["install"])


@router.get("/status", response_model=InstallStatusResponse)
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


@router.post("/bootstrap", response_model=BootstrapResponse, status_code=status.HTTP_201_CREATED)
def bootstrap(
    payload: BootstrapRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BootstrapResponse:
    """Create the first super-admin and mark the install complete.

    Args:
        payload: Bootstrap request payload.
        storage: Initialized database pool manager.
        settings: Application settings.

    Returns:
        BootstrapResponse: Bootstrap completion payload.

    Raises:
        ConfigError: If bootstrap is not allowed.
        StorageError: If PostgreSQL access fails.
    """

    result = bootstrap_install(storage, settings, payload)
    return BootstrapResponse(installed=True, user=result["user"])
