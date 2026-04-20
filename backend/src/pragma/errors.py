# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""Structured error handling for the Pragma backend.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ApiError(BaseModel):
    """Structured API error payload.

    Args:
        BaseModel: Pydantic model base class.

    Returns:
        None.

    Raises:
        ValidationError: If payload fields are invalid.
    """

    detail: str
    code: str


class PragmaError(Exception):
    """Base application error for structured API responses.

    Args:
        detail: Human-readable error detail.
        code: Stable machine-readable error code.
        status_code: HTTP status code for the response.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(self, detail: str, code: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


class ConfigError(PragmaError):
    """Raised when runtime configuration or install state is invalid.

    Args:
        detail: Human-readable error detail.
        code: Stable machine-readable error code.
        status_code: HTTP status code for the response.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        detail: str,
        code: str = "CONFIG_ERROR",
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(detail=detail, code=code, status_code=status_code)


class StorageError(PragmaError):
    """Raised when storage dependencies fail.

    Args:
        detail: Human-readable error detail.
        code: Stable machine-readable error code.
        status_code: HTTP status code for the response.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        detail: str,
        code: str = "STORAGE_ERROR",
        status_code: int = HTTPStatus.SERVICE_UNAVAILABLE,
    ) -> None:
        super().__init__(detail=detail, code=code, status_code=status_code)


class ContentError(PragmaError):
    """Raised when content-domain operations fail.

    Args:
        detail: Human-readable error detail.
        code: Stable machine-readable error code.
        status_code: HTTP status code for the response.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        detail: str,
        code: str = "CONTENT_ERROR",
        status_code: int = HTTPStatus.BAD_REQUEST,
    ) -> None:
        super().__init__(detail=detail, code=code, status_code=status_code)


class MediaError(PragmaError):
    """Raised when media-domain operations fail.

    Args:
        detail: Human-readable error detail.
        code: Stable machine-readable error code.
        status_code: HTTP status code for the response.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        detail: str,
        code: str = "MEDIA_ERROR",
        status_code: int = HTTPStatus.BAD_REQUEST,
    ) -> None:
        super().__init__(detail=detail, code=code, status_code=status_code)


class AuthError(PragmaError):
    """Raised when authentication or authorization fails.

    Args:
        detail: Human-readable error detail.
        code: Stable machine-readable error code.
        status_code: HTTP status code for the response.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        detail: str,
        code: str = "AUTH_ERROR",
        status_code: int = HTTPStatus.UNAUTHORIZED,
    ) -> None:
        super().__init__(detail=detail, code=code, status_code=status_code)


class SearchError(PragmaError):
    """Raised when search-domain operations fail.

    Args:
        detail: Human-readable error detail.
        code: Stable machine-readable error code.
        status_code: HTTP status code for the response.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        detail: str,
        code: str = "SEARCH_ERROR",
        status_code: int = HTTPStatus.BAD_REQUEST,
    ) -> None:
        super().__init__(detail=detail, code=code, status_code=status_code)


class ThemeError(PragmaError):
    """Raised when theme-domain operations fail.

    Args:
        detail: Human-readable error detail.
        code: Stable machine-readable error code.
        status_code: HTTP status code for the response.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        detail: str,
        code: str = "THEME_ERROR",
        status_code: int = HTTPStatus.BAD_REQUEST,
    ) -> None:
        super().__init__(detail=detail, code=code, status_code=status_code)


class ModuleError(PragmaError):
    """Raised when module-domain operations fail.

    Args:
        detail: Human-readable error detail.
        code: Stable machine-readable error code.
        status_code: HTTP status code for the response.

    Returns:
        None.

    Raises:
        None.
    """

    def __init__(
        self,
        detail: str,
        code: str = "MODULE_ERROR",
        status_code: int = HTTPStatus.BAD_REQUEST,
    ) -> None:
        super().__init__(detail=detail, code=code, status_code=status_code)


def build_error_payload(detail: str, code: str) -> dict[str, str]:
    """Build a structured JSON error payload.

    Args:
        detail: Human-readable error detail.
        code: Stable machine-readable error code.

    Returns:
        dict[str, str]: Error payload matching the API contract.

    Raises:
        None.
    """

    return ApiError(detail=detail, code=code).model_dump()


async def pragma_exception_handler(request: Request, exc: PragmaError) -> JSONResponse:
    """Render structured responses for application errors.

    Args:
        request: Current request object.
        exc: Application error instance.

    Returns:
        JSONResponse: Structured error response.

    Raises:
        None.
    """

    logger.warning(
        "Request failed with pragma error",
        extra={
            "path": str(request.url.path),
            "code": exc.code,
            "status_code": exc.status_code,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_payload(detail=exc.detail, code=exc.code),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Render structured responses for FastAPI HTTP exceptions.

    Args:
        request: Current request object.
        exc: FastAPI HTTP exception.

    Returns:
        JSONResponse: Structured error response.

    Raises:
        None.
    """

    detail = str(exc.detail)
    code = f"HTTP_{exc.status_code}"
    logger.warning(
        "Request failed with HTTP exception",
        extra={
            "path": str(request.url.path),
            "code": code,
            "status_code": exc.status_code,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_payload(detail=detail, code=code),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Render structured responses for request validation errors.

    Args:
        request: Current request object.
        exc: Validation exception raised by FastAPI.

    Returns:
        JSONResponse: Structured validation error response.

    Raises:
        None.
    """

    logger.warning(
        "Request validation failed",
        extra={
            "path": str(request.url.path),
            "errors": exc.errors(),
        },
    )
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content=build_error_payload(
            detail="Request validation failed",
            code="VALIDATION_ERROR",
        ),
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render structured responses for unexpected exceptions.

    Args:
        request: Current request object.
        exc: Unexpected application exception.

    Returns:
        JSONResponse: Structured internal error response.

    Raises:
        None.
    """

    logger.exception(
        "Unhandled exception during request processing",
        extra={"path": str(request.url.path)},
    )
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content=build_error_payload(
            detail="Internal server error",
            code="INTERNAL_ERROR",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register application exception handlers on the FastAPI app.

    Args:
        app: FastAPI application instance.

    Returns:
        None.

    Raises:
        None.
    """

    app.add_exception_handler(PragmaError, pragma_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
