# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Capability-check queries for PostgreSQL extensions.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection

_CAPABILITY_NAMES = ["pg_trgm", "pgvector"]


def get_extension_capabilities(connection: Connection) -> dict[str, dict[str, Any]]:
    """Return availability and installation state for supported extensions.

    Args:
        connection: Open PostgreSQL connection.

    Returns:
        dict[str, dict[str, Any]]: Capability information keyed by extension name.

    Raises:
        psycopg.Error: If PostgreSQL query execution fails.
    """

    rows = connection.execute(
        """
        SELECT name, default_version, installed_version
        FROM pg_available_extensions
        WHERE name = ANY(%s)
        """,
        (_CAPABILITY_NAMES,),
    ).fetchall()

    capabilities = {
        name: {
            "available": False,
            "installed": False,
            "default_version": None,
            "installed_version": None,
        }
        for name in _CAPABILITY_NAMES
    }
    for row in rows:
        capabilities[row["name"]] = {
            "available": True,
            "installed": row["installed_version"] is not None,
            "default_version": row["default_version"],
            "installed_version": row["installed_version"],
        }
    return capabilities
