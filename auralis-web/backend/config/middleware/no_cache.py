"""
No-Cache Middleware

Disables caching for frontend static files. Split out of
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


class NoCacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware to disable caching for frontend static files.

    Only applies to frontend assets (.html, .js, .css), not API responses.
    API streaming responses must NOT have cache-control headers modified.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # call_next(request) deliberately sits OUTSIDE the try below (#4808):
        # BaseHTTPMiddleware.call_next re-raises a downstream route handler's
        # exception at this call site, so catching Exception around it would
        # swallow that exception here and misattribute every unhandled route
        # error to NoCacheMiddleware instead of letting it reach
        # config/app.py's registered `@app.exception_handler(Exception)`.
        response = await call_next(request)

        try:
            # Only disable caching for frontend static files (not API endpoints)
            # API streaming responses must NOT have cache-control headers modified
            if not request.url.path.startswith('/api') and not request.url.path.startswith('/ws'):
                if request.url.path.endswith(('.html', '.js', '.css')) or request.url.path == '/':
                    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
                    response.headers["Pragma"] = "no-cache"
                    response.headers["Expires"] = "0"

            return cast(Response, response)
        except Exception as exc:
            return _middleware_error_response(exc, "NoCacheMiddleware")
