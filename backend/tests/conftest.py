# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Pytest fixtures for Pragma backend integration tests.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from uuid import uuid4

import psycopg
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql

from alembic import command
from pragma.app import create_app
from pragma.config import clear_settings_cache
from tests.helpers import BACKEND_ROOT, build_database_dsn, build_runtime_env, load_example_env


def _apply_runtime_env(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    """Apply runtime environment values to the current test process.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        values: Environment values to apply.

    Returns:
        None.

    Raises:
        None.
    """

    for key, value in values.items():
        monkeypatch.setenv(key, value)
    clear_settings_cache()


def _create_database(
    values: dict[str, str],
    database_name: str,
    *,
    extensions: tuple[str, ...] = ('pg_trgm', 'vector'),
) -> None:
    """Create an isolated PostgreSQL database for a test scope.

    Args:
        values: Environment values containing database connectivity settings.
        database_name: Database name to create.
        extensions: PostgreSQL extensions to install after database creation.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL cannot create the database or provision required extensions.
    """

    admin_dsn = build_database_dsn(values, values['PRAGMA_DATABASE_ADMIN_DATABASE'])
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(
            sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database_name))
        )

    requested_extensions = set(extensions)
    database_dsn = build_database_dsn(values, database_name)
    with psycopg.connect(database_dsn, autocommit=True) as connection:
        if 'pg_trgm' in requested_extensions:
            connection.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
        else:
            connection.execute('DROP EXTENSION IF EXISTS pg_trgm CASCADE')

        if 'vector' in requested_extensions:
            connection.execute('CREATE EXTENSION IF NOT EXISTS vector')
        else:
            connection.execute('DROP EXTENSION IF EXISTS vector CASCADE')


def _drop_database(values: dict[str, str], database_name: str) -> None:
    """Drop an isolated PostgreSQL database for a test scope.

    Args:
        values: Environment values containing database connectivity settings.
        database_name: Database name to drop.

    Returns:
        None.

    Raises:
        psycopg.Error: If PostgreSQL cannot drop the database.
    """

    admin_dsn = build_database_dsn(values, values["PRAGMA_DATABASE_ADMIN_DATABASE"])
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            (database_name,),
        )
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name))
        )


def _run_migrations() -> None:
    """Apply Alembic migrations to the currently configured database.

    Args:
        None.

    Returns:
        None.

    Raises:
        CommandError: If Alembic cannot apply the migration chain.
    """

    clear_settings_cache()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def example_env_values() -> dict[str, str]:
    """Return the parsed backend example environment values.

    Args:
        None.

    Returns:
        dict[str, str]: Parsed environment values.

    Raises:
        ValueError: If the example environment file is malformed.
    """

    return load_example_env()


@pytest.fixture()
def apply_runtime_env(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[dict[str, str]], None]:
    """Return a helper that applies runtime environment values.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        Callable[[dict[str, str]], None]: Environment application helper.

    Raises:
        None.
    """

    def _apply(values: dict[str, str]) -> None:
        _apply_runtime_env(monkeypatch, values)

    return _apply


def _build_isolated_runtime_env(
    example_env_values: dict[str, str], worker_id: str
) -> tuple[str, dict[str, str]]:
    """Build environment values for an isolated test database.

    Args:
        example_env_values: Parsed environment example values.
        worker_id: Pytest-xdist worker identifier.

    Returns:
        tuple[str, dict[str, str]]: Database name and runtime environment values.

    Raises:
        None.
    """

    database_name = f'pragma_test_{worker_id}_{uuid4().hex[:8]}'
    env_values = build_runtime_env(example_env_values, database_name)
    env_values.update({
        key: os.environ.get(key, value)
        for key, value in env_values.items()
        if key != 'PRAGMA_DATABASE_NAME'
    })
    env_values['PRAGMA_DATABASE_NAME'] = database_name
    return database_name, env_values


@pytest.fixture()
def runtime_database(
    monkeypatch: pytest.MonkeyPatch,
    example_env_values: dict[str, str],
    worker_id: str,
) -> Iterator[dict[str, str]]:
    """Create and configure an isolated PostgreSQL database for a test.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        example_env_values: Parsed environment example values.
        worker_id: Pytest-xdist worker identifier.

    Returns:
        Iterator[dict[str, str]]: Environment values bound to the isolated database.

    Raises:
        psycopg.Error: If PostgreSQL database creation or cleanup fails.
    """

    database_name, env_values = _build_isolated_runtime_env(
        example_env_values, worker_id
    )

    _create_database(env_values, database_name)
    _apply_runtime_env(monkeypatch, env_values)
    try:
        yield env_values
    finally:
        clear_settings_cache()
        _drop_database(env_values, database_name)


