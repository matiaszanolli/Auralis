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

from auralis.version import __version__ as AURALIS_VERSION
from core.encoding import WAVEncoderError

logger = logging.getLogger(__name__)


def is_dev_mode() -> bool:
    """Return True when running in development mode (--dev flag or AURALIS_DEV_MODE env var).

    #4802: the env var is namespaced (AURALIS_DEV_MODE, not bare DEV_MODE) —
    Electron launches the backend as a child process inheriting the user's
    full environment, so a bare DEV_MODE left exported for an unrelated
    project would silently re-enable Swagger/ReDoc/OpenAPI and widen the
    CORS/WebSocket origin allowlists in a packaged build. Deliberately no
    backward-compatible alias for the old bare name: keeping one would
    reintroduce exactly the collision this rename exists to close.
    """
    if "--dev" in sys.argv:
        return True

    env_dev = os.environ.get("AURALIS_DEV_MODE", "").lower() in ("1", "true", "yes")
    if env_dev:
        # Env-var activation is the silent case (#4802) — `--dev` is already
        # visible in the launching command line, so only warn here.
        logger.warning(
            "Dev mode activated via AURALIS_DEV_MODE environment variable — "
            "Swagger UI, ReDoc, the raw OpenAPI schema, and widened CORS/"
            "WebSocket origin allowlists are enabled. Unset AURALIS_DEV_MODE "
            "if this was not intended."
        )
    return env_dev


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
        version=AURALIS_VERSION,
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

    @app.exception_handler(WAVEncoderError)
    async def wav_encoder_exception_handler(request: Request, exc: WAVEncoderError) -> JSONResponse:
        # #3912: every current WAVEncoderError call site already catches and
        # translates it explicitly (routers/files.py and core/job_lifecycle.py
        # via _safe_error_message(), core/chunk_streaming.py by re-raising as
        # RuntimeError) — this is a safety net for a future REST caller that
        # forgets to, so it gets a category message instead of falling through
        # to the generic "Internal server error" below with no class context.
        # (WebMEncoderError, the issue's other named type, no longer exists —
        # its module was removed in #5147; only WAVEncoderError survives.)
        logger.error(f"Unhandled WAVEncoderError on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Audio encoding failed"},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app
