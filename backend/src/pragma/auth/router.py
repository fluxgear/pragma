# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Authentication routes for login, refresh, logout, and identity lookup.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, Response, status

from pragma.auth.admin_service import change_current_user_password
from pragma.auth.dependencies import get_current_user
from pragma.auth.models import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from pragma.auth.service import authenticate_user, logout_user, refresh_user_session
from pragma.config import Settings, get_settings
from pragma.errors import ApiError, AuthError
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

_AUTH_TOKEN_ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ApiError,
        "description": "Authentication credentials are invalid or expired",
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ApiError,
        "description": "Request validation failed",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ApiError,
        "description": "Authentication storage is unavailable",
    },
}
_AUTH_STORAGE_ERROR_RESPONSES = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ApiError,
        "description": "Authentication storage is unavailable",
    },
}
_AUTH_IDENTITY_ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ApiError,
        "description": "Authentication required",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ApiError,
        "description": "Authentication storage is unavailable",
    },
}
_AUTH_PASSWORD_ERROR_RESPONSES = {
    **_AUTH_TOKEN_ERROR_RESPONSES,
    status.HTTP_401_UNAUTHORIZED: {
        "model": ApiError,
        "description": "Authentication or current password is invalid",
    },
}

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, settings: Settings, refresh_token: str) -> None:
    """Set the refresh-token cookie on an HTTP response.

    Args:
        response: Outgoing HTTP response.
        settings: Application settings.
        refresh_token: Raw refresh token to persist in the cookie.

    Returns:
        None.

    Raises:
        None.
    """

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path=settings.refresh_cookie_path,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    """Delete the refresh-token cookie from an HTTP response.

    Args:
        response: Outgoing HTTP response.
        settings: Application settings.

    Returns:
        None.

    Raises:
        None.
    """

    response.delete_cookie(key=settings.refresh_cookie_name, path=settings.refresh_cookie_path)


def _require_refresh_cookie(request: Request, settings: Settings) -> str:
    """Read and validate the refresh-token cookie from the request.

    Args:
        request: Incoming HTTP request.
        settings: Application settings.

    Returns:
        str: Raw refresh token from the cookie.

    Raises:
        AuthError: If the refresh-token cookie is missing.
    """

    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token is None:
        raise AuthError(detail="Refresh token is required", code="REFRESH_TOKEN_REQUIRED")
    return refresh_token


def _normalize_origin_from_url(value: str) -> str | None:
    """Normalize a URL-like value to its serialized origin.

    Args:
        value: Absolute URL or Origin header value to normalize.

    Returns:
        str | None: Lowercase origin without default ports, or None if invalid.

    Raises:
        None.
    """

    try:
        parsed = urlparse(value.strip())
        hostname = parsed.hostname
    except ValueError:
        return None

    if parsed.scheme not in {"http", "https"} or hostname is None:
        return None

    scheme = parsed.scheme.lower()
    host = hostname.lower()
    netloc = parsed.netloc.rsplit("@", maxsplit=1)[-1]
    port_text = ""
    if netloc.startswith("["):
        bracket_index = netloc.find("]")
        if bracket_index == -1:
            return None
        port_text = netloc[bracket_index + 1 :].removeprefix(":")
    elif ":" in netloc:
        port_text = netloc.rsplit(":", maxsplit=1)[-1]
    if port_text and not port_text.isdecimal():
        return None

    port = int(port_text) if port_text else None
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    is_default_port = (scheme == "http" and port == 80) or (
        scheme == "https" and port == 443
    )
    if port is None or is_default_port:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def _refresh_cookie_header_origin(request: Request) -> str | None:
    """Extract the request's Origin/Referer origin for CSRF checks.

    Args:
        request: Incoming HTTP request.

    Returns:
        str | None: Normalized supplied origin, an empty string for an invalid
            supplied header, or None when both headers are absent.

    Raises:
        None.
    """

    for header_name in ("origin", "referer"):
        header_value = request.headers.get(header_name)
        if header_value is None:
            continue
        supplied_origin = _normalize_origin_from_url(header_value)
        return supplied_origin or ""
    return None


def _allowed_refresh_cookie_origins(request: Request, settings: Settings) -> frozenset[str]:
    """Return allowed origins for SameSite=None refresh-cookie requests.

    Args:
        request: Incoming HTTP request.
        settings: Application settings containing the configured site URL.

    Returns:
        frozenset[str]: Configured site origin plus the current API origin.

    Raises:
        None.
    """

    origins = {
        origin
        for origin in (
            _normalize_origin_from_url(settings.base_url),
            _normalize_origin_from_url(str(request.url)),
        )
        if origin is not None
    }
    return frozenset(origins)


