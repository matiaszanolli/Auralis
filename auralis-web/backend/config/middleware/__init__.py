"""
Middleware Configuration

Sets up middleware for the FastAPI application including CORS, caching,
and security headers.

A package since #5479, one module per middleware. setup_middleware() is the
single wiring point, and every name is re-exported here, so
`from config.middleware import X` is unchanged:
- error_response.py    shared JSON 500 for a middleware's own failure
- no_cache.py          NoCacheMiddleware
- security_headers.py  SecurityHeadersMiddleware and the CSP
- rate_limit.py        RateLimitMiddleware
- origin_check.py      OriginCheckMiddleware
- hosts.py             cors_allowed_origins(), trusted_hosts()

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .error_response import _middleware_error_response  # noqa: F401
from .hosts import (  # noqa: F401
    _TEST_HOSTS,
    _TRUSTED_HOSTS,
    cors_allowed_origins,
    trusted_hosts,
)
from .no_cache import NoCacheMiddleware
from .origin_check import OriginCheckMiddleware
from .rate_limit import RateLimitMiddleware
from .security_headers import (  # noqa: F401
    _ARTIST_ARTWORK_IMG_HOSTS,
    SecurityHeadersMiddleware,
)

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
    6. RateLimitMiddleware - rate limiting for expensive endpoints (#2575), innermost

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
    # OriginCheck → TrustedHost → RateLimit → app; a 403/429/400 bubbles back
    # up through SecurityHeaders/NoCache.

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

    # Origin validation for state-changing REST requests (#4893) — wraps
    # TrustedHost (so the Host header is already known-good) and RateLimit
    # (so a rejected CSRF-shaped request never consumes rate budget), wrapped
    # by SecurityHeaders so its 403 still carries the documented headers.
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
        allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "X-Session-Id"],
    )

    logger.debug(
        "✅ Middleware configured: TrustedHostMiddleware, RateLimitMiddleware, "
        "OriginCheckMiddleware, NoCacheMiddleware, SecurityHeadersMiddleware, CORSMiddleware"
    )
