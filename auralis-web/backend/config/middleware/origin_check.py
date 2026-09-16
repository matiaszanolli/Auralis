"""
Origin Check Middleware

Rejects cross-origin state-changing REST requests (#4893). Split out of
config/middleware.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import Callable
from typing import Any, cast

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .error_response import _middleware_error_response
from .hosts import cors_allowed_origins

logger = logging.getLogger(__name__)


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """
    Rejects cross-origin state-changing requests lacking a trusted Origin.

    CORS blocks a hostile page's JavaScript from *reading* a cross-origin
    response, but per the Fetch spec a "simple request" (POST/PUT/DELETE with
    no body, or a CORS-safelisted Content-Type) never triggers a preflight —
    it still executes on the server. Any state-changing REST route whose
    input comes entirely from the URL path/query is exploitable blind via a
    hidden auto-submitting form or `navigator.sendBeacon()` from any page the
    user's browser happens to have open (#4893). This is the REST equivalent
    of the check `config.globals.ConnectionManager.connect` already does for
    WebSocket upgrades, which CORS does not cover at all.

    Applied to every state-changing method rather than only the currently
    known-vulnerable routes, so a future endpoint doesn't silently reopen
    this gap. GET/HEAD/OPTIONS pass through untouched — OPTIONS must reach
    CORSMiddleware unmodified to answer preflight requests.

    #5067: the origin allowlist is resolved once here, at middleware
    construction (app startup — Starlette builds the middleware stack once
    and caches it, so `__init__` runs once per app lifetime, not per
    request), rather than calling `cors_allowed_origins()` — and therefore
    `is_dev_mode()` — on every dispatch. `is_dev_mode()` logs a one-shot
    "dev mode activated" warning intended as a boot notice; calling it per
    request turned that into per-request log spam whenever
    AURALIS_DEV_MODE was set. `is_dev_mode()` itself must stay fully
    dynamic (re-evaluated on every direct call) for #4802's own tests, so
    the fix is caching the *result* here rather than changing that
    function's behavior. `CORSMiddleware`'s setup already resolves the same
    list once at app-construction time (setup_middleware() in __init__.py);
    this just brings `OriginCheckMiddleware` in line with that existing
    convention instead of inventing a new one.
    """

    _STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._cached_origins = frozenset(cors_allowed_origins())

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # The try below covers ONLY this middleware's own origin check.
        # call_next(request) is called exactly once, OUTSIDE the try, at the
        # bottom of this method — same reasoning as RateLimitMiddleware's
        # dispatch() comment in rate_limit.py (#4808).
        try:
            if request.method in self._STATE_CHANGING_METHODS and request.url.path.startswith("/api"):
                from ..globals import LOOPBACK_HOSTS

                origin = request.headers.get("origin", "").lower()
                if origin:
                    # Non-empty Origin: must be in the same allowlist CORS uses
                    # (cached once at construction — see class docstring, #5067).
                    if origin not in self._cached_origins:
                        logger.warning(
                            f"Rejected {request.method} {request.url.path}: untrusted origin {origin!r}"
                        )
                        return JSONResponse(status_code=403, content={"detail": "Untrusted origin"})
                else:
                    # Empty Origin: allow only from loopback so non-browser local
                    # processes on non-loopback interfaces can't bypass the check.
                    client_host = (request.client.host if request.client else "").lower()
                    if client_host not in LOOPBACK_HOSTS:
                        logger.warning(
                            f"Rejected {request.method} {request.url.path}: "
                            f"empty Origin from non-loopback host {client_host!r}"
                        )
                        return JSONResponse(status_code=403, content={"detail": "Untrusted origin"})
        except Exception as exc:
            return _middleware_error_response(exc, "OriginCheckMiddleware")

        return cast(Response, await call_next(request))
