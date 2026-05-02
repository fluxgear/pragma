# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""System and readiness routes for the Pragma backend.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from psycopg import Error as PsycopgError

from pragma.errors import StorageError
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.capabilities import get_extension_capabilities
from pragma.storage.queries.install import get_schema_status
from pragma.storage.queries.system import ping_database

router = APIRouter(prefix="/system", tags=["system"])


def _build_health_payload() -> dict[str, str]:
    """Build the liveness payload.

    Args:
        None.

    Returns:
        dict[str, str]: Liveness response body.

    Raises:
        None.
    """

    return {"status": "ok"}


def _build_ready_payload(storage: DatabasePool) -> dict[str, Any]:
    """Build the readiness payload from live database checks.

    Args:
        storage: Initialized database pool manager.

    Returns:
        dict[str, Any]: Readiness payload containing DB and capability information.

    Raises:
        StorageError: If database checks fail.
    """

    try:
        with storage.connection() as connection:
            ping_database(connection)
            schema_status = get_schema_status(connection)
            capabilities = get_extension_capabilities(connection)
    except PsycopgError as exc:
        raise StorageError(
            detail="Readiness checks failed against PostgreSQL",
            code="READINESS_CHECK_FAILED",
        ) from exc

    return {
        "status": "ok",
        "database": "up",
        "schema_ready": schema_status["schema_ready"],
        "capabilities": capabilities,
    }


@router.get("/health")
def health() -> dict[str, str]:
    """Return a simple liveness response.

    Args:
        None.

    Returns:
        dict[str, str]: Liveness response body.

    Raises:
        None.
    """

    return _build_health_payload()


@router.get("/ready")
def ready(
    storage: Annotated[DatabasePool, Depends(get_storage)],
) -> dict[str, Any]:
    """Return a readiness response backed by PostgreSQL checks.

    Args:
        storage: Initialized database pool manager.

    Returns:
        dict[str, Any]: Readiness response body.

    Raises:
        StorageError: If readiness checks fail.
    """

    return _build_ready_payload(storage=storage)
