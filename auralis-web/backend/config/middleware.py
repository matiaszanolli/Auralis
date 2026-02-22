"""
Middleware Configuration

Sets up middleware for the FastAPI application including CORS, caching,
and security headers.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from typing import Any, cast
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class NoCacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware to disable caching for frontend static files.

    Only applies to frontend assets (.html, .js, .tsx, .jsx), not API responses.
    API streaming responses must NOT have cache-control headers modified.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        response = await call_next(request)

        # Only disable caching for frontend static files (not API endpoints)
        # API streaming responses must NOT have cache-control headers modified
        if not request.url.path.startswith('/api') and not request.url.path.startswith('/ws'):
            if request.url.path.endswith(('.html', '.js', '.tsx', '.jsx')) or request.url.path == '/':
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"

        return cast(Response, response)


def setup_middleware(app: FastAPI) -> None:
    """
    Add middleware to FastAPI application.

    Configures middleware in the correct order:
    1. NoCacheMiddleware - for frontend assets
    2. CORSMiddleware - for cross-origin requests

    Args:
        app: FastAPI application instance (modified in-place)
    """
    # Add no-cache middleware first (innermost in processing order)
    app.add_middleware(NoCacheMiddleware)

    # CORS middleware for cross-origin requests
    # Allow multiple dev server ports since Vite auto-increments if port is in use
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",      # React dev server (default)
            "http://127.0.0.1:3000",
            "http://localhost:3001",      # React dev server (alt ports)
            "http://localhost:3002",
            "http://localhost:3003",
            "http://localhost:3004",
            "http://localhost:3005",
            "http://localhost:3006",
            "http://localhost:8765",      # Production (same-origin but explicit)
            "http://127.0.0.1:8765",
        ],
        allow_credentials=True,
        # Explicit lists instead of wildcards — allow_credentials=True with "*"
        # violates the CORS spec and overly broadens the attack surface (#2224).
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "X-Session-Id"],
    )

    logger.debug("✅ Middleware configured: NoCacheMiddleware, CORSMiddleware")
