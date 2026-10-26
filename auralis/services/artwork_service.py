"""
Artwork Service
~~~~~~~~~~~~~~~

Service for fetching artist and album artwork from external sources.

Supported sources (in priority order):
1. MusicBrainz Cover Art Archive (free, no API key)
2. Discogs API (requires API key/token)
3. Last.fm API (requires API key)

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from auralis.utils.artwork_security import validate_artwork_url
from auralis.utils.logging import sanitize_log_value

logger = logging.getLogger(__name__)


class _TrustedArtworkRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse a redirect to an untrusted host before requesting it (#5330).

    ``urlopen`` follows redirects on its own, so validating ``geturl()``
    afterwards only saw the last hop: a loopback or LAN hop in the middle of
    the chain had already been sent a real GET by then.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not validate_artwork_url(newurl):
            logger.warning("Rejecting untrusted artwork redirect: %r", newurl)
            raise urllib.error.HTTPError(
                newurl, code, "Untrusted artwork redirect", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# Opener for requests to image hosts, whose redirects are followed.
# Metadata API calls still use plain urlopen.
_artwork_opener = urllib.request.build_opener(_TrustedArtworkRedirectHandler)


from .artwork_sources.discogs import fetch_from_discogs
from .artwork_sources.lastfm import fetch_from_lastfm
from .artwork_sources.musicbrainz import fetch_from_musicbrainz

class ArtworkService:
    """
    Service for fetching artist and album artwork from external sources.

    Uses a multi-source fallback strategy:
    1. MusicBrainz (free, open data)
    2. Discogs (requires token)
    3. Last.fm (requires API key)
    """

    def __init__(
        self,
        discogs_token: str | None = None,
        lastfm_api_key: str | None = None,
        timeout: int = 10
    ):
        """
        Initialize artwork service with optional API credentials.

        Args:
            discogs_token: Discogs user token (optional)
            lastfm_api_key: Last.fm API key (optional)
            timeout: HTTP request timeout in seconds
        """
        self.discogs_token = discogs_token
        self.lastfm_api_key = lastfm_api_key
        self.timeout = timeout

        # User agent for API requests (required by MusicBrainz)
        self.user_agent = "Auralis/1.2.0 (https://github.com/matiaszanolli/Auralis)"

    def fetch_artist_artwork(self, artist_name: str) -> dict[str, Any] | None:
        """
        Fetch artist artwork from available sources.

        Tries sources in priority order:
        1. MusicBrainz
        2. Discogs (if token available)
        3. Last.fm (if API key available)

        Args:
            artist_name: Artist name to search for

        Returns:
            Dictionary with artwork_url and source, or None if not found
            Example: {'artwork_url': 'https://...', 'source': 'musicbrainz'}
        """
        # Try MusicBrainz first (always available)
        result = self._fetch_from_musicbrainz(artist_name)
        if result:
            return result

        # Try Discogs if token available
        if self.discogs_token:
            result = self._fetch_from_discogs(artist_name)
            if result:
                return result

        # Try Last.fm if API key available
        if self.lastfm_api_key:
            result = self._fetch_from_lastfm(artist_name)
            if result:
                return result

        logger.warning(f"No artwork found for artist: {sanitize_log_value(artist_name)}")
        return None

    def _fetch_from_musicbrainz(self, artist_name: str) -> dict[str, Any] | None:
        return fetch_from_musicbrainz(self, artist_name)

    def _fetch_from_discogs(self, artist_name: str) -> dict[str, Any] | None:
        return fetch_from_discogs(self, artist_name)

    def _fetch_from_lastfm(self, artist_name: str) -> dict[str, Any] | None:
        return fetch_from_lastfm(self, artist_name)

