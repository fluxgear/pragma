# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Authentication dependencies for protected routes.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Error as PsycopgError

from pragma.auth.security import ACCESS_TOKEN_TYPE, decode_token
from pragma.config import Settings, get_settings
from pragma.errors import AuthError, StorageError
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool
from pragma.storage.queries.users import get_user_by_id

_bearer_scheme = HTTPBearer(auto_error=False)


def _parse_token_subject(subject: str | None) -> UUID:
    """Parse a JWT subject claim into a UUID.

    Args:
        subject: Token subject claim.

    Returns:
        UUID: Parsed user identifier.

    Raises:
        AuthError: If the subject claim is missing or invalid.
    """

    if subject is None:
        raise AuthError(detail="Token subject is missing", code="TOKEN_INVALID")

    try:
        return UUID(subject)
    except ValueError as exc:
        raise AuthError(detail="Token subject is invalid", code="TOKEN_INVALID") from exc


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Resolve the authenticated user from the bearer access token.

    Args:
        credentials: Parsed Authorization header credentials.
        storage: Initialized database pool manager.
        settings: Application settings.

    Returns:
        dict[str, Any]: Authenticated user record.

    Raises:
        AuthError: If the bearer token is missing or invalid.
        StorageError: If the user lookup fails due to a database problem.
    """

    if credentials is None:
        raise AuthError(detail="Authentication required", code="AUTH_REQUIRED")

    payload = decode_token(
        settings=settings,
        token=credentials.credentials,
        expected_token_type=ACCESS_TOKEN_TYPE,
    )
    user_id = _parse_token_subject(payload.get("sub"))

    try:
        with storage.connection() as connection:
            user = get_user_by_id(connection, user_id)
    except PsycopgError as exc:
        raise StorageError(
            detail="Unable to load the authenticated user",
            code="AUTH_USER_LOOKUP_FAILED",
        ) from exc

    if user is None or not bool(user["is_active"]):
        raise AuthError(detail="Authenticated user is invalid", code="AUTH_USER_INVALID")
    return user
