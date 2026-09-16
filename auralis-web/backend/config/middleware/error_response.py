"""
Middleware Error Response

Shared JSON 500 for a failure in a middleware's own logic (#4378, #4808).
Split out of config/middleware.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging

from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def _middleware_error_response(exc: Exception, where: str) -> JSONResponse:
    """Uniform JSON 500 for an exception raised by a middleware's OWN logic
    (not a downstream route handler's — see #4808 on why `call_next(request)`
    must never sit inside the `try` this feeds).

    ``BaseHTTPMiddleware.dispatch`` runs outside FastAPI's ExceptionMiddleware,
    so ``@app.exception_handler(Exception)`` does not cover it — a raise here
    would otherwise reach Starlette's ``ServerErrorMiddleware`` and return a
    generic error response rather than one this codebase's own callers
    construct (#4378). #4808 found that ServerErrorMiddleware's response
    shape is no longer actually different — ``config/app.py``'s registered
    ``@app.exception_handler(Exception)`` produces the identical
    ``{"detail": "Internal server error"}`` / 500 shape — but this helper
    stays: it's still the right place to log which middleware's own
    bookkeeping failed, distinct from a route handler's exception.
    """
    logger.error(f"Unhandled exception in {where}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
