# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Install-state and bootstrap service functions.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg import Error as PsycopgError
from psycopg import IntegrityError

from pragma.auth.security import hash_password, normalize_identity, utc_now
from pragma.config import Settings
from pragma.errors import ConfigError, StorageError
from pragma.install.models import BootstrapRequest
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.capabilities import get_extension_capabilities
from pragma.storage.queries.install import get_install_state, get_schema_status, mark_installed
from pragma.storage.queries.users import count_superusers, create_user


def get_install_snapshot(storage: DatabasePool) -> dict[str, Any]:
    """Return install-state and capability information for the current system.

    Args:
        storage: Initialized database pool manager.

    Returns:
        dict[str, Any]: Install-state payload for API responses.

    Raises:
        StorageError: If PostgreSQL access fails.
    """

    try:
        with storage.connection() as connection:
            schema_status = get_schema_status(connection)
            capabilities = get_extension_capabilities(connection)
            if not schema_status["schema_ready"]:
                return {
                    "schema_ready": False,
                    "is_installed": False,
                    "superuser_exists": False,
                    "capabilities": capabilities,
                }

            install_state = get_install_state(connection)
            return {
                "schema_ready": True,
                "is_installed": bool(install_state["is_installed"]) if install_state else False,
                "superuser_exists": count_superusers(connection) > 0,
                "capabilities": capabilities,
            }
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to determine install status",
            code="INSTALL_STATUS_FAILED",
        ) from exc


def bootstrap_install(
    storage: DatabasePool, settings: Settings, payload: BootstrapRequest
) -> dict[str, Any]:
    """Create the first super-admin and mark the install complete.

    Args:
        storage: Initialized database pool manager.
        settings: Application settings.
        payload: Bootstrap request payload.

    Returns:
        dict[str, Any]: Bootstrap completion payload.

    Raises:
        ConfigError: If migrations are missing or bootstrap already completed.
        StorageError: If PostgreSQL access fails.
    """

    from pragma.auth.permissions import ROLE_ADMINISTRATOR
    from pragma.storage.queries.roles import replace_user_roles
    from pragma.storage.queries.users import get_user_by_id

    created_at = utc_now()

    try:
        with storage.connection() as connection, connection.transaction():
            schema_status = get_schema_status(connection)
            if not schema_status["schema_ready"]:
                raise ConfigError(
                    detail="Database schema is not ready for bootstrap",
                    code="MIGRATION_REQUIRED",
                    status_code=503,
                )

            install_state = get_install_state(connection)
            if (install_state and bool(install_state["is_installed"])) or count_superusers(
                connection
            ) > 0:
                raise ConfigError(
                    detail="Install bootstrap has already completed",
                    code="INSTALL_ALREADY_COMPLETED",
                    status_code=409,
                )

            user = create_user(
                connection=connection,
                user_id=uuid4(),
                email=normalize_identity(payload.email),
                username=normalize_identity(payload.username),
                password_hash=hash_password(payload.password),
                full_name=payload.full_name.strip() if payload.full_name else None,
                is_superuser=True,
                is_active=True,
                force_password_change=False,
                created_at=created_at,
            )
            replace_user_roles(
                connection,
                user_id=user['id'],
                role_keys=[ROLE_ADMINISTRATOR],
                assigned_by_user_id=user['id'],
                assigned_at=created_at,
            )
            mark_installed(connection, user['id'], created_at)
            stored_user = get_user_by_id(connection, user['id'])
    except IntegrityError as exc:
        raise ConfigError(
            detail="Install bootstrap has already completed",
            code="INSTALL_ALREADY_COMPLETED",
            status_code=409,
        ) from exc
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to complete install bootstrap",
            code="INSTALL_BOOTSTRAP_FAILED",
        ) from exc

    if stored_user is None:
        raise StorageError(
            detail='Unable to reload bootstrap superuser',
            code='INSTALL_BOOTSTRAP_USER_RELOAD_FAILED',
        )
    return {"installed": True, "user": stored_user}
