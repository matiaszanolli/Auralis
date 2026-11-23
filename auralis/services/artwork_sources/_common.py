"""
Shared helpers for the artwork metadata providers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The one request path, bounded JSON decoding and trusted-URL validation used by
the MusicBrainz, Discogs and Last.fm fetchers (split from ``artwork_service``
with them, #6273). Every metadata request goes through ``fetch_metadata_json``:
spaced per host (#6548) and never redirected (#6546).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from auralis.utils.artwork_security import (
    MAX_ARTWORK_PAYLOAD_BYTES,
    validate_artwork_url,
)
from auralis.utils.host_throttle import MUSICBRAINZ_MIN_INTERVAL_S, HostThrottle

logger = logging.getLogger(__name__)

# A CLI run walks the whole library: without spacing it sent requests at network speed, and
# MusicBrainz blocks the User-Agent every Auralis install shares (#6548). Discogs allows 60
# authenticated requests a minute; Last.fm asks for well under five a second.
_THROTTLE = HostThrottle({
    "musicbrainz.org": MUSICBRAINZ_MIN_INTERVAL_S,
    "api.discogs.com": 1.0,
    "ws.audioscrobbler.com": 0.25,
})
_DEFAULT_BACKOFF_S = 10.0
_MAX_BACKOFF_S = 120.0


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """The providers' JSON APIs never need a redirect; following one sent a GET wherever a
    compromised or intercepted provider pointed, loopback and LAN included (#6546)."""

    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        logger.warning("Refusing a %d redirect from %s to %r", code, urllib.parse.urlsplit(req.full_url).hostname, newurl)
        return None  # urllib then raises the 3xx as an HTTPError


_OPENER = urllib.request.build_opener(_RefuseRedirects)


def _backoff_seconds(headers: Any) -> float:
    """A numeric Retry-After, capped; the default when absent or an HTTP date."""
    try:
        return min(max(float(headers.get("Retry-After")), 0.0), _MAX_BACKOFF_S)
    except (AttributeError, TypeError, ValueError):
        return _DEFAULT_BACKOFF_S


def fetch_metadata_json(req: urllib.request.Request, timeout: float) -> Any:
    """Send one provider metadata request and decode its bounded JSON body.

    Waits for the host's next request slot, refuses redirects, and on 429/503 pushes the
    host's next slot out (Retry-After, else a default) and logs a WARNING: those used to be
    swallowed at DEBUG, so a rate-limited run silently reported every later artist missing.
    """
    host = urllib.parse.urlsplit(req.full_url).hostname or ""
    _THROTTLE.wait_blocking(host)
    try:
        with _OPENER.open(req, timeout=timeout) as response:
            return _read_json_response(response)
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            delay = _backoff_seconds(e.headers)
            _THROTTLE.back_off(host, delay)
            logger.warning("%s answered %d; pausing requests to it for %.0fs", host, e.code, delay)
        raise


def _read_json_response(response: Any) -> Any:
    """Decode a bounded JSON response from an artwork metadata provider."""
    payload = response.read(MAX_ARTWORK_PAYLOAD_BYTES + 1)
    if len(payload) > MAX_ARTWORK_PAYLOAD_BYTES:
        raise ValueError(
            f"Artwork metadata response exceeded {MAX_ARTWORK_PAYLOAD_BYTES} bytes"
        )
    return json.loads(payload.decode("utf-8"))


def _validated_artwork_result(
    artwork_url: str,
    source: str,
) -> dict[str, str] | None:
    """Build an artwork result only when its external URL is trusted."""
    if not validate_artwork_url(artwork_url):
        logger.warning("Rejecting untrusted %s artwork URL: %r", source, artwork_url)
        return None
    return {"artwork_url": artwork_url, "source": source}
