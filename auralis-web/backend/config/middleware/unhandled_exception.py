"""
Unhandled Exception Middleware

Turns a route exception that nothing mapped to a status code into the generic
JSON 500 *inside* the middleware stack (#5986).

``@app.exception_handler(Exception)`` is installed on Starlette's outermost
``ServerErrorMiddleware``, outside every user middleware. Since #4808 each
``BaseHTTPMiddleware`` here calls ``call_next`` outside its ``try``, so the
exception propagated past SecurityHeaders, NoCache and CORS before that handler
built the response: every 500 carried no CSP, X-Frame-Options or CORS headers (a
cross-origin client saw a network error, not the JSON body), and
``ServerErrorMiddleware`` re-raised after sending, logging the traceback twice.
Catching here, as the innermost middleware, lets the 500 travel back out through
all of them like any other response.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any, cast

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .error_response import unhandled_exception_response


class UnhandledExceptionMiddleware(BaseHTTPMiddleware):
    """Answer an escaped route exception with the generic 500 (logged once).

    HTTPException, RequestValidationError and WAVEncoderError are handled by
    FastAPI's ExceptionMiddleware beneath this one, so only genuinely unhandled
    exceptions arrive here.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        try:
            return cast(Response, await call_next(request))
        except Exception as exc:
            return unhandled_exception_response(request, exc)
