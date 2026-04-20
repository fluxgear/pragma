# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Password hashing and JWT helpers for authentication.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash

from pragma.config import Settings
from pragma.errors import AuthError

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
_PASSWORD_HASHER = PasswordHash.recommended()


def utc_now() -> datetime:
    """Return the current UTC timestamp.

    Args:
        None.

    Returns:
        datetime: Timezone-aware UTC timestamp.

    Raises:
        None.
    """

    return datetime.now(tz=UTC)


def normalize_identity(value: str) -> str:
    """Normalize login identifiers for case-insensitive lookup.

    Args:
        value: Raw email or username value.

    Returns:
        str: Normalized identifier.

    Raises:
        None.
    """

    return value.strip().lower()


def hash_password(password: str) -> str:
    """Hash a raw password for durable storage.

    Args:
        password: Raw password string.

    Returns:
        str: Password hash string.

    Raises:
        ValueError: If the hashing library rejects the password input.
    """

    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a raw password against a stored hash.

    Args:
        password: Raw password string.
        password_hash: Stored password hash string.

    Returns:
        bool: True when the password is valid, otherwise False.

    Raises:
        ValueError: If the stored hash format is invalid.
    """

    return bool(_PASSWORD_HASHER.verify(password, password_hash))


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token before persisting it.

    Args:
        token: Raw refresh token.

    Returns:
        str: Hex-encoded SHA-256 digest.

    Raises:
        None.
    """

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(settings: Settings, user_id: UUID) -> tuple[str, datetime]:
    """Create a signed short-lived access token.

    Args:
        settings: Application settings.
        user_id: Authenticated user identifier.

    Returns:
        tuple[str, datetime]: Encoded token and its expiry timestamp.

    Raises:
        None.
    """

    issued_at = utc_now()
    expires_at = issued_at + timedelta(minutes=settings.jwt_access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "typ": ACCESS_TOKEN_TYPE,
        "jti": str(uuid4()),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def create_refresh_token(
    settings: Settings, user_id: UUID, session_id: UUID
) -> tuple[str, datetime]:
    """Create a signed refresh token bound to a refresh-session identifier.

    Args:
        settings: Application settings.
        user_id: Authenticated user identifier.
        session_id: Refresh-session identifier.

    Returns:
        tuple[str, datetime]: Encoded token and its expiry timestamp.

    Raises:
        None.
    """

    issued_at = utc_now()
    expires_at = issued_at + timedelta(days=settings.jwt_refresh_token_ttl_days)
    payload = {
        "sub": str(user_id),
        "typ": REFRESH_TOKEN_TYPE,
        "jti": str(session_id),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(
    settings: Settings, token: str, expected_token_type: str
) -> dict[str, str | int]:
    """Decode and validate a signed JWT token.

    Args:
        settings: Application settings.
        token: Encoded JWT token.
        expected_token_type: Token type expected by the caller.

    Returns:
        dict[str, str | int]: Decoded token payload.

    Raises:
        AuthError: If the token is expired, malformed, or of the wrong type.
    """

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise AuthError(detail="Token has expired", code="TOKEN_EXPIRED") from exc
    except InvalidTokenError as exc:
        raise AuthError(detail="Token is invalid", code="TOKEN_INVALID") from exc

    token_type = payload.get("typ")
    if token_type != expected_token_type:
        raise AuthError(detail="Token type is invalid", code="TOKEN_TYPE_INVALID")
    return payload
