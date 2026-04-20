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

    capability_to_extension = {
        "pg_trgm": "pg_trgm",
        "pgvector": "vector",
    }
    rows = connection.execute(
        """
        SELECT name, default_version, installed_version
        FROM pg_available_extensions
        WHERE name = ANY(%s)
        """,
        (list(capability_to_extension.values()),),
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
    extension_to_capability = {
        extension_name: capability_name
        for capability_name, extension_name in capability_to_extension.items()
    }
    for row in rows:
        capability_name = extension_to_capability[row["name"]]
        capabilities[capability_name] = {
            "available": True,
            "installed": row["installed_version"] is not None,
            "default_version": row["default_version"],
            "installed_version": row["installed_version"],
        }
    return capabilities