def _require_same_site_none_origin(request: Request, settings: Settings) -> None:
    """Require same-site Origin/Referer for SameSite=None cookie requests.

    Args:
        request: Incoming HTTP request.
        settings: Application settings controlling refresh-cookie SameSite mode.

    Returns:
        None.

    Raises:
        AuthError: If SameSite=None is active and the request lacks a valid,
            allowed Origin or Referer header.
    """

    if settings.refresh_cookie_samesite != "none":
        return

    supplied_origin = _refresh_cookie_header_origin(request)
    if supplied_origin is None:
        raise AuthError(
            detail="Origin or Referer header is required",
            code="CSRF_ORIGIN_REQUIRED",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if supplied_origin not in _allowed_refresh_cookie_origins(request, settings):
        raise AuthError(
            detail="Origin is not allowed for this request",
            code="CSRF_ORIGIN_FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


@router.post("/login", response_model=TokenResponse, responses=_AUTH_TOKEN_ERROR_RESPONSES)
def login(
    payload: LoginRequest,
    response: Response,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Authenticate a user and return a new access token.

    Args:
        payload: Login request payload.
        response: Outgoing HTTP response.
        storage: Initialized database pool manager.
        settings: Application settings.

    Returns:
        TokenResponse: Access token payload with user information.

    Raises:
        AuthError: If supplied credentials are invalid.
        StorageError: If the storage layer fails during authentication.
    """

    auth_payload = authenticate_user(storage, settings, payload.identity, payload.password)
    _set_refresh_cookie(response, settings, auth_payload["refresh_token"])
    return TokenResponse(
        access_token=auth_payload["access_token"],
        expires_in=auth_payload["expires_in"],
        user=UserResponse.from_record(auth_payload["user"]),
    )


@router.post("/refresh", response_model=TokenResponse, responses=_AUTH_TOKEN_ERROR_RESPONSES)
def refresh(
    request: Request,
    response: Response,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Rotate the refresh token and return a new access token.

    Args:
        request: Incoming HTTP request.
        response: Outgoing HTTP response.
        storage: Initialized database pool manager.
        settings: Application settings.

    Returns:
        TokenResponse: Access token payload with user information.

    Raises:
        AuthError: If the refresh token is missing or invalid.
        StorageError: If the storage layer fails during refresh.
    """

    _require_same_site_none_origin(request, settings)
    refresh_token = _require_refresh_cookie(request, settings)
    auth_payload = refresh_user_session(storage, settings, refresh_token)
    _set_refresh_cookie(response, settings, auth_payload["refresh_token"])
    return TokenResponse(
        access_token=auth_payload["access_token"],
        expires_in=auth_payload["expires_in"],
        user=UserResponse.from_record(auth_payload["user"]),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_AUTH_STORAGE_ERROR_RESPONSES,
)
def logout(
    request: Request,
    response: Response,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Revoke the current refresh token and clear the auth cookie.

    Args:
        request: Incoming HTTP request.
        response: Outgoing HTTP response.
        storage: Initialized database pool manager.
        settings: Application settings.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        AuthError: If SameSite=None origin validation fails.
        StorageError: If the storage layer fails during logout.
    """

    _require_same_site_none_origin(request, settings)
    logout_user(storage, settings, request.cookies.get(settings.refresh_cookie_name))
    _clear_refresh_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse, responses=_AUTH_IDENTITY_ERROR_RESPONSES)
def me(current_user: Annotated[dict[str, object], Depends(get_current_user)]) -> UserResponse:
    """Return the current authenticated user.

    Args:
        current_user: Authenticated user record injected by the auth dependency.

    Returns:
        UserResponse: Authenticated user payload.

    Raises:
        AuthError: If authentication fails.
        StorageError: If user lookup fails.
    """

    return UserResponse.from_record(current_user)


@router.post(
    "/change-password",
    response_model=UserResponse,
    responses=_AUTH_PASSWORD_ERROR_RESPONSES,
)
def change_password(
    payload: ChangePasswordRequest,
    storage: Annotated[DatabasePool, Depends(get_storage)],
    current_user: Annotated[dict[str, object], Depends(get_current_user)],
) -> UserResponse:
    """Change the current authenticated user's password.

    Args:
        payload: Authenticated password-change payload.
        storage: Initialized database pool manager.
        current_user: Authenticated user context.

    Returns:
        UserResponse: Updated authenticated user payload.

    Raises:
        AuthError: If authentication or the current password is invalid.
        StorageError: If the storage layer fails during password rotation.
    """

    updated_user = change_current_user_password(
        storage,
        dict(current_user),
        payload.current_password,
        payload.new_password,
    )
    return UserResponse.from_record(updated_user)
