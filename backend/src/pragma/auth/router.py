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

from fastapi import APIRouter, Depends, Request, Response, status

from pragma.auth.dependencies import get_current_user
from pragma.auth.models import LoginRequest, TokenResponse, UserResponse
from pragma.auth.service import authenticate_user, logout_user, refresh_user_session
from pragma.config import Settings, get_settings
from pragma.storage import get_storage
from pragma.storage.pool import DatabasePool

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
        from pragma.errors import AuthError

        raise AuthError(detail="Refresh token is required", code="REFRESH_TOKEN_REQUIRED")
    return refresh_token


@router.post("/login", response_model=TokenResponse)
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


@router.post("/refresh", response_model=TokenResponse)
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

    refresh_token = _require_refresh_cookie(request, settings)
    auth_payload = refresh_user_session(storage, settings, refresh_token)
    _set_refresh_cookie(response, settings, auth_payload["refresh_token"])
    return TokenResponse(
        access_token=auth_payload["access_token"],
        expires_in=auth_payload["expires_in"],
        user=UserResponse.from_record(auth_payload["user"]),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
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
        StorageError: If the storage layer fails during logout.
    """

    logout_user(storage, settings, request.cookies.get(settings.refresh_cookie_name))
    _clear_refresh_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
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
