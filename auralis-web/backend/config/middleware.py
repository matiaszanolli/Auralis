"""
Middleware Configuration

Sets up middleware for the FastAPI application including CORS, caching,
and security headers.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
import time
from typing import Any, cast
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add browser security headers to all responses.

    Sets standard headers to prevent clickjacking, MIME-type sniffing,
    and other common browser-based attacks.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return cast(Response, response)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple per-path rate limiting for expensive REST endpoints (#2575).

    Uses a sliding-window counter per client IP + path prefix.
    Only applies to paths in ``_RATE_LIMITS``; all other routes pass through.
    """

    # path-prefix → (max_requests, window_seconds)
    _RATE_LIMITS: dict[str, tuple[int, int]] = {
        "/api/files/upload": (5, 60),       # 5 uploads per minute
        "/api/processing": (10, 60),        # 10 processing jobs per minute
        "/api/library/scan": (2, 60),       # 2 scans per minute
        "/api/similarity": (20, 60),        # 20 similarity queries per minute
    }

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        # {client_key: [timestamp, ...]}
        self._windows: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        path = request.url.path

        # Find matching rate-limit rule
        limit_rule: tuple[int, int] | None = None
        for prefix, rule in self._RATE_LIMITS.items():
            if path.startswith(prefix):
                limit_rule = rule
                break

        if limit_rule is None:
            return await call_next(request)

        max_requests, window_sec = limit_rule
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{path}"
        now = time.monotonic()

        # Prune expired entries and check limit
        timestamps = self._windows.get(key, [])
        timestamps = [t for t in timestamps if now - t < window_sec]

        if len(timestamps) >= max_requests:
            retry_after = int(window_sec - (now - timestamps[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
        self._windows[key] = timestamps

        return await call_next(request)


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

    # Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting for expensive endpoints (#2575)
    app.add_middleware(RateLimitMiddleware)

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

    logger.debug("✅ Middleware configured: NoCacheMiddleware, SecurityHeadersMiddleware, CORSMiddleware")
