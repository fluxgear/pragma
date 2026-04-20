# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Database pool management for the Pragma backend.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from pragma.config import Settings
from pragma.errors import StorageError


class DatabasePool:
    """Manage the PostgreSQL connection pool lifecycle.

    Args:
        settings: Application settings used to configure the pool.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: ConnectionPool | None = None

    def open(self) -> None:
        """Initialize and verify the connection pool.

        Args:
            None.

        Returns:
            None.

        Raises:
            StorageError: If the pool cannot connect to PostgreSQL.
        """

        if self._pool is not None:
            return

        try:
            self._pool = ConnectionPool(
                conninfo=self._settings.database_dsn,
                min_size=self._settings.database_pool_min_size,
                max_size=self._settings.database_pool_max_size,
                open=False,
                kwargs={"row_factory": dict_row},
            )
            self._pool.open()
            self._pool.wait()
            self.check_connection()
        except (PsycopgError, PoolTimeout) as exc:
            raise StorageError(
                detail="Unable to connect to PostgreSQL with the configured settings",
                code="DATABASE_CONNECTION_FAILED",
            ) from exc

    def close(self) -> None:
        """Close the connection pool if it is open.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        if self._pool is None:
            return

        self._pool.close()
        self._pool = None

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        """Yield a pooled database connection.

        Args:
            None.

        Returns:
            Iterator[Connection]: Context manager yielding a database connection.

        Raises:
            StorageError: If the pool is not initialized.
        """

        if self._pool is None:
            raise StorageError(
                detail="Database pool is not initialized",
                code="DATABASE_POOL_NOT_INITIALIZED",
            )

        with self._pool.connection() as connection:
            yield connection

    def check_connection(self) -> None:
        """Run a lightweight connectivity query against PostgreSQL.

        Args:
            None.

        Returns:
            None.

        Raises:
            StorageError: If the connectivity check fails.
        """

        try:
            with self.connection() as connection:
                connection.execute("SELECT 1").fetchone()
        except (PsycopgError, PoolTimeout) as exc:
            raise StorageError(
                detail="Database connectivity check failed",
                code="DATABASE_PING_FAILED",
            ) from exc
