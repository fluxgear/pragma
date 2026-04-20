# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Alembic environment configuration for the Pragma backend.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from pragma.config import clear_settings_cache, get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def get_url() -> str:
    """Resolve the configured SQLAlchemy database URL for migrations.

    Args:
        None.

    Returns:
        str: SQLAlchemy database URL for Alembic.

    Raises:
        ValidationError: If required configuration is missing or invalid.
    """

    clear_settings_cache()
    return get_settings().sqlalchemy_database_url


def run_migrations_offline() -> None:
    """Run migrations in offline mode.

    Args:
        None.

    Returns:
        None.

    Raises:
        CommandError: If Alembic configuration is invalid.
    """

    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode.

    Args:
        None.

    Returns:
        None.

    Raises:
        SQLAlchemyError: If the migration engine cannot connect.
    """

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
