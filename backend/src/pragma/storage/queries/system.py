# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Storage queries for system readiness checks.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from psycopg import Connection


def ping_database(connection: Connection) -> None:
    """Execute a lightweight database connectivity probe.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    connection.execute("SELECT 1").fetchone()
