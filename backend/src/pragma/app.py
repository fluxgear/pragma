# Copyright (c) 2026 Marc Mironescu / FluxGear. MIT License.
"""FastAPI application factory for the Pragma backend.

Args:
    None.

Returns:
    None.

Raises:
    None.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pragma import __version__
from pragma.auth.router import router as auth_router
from pragma.config import Settings, get_settings
from pragma.content.router import router as content_router
from pragma.errors import register_exception_handlers
from pragma.install.router import router as install_router
from pragma.media.router import router as media_router
from pragma.storage.pool import DatabasePool
from pragma.system.router import router as system_router


def _configure_logging(settings: Settings) -> None:
    """Configure application logging for the backend process.

    Args:
        settings: Application settings.

    Returns:
        None.

    Raises:
        None.
    """

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level)


def build_lifespan(settings: Settings) -> Callable[[FastAPI], AsyncIterator[None]]:
    """Build the FastAPI lifespan handler for storage lifecycle management.

    Args:
        settings: Application settings.

    Returns:
        Callable[[FastAPI], AsyncIterator[None]]: Configured FastAPI lifespan handler.

    Raises:
        None.
    """

    storage = DatabasePool(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Open and close storage resources around the app lifespan.

        Args:
            app: FastAPI application instance.

        Returns:
            AsyncIterator[None]: Async application lifespan context.

        Raises:
            StorageError: If the database pool cannot be initialized.
        """

        app.state.settings = settings
        storage.open()
        app.state.storage = storage
        try:
            yield
        finally:
            storage.close()

    return lifespan


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Args:
        None.

    Returns:
        FastAPI: Configured FastAPI application.

    Raises:
        ValidationError: If required configuration is missing or invalid.
    """

    settings = get_settings()
    _configure_logging(settings)

    app = FastAPI(
        title='Pragma API',
        version=__version__,
        lifespan=build_lifespan(settings),
    )
    register_exception_handlers(app)
    app.include_router(system_router, prefix='/api/v1')
    app.include_router(install_router, prefix='/api/v1')
    app.include_router(auth_router, prefix='/api/v1')
    app.include_router(content_router, prefix='/api/v1')
    app.include_router(media_router, prefix='/api/v1')
    return app
