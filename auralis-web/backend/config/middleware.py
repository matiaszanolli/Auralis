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
from collections import OrderedDict
from typing import Any, cast
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .origins import LOOPBACK_ORIGIN_HOSTS, csp_connect_src, origin_matrix

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
        # call_next(request) sits outside the try below for the same reason
        # as NoCacheMiddleware's — see its dispatch() comment (#4808).
        response = await call_next(request)

        try:
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
                # Derived from config/origins.py so it cannot drift from the
                # CORS and WebSocket allowlists again (#4712) — it listed only
                # `localhost`, blocking the WS for a page opened via 127.0.0.1.
                f"connect-src {csp_connect_src()}; "
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

    # Evict stale keys every 256 rate-limited requests (#2630). This bounds
    # growth BETWEEN windows — once every timestamp for a key is older than
    # max_window, the sweep removes it. It does NOT bound growth WITHIN a
    # single window: a burst of many distinct client_ip:path keys inside one
    # 60s window (e.g. every track ID touched across a large library) is not
    # caught by this sweep no matter how often it runs, since each such
    # entry's newest timestamp is still fresh (#4804). The hard cap below is
    # what actually bounds that case; keying on path prefix instead of the
    # full path (#4728) would remove the growth path entirely by collapsing
    # the key space to clients × rule count.
    _EVICTION_INTERVAL = 256

    # Hard cap on live entries, independent of the between-window sweep above
    # (#4804). Evicted LRU-style (least-recently-touched first, via
    # OrderedDict.move_to_end() on every hit) so active clients are never
    # evicted ahead of quiet ones. ~10k entries is a generous margin above
    # normal traffic shapes while still bounding worst-case memory (roughly
    # 2 MB at the ~200 B/entry estimate from #4804's own impact analysis).
    _MAX_WINDOW_ENTRIES = 10_000

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        # {client_key: [timestamp, ...]} — OrderedDict (not plain dict) so
        # move_to_end() can track recency for the hard-cap LRU eviction below.
        self._windows: OrderedDict[str, list[float]] = OrderedDict()
        self._request_count = 0
        # Serialize the get → prune → check → write critical section so the
        # rate limit is exact even if a future refactor introduces an await
        # inside the block (#3329). Single-threaded asyncio makes the lock
        # nearly free under normal conditions.
        self._lock: asyncio.Lock = asyncio.Lock()

    def _evict_stale_keys(self, now: float) -> None:
        """Remove dict entries whose timestamps have all expired, then
        enforce the hard cap (#4804) — see _MAX_WINDOW_ENTRIES and the
        _EVICTION_INTERVAL comment above for why both are needed."""
        # Find the longest window across all rules for a conservative cutoff
        max_window = max(w for _, w in self._RATE_LIMITS.values())
        stale_keys = [
            k for k, ts in self._windows.items()
            if not ts or now - ts[-1] >= max_window
        ]
        for k in stale_keys:
            del self._windows[k]

        # Hard cap: bounds within-window growth the staleness sweep above
        # cannot catch. popitem(last=False) drops the oldest (least-recently-
        # touched) entry — dispatch() calls move_to_end() on every hit, so
        # this is true LRU, not merely insertion order.
        while len(self._windows) > self._MAX_WINDOW_ENTRIES:
            self._windows.popitem(last=False)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # The try below covers ONLY this middleware's own rate-limit
        # bookkeeping — matching a rule, the sliding-window lock/dict
        # manipulation, and the 429 it may return. call_next(request) is
        # called exactly once, OUTSIDE the try, at the bottom of this method
        # (#4808): BaseHTTPMiddleware.call_next re-raises a downstream route
        # handler's exception at its call site, so wrapping it here caught
        # every unhandled route exception and misattributed it as
        # "Unhandled exception in RateLimitMiddleware" instead of letting it
        # reach config/app.py's registered `@app.exception_handler(Exception)`.
        # This used to be two call sites (an early-return fast path plus the
        # final one); collapsing to one after the bookkeeping block achieves
        # the same fast-path behavior (nothing below runs when no rule
        # matches) without needing call_next inside the guarded section.
        try:
            path = request.url.path

            # Find matching rate-limit rule
            limit_rule: tuple[int, int] | None = None
            matched_prefix: str | None = None
            for prefix, rule in self._RATE_LIMITS.items():
                if path.startswith(prefix):
                    limit_rule = rule
                    matched_prefix = prefix
                    break

            if limit_rule is not None and matched_prefix is not None:
                max_requests, window_sec = limit_rule
                client_ip = request.client.host if request.client else "unknown"
                # Key on the matched prefix, not the full path (#4728). Every
                # rate-limited prefix except two fixed paths fans out over a path
                # parameter (track_id, job_id, ...) — keying on the full path gave
                # each distinct resource its own fresh, effectively-unlimited
                # budget instead of the shared one the docstring promises.
                key = f"{client_ip}:{matched_prefix}"
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
                        # Recency touch for the hard-cap LRU eviction (#4804) —
                        # a client still being rate-limited is by definition
                        # active and must not be evicted ahead of quiet keys.
                        self._windows.move_to_end(key)
                        retry_after = int(window_sec - (now - timestamps[0])) + 1
                        return JSONResponse(
                            status_code=429,
                            content={"detail": "Too many requests"},
                            headers={"Retry-After": str(retry_after)},
                        )

                    timestamps.append(now)
                    self._windows[key] = timestamps
                    self._windows.move_to_end(key)  # recency touch (#4804)
        except Exception as exc:
            return _middleware_error_response(exc, "RateLimitMiddleware")

        return await call_next(request)


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
    """

    _STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # The try below covers ONLY this middleware's own origin check.
        # call_next(request) is called exactly once, OUTSIDE the try, at the
        # bottom of this method — same reasoning as RateLimitMiddleware's
        # dispatch() comment (#4808).
        try:
            if request.method in self._STATE_CHANGING_METHODS and request.url.path.startswith("/api"):
                from .globals import LOOPBACK_HOSTS

                origin = request.headers.get("origin", "").lower()
                if origin:
                    # Non-empty Origin: must be in the same allowlist CORS uses.
                    if origin not in cors_allowed_origins():
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

        return await call_next(request)


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

    The host x port matrix itself lives in config/origins.py — shared with
    build_ws_origins() and the CSP connect-src directive so the three cannot
    drift apart again (#4712).
    """
    return origin_matrix(("http", "https"))


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
#
# Sourced from config/origins.py rather than re-spelled here: this was the
# fourth independent copy of the same both-spellings host policy, alongside
# CORS, the WS allowlist and the CSP (#4712 / #3539). A new loopback spelling
# must be trusted in the Host header for the same reason it must be allowed as
# an origin, so the coupling is intended.
_TRUSTED_HOSTS: tuple[str, ...] = LOOPBACK_ORIGIN_HOSTS

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
