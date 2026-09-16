"""
Security Headers Middleware

Browser security headers and the CSP on every response. Split out of
config/middleware.py (#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any, cast

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..origins import csp_connect_src
from .error_response import _middleware_error_response

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
        # as NoCacheMiddleware's — see its dispatch() comment in no_cache.py (#4808).
        response = await call_next(request)

        try:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            img_src = " ".join(("'self'", "data:", "blob:", *_ARTIST_ARTWORK_IMG_HOSTS))
            # `'unsafe-inline'` on both directives is intentional, not an
            # oversight (#3900) -- each was investigated for a hash/nonce
            # replacement and rejected for a concrete, checkable reason:
            #
            # script-src: the built frontend (auralis-web/frontend/dist/,
            # served by main.py's StaticFiles(html=True) mount) ships one
            # fixed inline `<script type="module">` bootstrap block in
            # index.html. Its exact bytes change on every Vite build (the
            # embedded chunk filenames carry a content hash), so a CSP
            # `'sha256-...'` allowance would have to be computed from the
            # live index.html at startup and kept byte-for-byte in sync with
            # whatever the browser's HTML parser feeds its SHA-256 -- a
            # mismatch fails silently at the CSP layer and blocks the app's
            # entire boot (a blank white screen) for every user, which this
            # environment has no Playwright/browser-driven test to verify
            # against before shipping. Worse-than-the-gap-it-closes risk for
            # a LOW-severity, Electron-only (no remote content) finding.
            # TODO(#5484): revisit if Vite's own CSP/nonce plugin support
            # (or a real browser-driven frontend test suite) lands.
            #
            # style-src: React/MUI here render styling as inline `style="..."`
            # element attributes (sx props, emotion CSS-in-JS), not `<style>`
            # tags -- and per the CSP spec, `'nonce-...'`/`'sha256-...'` only
            # ever allowlist `<script>`/`<style>` elements, never the `style=`
            # *attribute*. There is no nonce/hash mechanism that covers this
            # case at all; removing 'unsafe-inline' here would require
            # rewriting the inline-style usage sitewide to class-based
            # styling, out of scope for a backend CSP header fix.
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
                # default-src is not a fallback for either of these (#5363).
                # Without them an injected <form action> could post off-origin
                # and an injected <base href> would re-point every relative URL.
                "form-action 'self'; "
                "base-uri 'self'; "
                "media-src 'self' blob:;"
            )

            return cast(Response, response)
        except Exception as exc:
            return _middleware_error_response(exc, "SecurityHeadersMiddleware")
