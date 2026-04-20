# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Shared test helpers for backend integration tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from urllib.parse import quote

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def load_example_env() -> dict[str, str]:
    """Load key-value pairs from the backend example environment file.

    Args:
        None.

    Returns:
        dict[str, str]: Parsed environment values from ``backend/.env.example``.

    Raises:
        ValueError: If a non-empty line in the example file is malformed.
    """

    values: dict[str, str] = {}
    for raw_line in (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Malformed env example line: {raw_line!r}")
        key, value = line.split("=", 1)
        values[key] = value
    return values


def build_runtime_env(base_env: Mapping[str, str], database_name: str) -> dict[str, str]:
    """Build runtime environment values for a dedicated test database.

    Args:
        base_env: Base environment values loaded from ``.env.example``.
        database_name: Dedicated database name for the current test scope.

    Returns:
        dict[str, str]: Runtime environment values for the current test scope.

    Raises:
        None.
    """

    values = dict(base_env)
    values["PRAGMA_DATABASE_NAME"] = database_name
    values["PRAGMA_BASE_URL"] = "http://testserver"
    values["PRAGMA_JWT_SECRET_KEY"] = "pragma-test-secret-key-1234567890"
    return values


def build_database_dsn(values: Mapping[str, str], database_name: str) -> str:
    """Build a PostgreSQL DSN from environment-style configuration values.

    Args:
        values: Environment-style configuration mapping.
        database_name: Database name to embed in the DSN.

    Returns:
        str: PostgreSQL DSN compatible with psycopg.

    Raises:
        KeyError: If required configuration keys are missing.
    """

    user = quote(values["PRAGMA_DATABASE_USER"], safe="")
    password = quote(values["PRAGMA_DATABASE_PASSWORD"], safe="")
    host = values["PRAGMA_DATABASE_HOST"]
    port = values["PRAGMA_DATABASE_PORT"]
    return f"postgresql://{user}:{password}@{host}:{port}/{database_name}"
