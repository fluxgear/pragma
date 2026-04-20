# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Authentication service functions for login, refresh, and logout.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from psycopg import Error as PsycopgError

from pragma.auth.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
    normalize_identity,
    utc_now,
    verify_password,
)
from pragma.config import Settings
from pragma.errors import AuthError, StorageError
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.auth_sessions import (
    create_refresh_session,
    get_active_refresh_session,
    revoke_refresh_session,
)
from pragma.storage.queries.users import get_user_by_id, get_user_by_identity, update_last_login

logger = logging.getLogger(__name__)


def _build_token_response(
    settings: Settings, user: dict[str, Any], refresh_session_id: UUID
) -> dict[str, Any]:
    """Build an access token, refresh token, and response payload for a user.

    Args:
        settings: Application settings.
        user: Authenticated user record.
        refresh_session_id: Refresh-session identifier to bind to the refresh token.

    Returns:
        dict[str, Any]: Token payload and metadata for HTTP responses.

    Raises:
        None.
    """

    access_token, access_expires_at = create_access_token(settings, user["id"])
    refresh_token, refresh_expires_at = create_refresh_token(
        settings,
        user["id"],
        refresh_session_id,
    )
    return {
        "access_token": access_token,
        "access_expires_at": access_expires_at,
        "expires_in": settings.jwt_access_token_ttl_minutes * 60,
        "refresh_token": refresh_token,
        "refresh_expires_at": refresh_expires_at,
        "refresh_session_id": refresh_session_id,
        "user": user,
    }


def authenticate_user(
    storage: DatabasePool, settings: Settings, identity: str, password: str
) -> dict[str, Any]:
    """Authenticate a user and issue access and refresh tokens.

    Args:
        storage: Initialized database pool manager.
        settings: Application settings.
        identity: Raw email or username credential.
        password: Raw password credential.

    Returns:
        dict[str, Any]: Authentication payload with tokens and serialized user data.

    Raises:
        AuthError: If credentials are invalid or the account is inactive.
        StorageError: If PostgreSQL access fails.
    """

    normalized_identity = normalize_identity(identity)
    issued_at = utc_now()

    try:
        with storage.connection() as connection, connection.transaction():
            user = get_user_by_identity(connection, normalized_identity)
            if user is None or not verify_password(password, str(user["password_hash"])):
                raise AuthError(detail="Invalid credentials", code="INVALID_CREDENTIALS")
            if not bool(user["is_active"]):
                raise AuthError(detail="User account is inactive", code="AUTH_INACTIVE")

            token_payload = _build_token_response(settings, user, uuid4())
            create_refresh_session(
                connection=connection,
                session_id=token_payload["refresh_session_id"],
                user_id=user["id"],
                token_hash=hash_refresh_token(token_payload["refresh_token"]),
                expires_at=token_payload["refresh_expires_at"],
                rotated_from_id=None,
                issued_at=issued_at,
            )
            update_last_login(connection, user["id"], issued_at)
            user["last_login_at"] = issued_at
            token_payload["user"] = user
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to authenticate the supplied credentials",
            code="AUTH_STORAGE_FAILURE",
        ) from exc

    return token_payload


def refresh_user_session(
    storage: DatabasePool, settings: Settings, refresh_token: str
) -> dict[str, Any]:
    """Rotate a refresh token and issue a fresh access token.

    Args:
        storage: Initialized database pool manager.
        settings: Application settings.
        refresh_token: Raw refresh token from the auth cookie.

    Returns:
        dict[str, Any]: Authentication payload with rotated tokens and user data.

    Raises:
        AuthError: If the refresh token is invalid, revoked, or belongs to an inactive user.
        StorageError: If PostgreSQL access fails.
    """

    payload = decode_token(
        settings=settings,
        token=refresh_token,
        expected_token_type=REFRESH_TOKEN_TYPE,
    )
    session_claim = payload.get("jti")
    subject_claim = payload.get("sub")
    if not isinstance(session_claim, str) or not isinstance(subject_claim, str):
        raise AuthError(detail="Refresh token is invalid", code="TOKEN_INVALID")

    try:
        refresh_session_id = UUID(session_claim)
        user_id = UUID(subject_claim)
    except ValueError as exc:
        raise AuthError(detail="Refresh token is invalid", code="TOKEN_INVALID") from exc

    issued_at = utc_now()
    token_hash = hash_refresh_token(refresh_token)

    try:
        with storage.connection() as connection, connection.transaction():
            session = get_active_refresh_session(connection, refresh_session_id, token_hash)
            if session is None:
                raise AuthError(detail="Refresh token is not active", code="TOKEN_REVOKED")

            user = get_user_by_id(connection, user_id)
            if user is None or not bool(user["is_active"]):
                raise AuthError(
                    detail="Authenticated user is invalid",
                    code="AUTH_USER_INVALID",
                )

            revoke_refresh_session(connection, refresh_session_id, issued_at)
            token_payload = _build_token_response(settings, user, uuid4())
            create_refresh_session(
                connection=connection,
                session_id=token_payload["refresh_session_id"],
                user_id=user["id"],
                token_hash=hash_refresh_token(token_payload["refresh_token"]),
                expires_at=token_payload["refresh_expires_at"],
                rotated_from_id=refresh_session_id,
                issued_at=issued_at,
            )
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to refresh the current session",
            code="AUTH_REFRESH_STORAGE_FAILURE",
        ) from exc

    return token_payload


def logout_user(storage: DatabasePool, settings: Settings, refresh_token: str | None) -> None:
    """Revoke the current refresh token when present.

    Args:
        storage: Initialized database pool manager.
        settings: Application settings.
        refresh_token: Raw refresh token from the auth cookie, if present.

    Returns:
        None.

    Raises:
        StorageError: If PostgreSQL access fails while revoking an active token.
    """

    if refresh_token is None:
        return

    try:
        payload = decode_token(
            settings=settings,
            token=refresh_token,
            expected_token_type=REFRESH_TOKEN_TYPE,
        )
    except AuthError as exc:
        logger.info("Ignoring invalid refresh token during logout", exc_info=exc)
        return

    session_claim = payload.get("jti")
    if not isinstance(session_claim, str):
        return

    try:
        refresh_session_id = UUID(session_claim)
    except ValueError as exc:
        logger.info("Ignoring malformed refresh token session id during logout", exc_info=exc)
        return

    try:
        with storage.connection() as connection, connection.transaction():
            revoke_refresh_session(connection, refresh_session_id, utc_now())
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to revoke the current session",
            code="AUTH_LOGOUT_STORAGE_FAILURE",
        ) from exc
