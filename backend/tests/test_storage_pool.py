# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Database pool lifecycle tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

import pytest

from pragma.errors import StorageError
from pragma.storage import pool as pool_module
from pragma.storage.pool import DatabasePool


class FakeConnectionPool:
    """Minimal connection pool double for DatabasePool.open tests.

    Args:
        kwargs: Captured connection pool configuration.

    Returns:
        None.

    Raises:
        None.
    """

    instances: ClassVar[list[FakeConnectionPool]] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.open_called = False
        self.wait_called = False
        self.close_called = False
        self.instances.append(self)

    def open(self) -> None:
        """Record pool open calls.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        self.open_called = True

    def wait(self) -> None:
        """Record pool readiness waits.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        self.wait_called = True

    def close(self) -> None:
        """Record pool close calls.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        self.close_called = True


def test_open_closes_pool_when_check_connection_raises_storage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure startup ping failures do not leave an opened pool assigned.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.

    Raises:
        None.
    """

    FakeConnectionPool.instances.clear()
    settings = SimpleNamespace(
        database_dsn="postgresql://pragma:secret@localhost:5432/pragma",
        database_pool_min_size=1,
        database_pool_max_size=1,
    )
    pool = DatabasePool(settings)
    ping_error = StorageError(
        detail="Database connectivity check failed",
        code="DATABASE_PING_FAILED",
    )

    def fail_check_connection() -> None:
        raise ping_error

    monkeypatch.setattr(pool_module, "ConnectionPool", FakeConnectionPool)
    monkeypatch.setattr(pool, "check_connection", fail_check_connection)

    with pytest.raises(StorageError) as exc_info:
        pool.open()

    fake_pool = FakeConnectionPool.instances[0]
    assert exc_info.value is ping_error
    assert fake_pool.open_called is True
    assert fake_pool.wait_called is True
    assert fake_pool.close_called is True
    assert pool._pool is None
