# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Storage package exports and request-scoped dependencies.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import cast

from fastapi import Request

from pragma.storage.pool import DatabasePool


def get_storage(request: Request) -> DatabasePool:
    """Return the initialized database pool from application state.

    Args:
        request: FastAPI request object.

    Returns:
        DatabasePool: Initialized database pool manager.

    Raises:
        AttributeError: If the application state does not hold a database pool.
    """

    return cast(DatabasePool, request.app.state.storage)