@pytest.fixture()
def runtime_database_without_pg_trgm(
    monkeypatch: pytest.MonkeyPatch,
    example_env_values: dict[str, str],
    worker_id: str,
) -> Iterator[dict[str, str]]:
    """Create and configure an isolated database without ``pg_trgm``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        example_env_values: Parsed environment example values.
        worker_id: Pytest-xdist worker identifier.

    Returns:
        Iterator[dict[str, str]]: Environment values bound to the isolated database.

    Raises:
        psycopg.Error: If PostgreSQL database creation or cleanup fails.
    """

    database_name, env_values = _build_isolated_runtime_env(
        example_env_values, worker_id
    )

    _create_database(env_values, database_name, extensions=('vector',))
    _apply_runtime_env(monkeypatch, env_values)
    try:
        yield env_values
    finally:
        clear_settings_cache()
        _drop_database(env_values, database_name)


@pytest.fixture()
def runtime_database_without_pgvector(
    monkeypatch: pytest.MonkeyPatch,
    example_env_values: dict[str, str],
    worker_id: str,
) -> Iterator[dict[str, str]]:
    """Create and configure an isolated database without ``pgvector``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        example_env_values: Parsed environment example values.
        worker_id: Pytest-xdist worker identifier.

    Returns:
        Iterator[dict[str, str]]: Environment values bound to the isolated database.

    Raises:
        psycopg.Error: If PostgreSQL database creation or cleanup fails.
    """

    database_name, env_values = _build_isolated_runtime_env(
        example_env_values, worker_id
    )

    _create_database(env_values, database_name, extensions=('pg_trgm',))
    _apply_runtime_env(monkeypatch, env_values)
    try:
        yield env_values
    finally:
        clear_settings_cache()
        _drop_database(env_values, database_name)


@pytest.fixture()
def runtime_database_without_search_extensions(
    monkeypatch: pytest.MonkeyPatch,
    example_env_values: dict[str, str],
    worker_id: str,
) -> Iterator[dict[str, str]]:
    """Create and configure an isolated database without search extensions.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        example_env_values: Parsed environment example values.
        worker_id: Pytest-xdist worker identifier.

    Returns:
        Iterator[dict[str, str]]: Environment values bound to the isolated database.

    Raises:
        psycopg.Error: If PostgreSQL database creation or cleanup fails.
    """

    database_name, env_values = _build_isolated_runtime_env(
        example_env_values, worker_id
    )

    _create_database(env_values, database_name, extensions=())
    _apply_runtime_env(monkeypatch, env_values)
    try:
        yield env_values
    finally:
        clear_settings_cache()
        _drop_database(env_values, database_name)


@pytest.fixture()
def migrated_database_without_pg_trgm(
    runtime_database_without_pg_trgm: dict[str, str],
) -> dict[str, str]:
    """Apply Alembic migrations to a test database without ``pg_trgm``.

    Args:
        runtime_database_without_pg_trgm: Runtime environment values for the isolated test database.

    Returns:
        dict[str, str]: Environment values for the migrated test database.

    Raises:
        CommandError: If Alembic cannot apply the migration chain.
    """

    _run_migrations()
    return runtime_database_without_pg_trgm


@pytest.fixture()
def migrated_database_without_pgvector(
    runtime_database_without_pgvector: dict[str, str],
) -> dict[str, str]:
    """Apply Alembic migrations to a test database without ``pgvector``.

    Args:
        runtime_database_without_pgvector: Runtime environment values for the
            isolated test database.
            isolated test database.

    Returns:
        dict[str, str]: Environment values for the migrated test database.

    Raises:
        CommandError: If Alembic cannot apply the migration chain.
    """

    _run_migrations()
    return runtime_database_without_pgvector


@pytest.fixture()
def migrated_database_without_search_extensions(
    runtime_database_without_search_extensions: dict[str, str],
) -> dict[str, str]:
    """Apply Alembic migrations to a database without search extensions.

        runtime_database_without_search_extensions: Runtime environment values
            for the isolated test database.
        runtime_database_without_search_extensions: Runtime environment values
            for the isolated test database.

    Returns:
        dict[str, str]: Environment values for the migrated test database.

    Raises:
        CommandError: If Alembic cannot apply the migration chain.
    """

    _run_migrations()
    return runtime_database_without_search_extensions


@pytest.fixture()
def migrated_database(runtime_database: dict[str, str]) -> dict[str, str]:
    """Apply Alembic migrations to an isolated test database.

    Args:
        runtime_database: Environment values for the isolated test database.

    Returns:
        dict[str, str]: Environment values for the migrated test database.

    Raises:
        CommandError: If Alembic cannot apply the migration chain.
    """

    _run_migrations()
    return runtime_database


@pytest.fixture()
def client(migrated_database: dict[str, str]) -> Iterator[TestClient]:
    """Return a FastAPI test client bound to a migrated test database.

    Args:
        migrated_database: Environment values for the migrated test database.

    Returns:
        Iterator[TestClient]: Active FastAPI test client.

    Raises:
        StorageError: If application startup cannot connect to PostgreSQL.
    """

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def bootstrap_payload() -> dict[str, str]:
    """Return a reusable bootstrap payload for the first super-admin.

    Args:
        None.

    Returns:
        dict[str, str]: Bootstrap payload.

    Raises:
        None.
    """

    return {
        "email": "admin@example.com",
        "username": "admin",
        "password": "SuperSecurePassword123",
        "full_name": "Admin User",
    }
