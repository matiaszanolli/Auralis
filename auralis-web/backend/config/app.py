"""
FastAPI Application Factory

Creates and configures the FastAPI application instance with metadata,
documentation URLs, and default settings.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
import os
import sys
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def is_dev_mode() -> bool:
    """Return True when running in development mode (--dev flag or DEV_MODE env var)."""
    return "--dev" in sys.argv or os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")


def create_app(lifespan: Any = None) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        lifespan: Optional async context manager for startup/shutdown handling

    Returns:
        Configured FastAPI instance with metadata and documentation URLs
    """
    # Only expose Swagger UI / ReDoc / the raw OpenAPI schema in development mode
    # to avoid leaking the full API schema in production (fixes #2418). Disabling
    # docs_url/redoc_url alone left FastAPI serving the complete schema at the
    # default /openapi.json in production, so openapi_url must be disabled too
    # (#4375).
    is_dev = is_dev_mode()
    app = FastAPI(
        title="Auralis Web API",
        description="Modern web backend for Auralis audio processing",
        version="1.0.0",
        docs_url="/api/docs" if is_dev else None,
        redoc_url="/api/redoc" if is_dev else None,
        openapi_url="/api/openapi.json" if is_dev else None,
        lifespan=lifespan,
    )

    # Global exception handlers (#2126, #2092)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Extract only JSON-safe fields from Pydantic v2 errors.
        # exc.errors() can contain raw ValueError objects in ctx which
        # are not JSON-serializable.
        errors = [
            {
                "field": ".".join(str(loc) for loc in e.get("loc", [])),
                "message": e.get("msg", ""),
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"detail": "Validation error", "errors": errors},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app
