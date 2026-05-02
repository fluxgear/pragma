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
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

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
        ValueError: If an unexpected logging level bypasses settings validation.
    """

    log_level = logging.getLevelName(settings.log_level)
    if not isinstance(log_level, int):
        raise ValueError(f'Invalid log level: {settings.log_level}')
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

    from pragma.modules import build_module_runtime, set_active_module_runtime
    from pragma.realtime import (
        build_realtime_hub,
        build_realtime_listener,
        build_realtime_publisher,
        set_active_realtime_publisher,
    )
    from pragma.themes import build_theme_runtime

    storage = DatabasePool(settings)
    theme_runtime = build_theme_runtime(settings)
    module_runtime = build_module_runtime(settings)
    realtime_publisher = build_realtime_publisher(settings)
    realtime_hub = build_realtime_hub(settings)
    realtime_listener = build_realtime_listener(settings, realtime_hub)

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
        app.state.theme_runtime = theme_runtime
        app.state.module_runtime = module_runtime
        app.state.realtime_publisher = realtime_publisher
        app.state.realtime_hub = realtime_hub
        app.state.realtime_listener = realtime_listener
        storage.open()
        app.state.storage = storage
        set_active_module_runtime(module_runtime)
        set_active_realtime_publisher(realtime_publisher)

        try:
            module_runtime.refresh(storage)
            await realtime_listener.start()
            yield
        finally:
            set_active_realtime_publisher(None)
            set_active_module_runtime(None)
            await realtime_listener.stop()
            await realtime_hub.shutdown()
            realtime_publisher.close()
            storage.close()

    return lifespan


_SECURITY_HEADER_DEFAULTS = {
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
}


def _add_browser_hardening_headers(app: FastAPI) -> None:
    """Install centralized browser hardening headers.

    Args:
        app: FastAPI application instance.

    Returns:
        None.

    Raises:
        None.
    """

    @app.middleware('http')
    async def browser_hardening_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Add safe default browser security headers to HTTP responses.

        Args:
            request: Incoming request.
            call_next: Next middleware/application callable.

        Returns:
            Response: Response with hardening headers when not already set.

        Raises:
            None.
        """

        response = await call_next(request)
        for header_name, header_value in _SECURITY_HEADER_DEFAULTS.items():
            response.headers.setdefault(header_name, header_value)
        return response


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Args:
        None.

    Returns:
        FastAPI: Configured FastAPI application.

    Raises:
        ValidationError: If required configuration is missing or invalid.
    """

    from pragma.ai.router import router as ai_router
    from pragma.auth.admin_router import router as users_router
    from pragma.modules.router import router as modules_router
    from pragma.public.router import router as public_router
    from pragma.realtime.router import router as realtime_router
    from pragma.search.router import router as search_router

    settings = get_settings()
    _configure_logging(settings)

    app = FastAPI(
        title='Pragma API',
        version=__version__,
        lifespan=build_lifespan(settings),
    )
    _add_browser_hardening_headers(app)
    register_exception_handlers(app)
    app.include_router(system_router, prefix='/api/v1')
    app.include_router(install_router, prefix='/api/v1')
    app.include_router(auth_router, prefix='/api/v1')
    app.include_router(content_router, prefix='/api/v1')
    app.include_router(media_router, prefix='/api/v1')
    app.include_router(search_router, prefix='/api/v1')
    app.include_router(ai_router, prefix='/api/v1')
    app.include_router(modules_router, prefix='/api/v1')
    app.include_router(users_router, prefix='/api/v1')
    app.include_router(realtime_router, prefix='/api/v1')
    app.include_router(public_router)
    return app
