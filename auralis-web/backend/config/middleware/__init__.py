"""
Middleware Configuration

Sets up middleware for the FastAPI application including CORS, caching,
and security headers.

A package since #5479, one module per middleware. setup_middleware() is the
single wiring point:
- error_response.py    shared JSON 500 for a middleware's own failure
- no_cache.py          NoCacheMiddleware
- security_headers.py  SecurityHeadersMiddleware and the CSP
- rate_limit.py        RateLimitMiddleware
- unhandled_exception.py  UnhandledExceptionMiddleware
- origin_check.py      OriginCheckMiddleware
- hosts.py             cors_allowed_origins(), trusted_hosts()

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .hosts import cors_allowed_origins, trusted_hosts
from .no_cache import NoCacheMiddleware
from .origin_check import OriginCheckMiddleware
from .rate_limit import RateLimitMiddleware
from .security_headers import SecurityHeadersMiddleware
from .unhandled_exception import UnhandledExceptionMiddleware

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """
    Add middleware to FastAPI application.

    `add_middleware` composes LIFO: the last-registered middleware wraps
    outermost. Request-inbound order (outermost first) is:
    1. CORSMiddleware - cross-origin requests
    2. SecurityHeadersMiddleware - security headers on every response
    3. NoCacheMiddleware - no-cache headers for frontend assets
    4. OriginCheckMiddleware - CSRF-shaped request rejection (#4893)
    5. TrustedHostMiddleware - Host header validation (#4353)
    6. RateLimitMiddleware - rate limiting for expensive endpoints (#2575)
    7. UnhandledExceptionMiddleware - generic 500 for escaped route exceptions
       (#5986), innermost, so that 500 still gets every header above

    See the registration order below (reverse of the above) for why each
    middleware is placed where it is.

    Args:
        app: FastAPI application instance (modified in-place)
    """
    # Starlette runs middleware in REVERSE add order, so the last-added wraps
    # outermost. Register RateLimit FIRST (innermost) so SecurityHeaders and
    # NoCache wrap it — otherwise a rate-limit 429 short-circuits before those
    # run and is returned without the documented security headers (#3843).
    #
    # Resulting request-inbound order: CORS → SecurityHeaders → NoCache →
    # OriginCheck → TrustedHost → RateLimit → UnhandledException → app; a
    # 403/429/400 bubbles back up through SecurityHeaders/NoCache, and so does
    # the 500 for a route exception (#5986).

    # Generic 500 for a route exception nothing mapped to a status — innermost,
    # so the exception never escapes past SecurityHeaders/NoCache/CORS into
    # ServerErrorMiddleware, which sits outside all of them (#5986).
    app.add_middleware(UnhandledExceptionMiddleware)

    # Rate limiting for expensive endpoints (#2575) — innermost
    app.add_middleware(RateLimitMiddleware)

    # Host-header validation (#4353) — wraps RateLimit, wrapped by
    # SecurityHeaders. Placed here rather than outermost for the same reason
    # #3843 reordered RateLimit: an "Invalid host header" 400 is a response
    # like any other and should carry the documented security headers, which it
    # would not if it short-circuited outside SecurityHeadersMiddleware. It
    # still runs before RateLimit, so a rebinding probe cannot consume the rate
    # budget, and before any route handler.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts())

    # Origin validation for state-changing REST requests (#4893) — runs
    # before TrustedHost on the request-inbound path, so it cannot rely on
    # the Host header having been validated yet (#5275); wraps RateLimit
    # (so a rejected CSRF-shaped request never consumes rate budget) and is
    # wrapped by SecurityHeaders so its 403 still carries the documented
    # headers.
    app.add_middleware(OriginCheckMiddleware)

    # No-cache middleware for frontend assets
    app.add_middleware(NoCacheMiddleware)

    # Security headers middleware — wraps RateLimit so 429s get the headers too
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS middleware for cross-origin requests.
    # Allow multiple dev server ports since Vite auto-increments if port is in
    # use. Generate both `localhost` and `127.0.0.1` entries for every port —
    # browsers treat them as distinct origins, so a dev opening the app via
    # the IP form on an alt port (e.g. 127.0.0.1:3001) was previously blocked
    # by CORS preflight even though localhost:3001 was allowed (#3539 /
    # BE-NEW-81).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins(),
        allow_credentials=True,
        # Explicit lists instead of wildcards — allow_credentials=True with "*"
        # violates the CORS spec and overly broadens the attack surface (#2224).
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        # X-Confirm-Reset is the library-reset guard routers/library.py requires
        # and settingsService.ts sends, so a cross-origin page needs it preflighted
        # (#5989). Keep this in step with the custom headers the frontend sends.
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "Accept",
            "X-Session-Id",
            "X-Confirm-Reset",
        ],
    )

    logger.debug(
        "✅ Middleware configured: UnhandledExceptionMiddleware, TrustedHostMiddleware, RateLimitMiddleware, "
        "OriginCheckMiddleware, NoCacheMiddleware, SecurityHeadersMiddleware, CORSMiddleware"
    )
