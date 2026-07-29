"""
Middleware Configuration

Sets up middleware for the FastAPI application including CORS, caching,
and security headers.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import logging
import sys
import time
from typing import Any, cast
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


def _middleware_error_response(exc: Exception, where: str) -> JSONResponse:
    """Uniform JSON 500 for an exception raised inside a middleware dispatch.

    ``BaseHTTPMiddleware.dispatch`` runs outside FastAPI's ExceptionMiddleware,
    so ``@app.exception_handler(Exception)`` does not cover it — a raise here
    would otherwise reach Starlette's ``ServerErrorMiddleware`` and return a
    plaintext ``Internal Server Error`` without the ``{"detail": ...}`` shape the
    frontend expects (#4378).
    """
    logger.error(f"Unhandled exception in {where}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


class NoCacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware to disable caching for frontend static files.

    Only applies to frontend assets (.html, .js, .css), not API responses.
    API streaming responses must NOT have cache-control headers modified.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        try:
            response = await call_next(request)

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


# Image hosts that artist artwork is served from (#4526).
#
# Unlike album and track artwork — which `to_dict()` rewrites to a same-origin
# `/api/.../artwork` path — `Artist.artwork_url` deliberately stores the raw
# external CDN URL and the frontend renders it directly as an `<img src>`. Under
# `img-src 'self' data: blob:` the browser blocked every one of them, so the
# artist detail page showed the no-artwork fallback for every artist that
# actually had artwork. This is invisible in `--dev` (Vite serves the document
# from :3000, so this middleware's CSP does not apply to it) and always broken
# in the shipped Electron build, where the backend serves the SPA itself.
#
# These are the hosts the three fetchers in `auralis/services/artwork_service.py`
# actually produce:
#   - Last.fm  (`_fetch_from_lastfm`)     -> lastfm.freetls.fastly.net, and the
#                                            older akamaized.net CDN
#   - Discogs  (`_fetch_from_discogs`)    -> i/img.discogs.com
#   - MusicBrainz (`_fetch_from_musicbrainz`) -> whatever host an editor put in
#                                            the artist's `image` URL relation,
#                                            in practice Wikimedia Commons
#
# KNOWN LIMITATION: the MusicBrainz case is open-ended by construction — the
# relation resource is arbitrary editor-supplied data, so an artist whose image
# relation points somewhere not listed here will still be blocked and fall back
# to the placeholder. Enumerating hosts trades a total outage for a partial one;
# it is not a complete fix. Closing that gap properly means serving artist
# artwork from our own origin like albums do (see #4526 for the alternatives).
# Do NOT "fix" a missing image by relaxing this to `https:` — that would allow
# every HTTPS image on the internet and give up the directive entirely.
_ARTIST_ARTWORK_IMG_HOSTS = (
    "https://lastfm.freetls.fastly.net",
    "https://*.lastfm.freetls.fastly.net",
    "https://lastfm-img2.akamaized.net",
    "https://i.discogs.com",
    "https://img.discogs.com",
    "https://upload.wikimedia.org",
    "https://commons.wikimedia.org",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add browser security headers to all responses.

    Sets standard headers to prevent clickjacking, MIME-type sniffing,
    and other common browser-based attacks.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        try:
            response = await call_next(request)

            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            img_src = " ".join(("'self'", "data:", "blob:", *_ARTIST_ARTWORK_IMG_HOSTS))
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                f"img-src {img_src}; "
                "connect-src 'self' ws://localhost:* http://localhost:*; "
                "media-src 'self' blob:;"
            )

            return cast(Response, response)
        except Exception as exc:
            return _middleware_error_response(exc, "SecurityHeadersMiddleware")


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

    # Evict stale keys every 256 rate-limited requests to bound memory (#2630).
    _EVICTION_INTERVAL = 256

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        # {client_key: [timestamp, ...]}
        self._windows: dict[str, list[float]] = {}
        self._request_count = 0
        # Serialize the get → prune → check → write critical section so the
        # rate limit is exact even if a future refactor introduces an await
        # inside the block (#3329). Single-threaded asyncio makes the lock
        # nearly free under normal conditions.
        self._lock: asyncio.Lock = asyncio.Lock()

    def _evict_stale_keys(self, now: float) -> None:
        """Remove dict entries whose timestamps have all expired."""
        # Find the longest window across all rules for a conservative cutoff
        max_window = max(w for _, w in self._RATE_LIMITS.values())
        stale_keys = [
            k for k, ts in self._windows.items()
            if not ts or now - ts[-1] >= max_window
        ]
        for k in stale_keys:
            del self._windows[k]

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        try:
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

            # Critical section (#3329): eviction + sliding-window get/check/write
            # must be atomic with respect to other concurrent dispatches.
            async with self._lock:
                # Periodic eviction of stale keys to prevent unbounded growth (#2630)
                self._request_count += 1
                if self._request_count >= self._EVICTION_INTERVAL:
                    self._request_count = 0
                    self._evict_stale_keys(now)

                # Prune expired entries and check limit
                timestamps = self._windows.get(key, [])
                timestamps = [t for t in timestamps if now - t < window_sec]

                if not timestamps:
                    self._windows.pop(key, None)

                if len(timestamps) >= max_requests:
                    self._windows[key] = timestamps
                    retry_after = int(window_sec - (now - timestamps[0])) + 1
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many requests"},
                        headers={"Retry-After": str(retry_after)},
                    )

                timestamps.append(now)
                self._windows[key] = timestamps

            return await call_next(request)
        except Exception as exc:
            return _middleware_error_response(exc, "RateLimitMiddleware")


def cors_allowed_origins() -> list[str]:
    """Build the CORS allow-origins list.

    Both `localhost` and `127.0.0.1` are emitted for every port — browsers treat
    them as distinct origins, so a dev opening the app via the IP form on an alt
    port (e.g. 127.0.0.1:3001) would otherwise be blocked by CORS preflight
    (#3539 / BE-NEW-81). The Vite dev ports (3000-3006) are only legitimate in
    dev; a packaged build never serves the frontend from them, so they are
    included only when is_dev_mode() (#4350). Port 8765 (the backend itself) is
    always allowed. Shares the dev-gating contract with globals.ALLOWED_WS_ORIGINS.

    Both http and https are emitted (#3897). A dev running Vite behind a TLS
    cert — needed for secure-context features like service workers — has a page
    origin of `https://localhost:3000`, which this list would otherwise reject
    at CORS preflight. globals.build_ws_origins() already covers the https/wss
    schemes; this list was the remaining half of that gap.

    Only http/https appear here, not ws/wss: an Origin header for an HTTP
    request always carries the *page* scheme, so a `ws://` entry could never
    match a CORS preflight.
    """
    from .app import is_dev_mode
    dev_ports = list(range(3000, 3007)) if is_dev_mode() else []
    all_ports = dev_ports + [8765]
    return [
        f"{scheme}://{host}:{port}"
        for scheme in ("http", "https")
        for host in ("localhost", "127.0.0.1")
        for port in all_ports
    ]


# Hosts a browser can legitimately put in the Host header for this backend.
#
# Starlette's TrustedHostMiddleware strips the port before matching
# (`headers.get("host", "").split(":")[0]`), so these are bare hostnames. The
# issue proposed entries like "localhost:8765" — those could never match, since
# the port is gone by the time the comparison happens.
#
# No "[::1]": the same split(":") leaves "[" for an IPv6 literal, so a bracketed
# address cannot be matched at all. It does not need to be — main.py binds
# 127.0.0.1, so the v6 loopback never reaches this process.
_TRUSTED_HOSTS: tuple[str, ...] = ("localhost", "127.0.0.1")

# Starlette's TestClient sends `Host: testserver` by default, and several
# suites drive the ASGI app through httpx with base_url="http://test". Neither
# is resolvable as a public domain (both are single-label, so a browser cannot
# be induced to send them for a rebound address), but they are still test
# scaffolding and are kept out of the shipped allowlist.
_TEST_HOSTS: tuple[str, ...] = ("testserver", "test")


def trusted_hosts(include_test_hosts: bool | None = None) -> list[str]:
    """Build the allowed Host header values (#4353).

    DNS-rebinding defence in depth: a page on attacker.com rebound to 127.0.0.1
    reaches this backend with `Host: attacker.com`. Validating the header
    rejects it before any handler runs.

    Args:
        include_test_hosts: Force the test hosts in or out. Defaults to
            autodetecting pytest, so production never carries them; passing
            False is how the test suite asserts that.
    """
    if include_test_hosts is None:
        include_test_hosts = "pytest" in sys.modules
    hosts = list(_TRUSTED_HOSTS)
    if include_test_hosts:
        hosts.extend(_TEST_HOSTS)
    return hosts


def setup_middleware(app: FastAPI) -> None:
    """
    Add middleware to FastAPI application.

    Configures middleware in the correct order:
    1. NoCacheMiddleware - for frontend assets
    2. CORSMiddleware - for cross-origin requests

    Args:
        app: FastAPI application instance (modified in-place)
    """
    # Starlette runs middleware in REVERSE add order, so the last-added wraps
    # outermost. Register RateLimit FIRST (innermost) so SecurityHeaders and
    # NoCache wrap it — otherwise a rate-limit 429 short-circuits before those
    # run and is returned without the documented security headers (#3843).
    #
    # Resulting request-inbound order: CORS → SecurityHeaders → NoCache →
    # TrustedHost → RateLimit → app; a 429 or an invalid-host 400 bubbles back
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
        "NoCacheMiddleware, SecurityHeadersMiddleware, CORSMiddleware"
    )
