"""
No-Cache Middleware

Disables caching for frontend entry points (hashed bundles are immutable). Split out of
config/middleware.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any, cast

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .error_response import _middleware_error_response


# Where Vite emits its content-hashed bundles (index-<hash>.js, ...).
HASHED_ASSET_PREFIX = '/assets/'


class NoCacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware to disable caching for frontend entry points.

    Applies to / and .html/.js/.css outside /assets/, where a stale copy would
    pin users to an old build. Content-hashed bundles under /assets/ are marked
    immutable instead. Never touches API responses: API streaming responses must
    NOT have cache-control headers modified.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # call_next(request) deliberately sits OUTSIDE the try below (#4808):
        # BaseHTTPMiddleware.call_next re-raises a downstream route handler's
        # exception at this call site, so catching Exception around it would
        # swallow that exception here and misattribute every unhandled route
        # error to NoCacheMiddleware instead of letting it reach
        # UnhandledExceptionMiddleware, which answers it (#5986).
        response = await call_next(request)

        try:
            # Only disable caching for frontend static files (not API endpoints)
            # API streaming responses must NOT have cache-control headers modified
            path = request.url.path
            if not path.startswith('/api') and not path.startswith('/ws'):
                if path.startswith(HASHED_ASSET_PREFIX) and path.endswith(('.js', '.css')):
                    # Vite names these by content hash: a new build is a new URL,
                    # so a given URL never changes. no-store here threw away the
                    # caching the hashing exists to provide (#5071). Only a 200
                    # is marked immutable; a 404 for a stale hash must not stick.
                    if response.status_code == 200:
                        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                elif path.endswith(('.html', '.js', '.css')) or path == '/':
                    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
                    response.headers["Pragma"] = "no-cache"
                    response.headers["Expires"] = "0"

            return cast(Response, response)
        except Exception as exc:
            return _middleware_error_response(exc, "NoCacheMiddleware")
