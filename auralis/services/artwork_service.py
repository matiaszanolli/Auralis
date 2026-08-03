"""
Artwork Service
~~~~~~~~~~~~~~~

Service for fetching artist and album artwork from external sources.

Supported sources (in priority order):
1. MusicBrainz Cover Art Archive (free, no API key)
2. Discogs API (requires API key/token)
3. Last.fm API (requires API key)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
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
from auralis.utils.logging import sanitize_log_value

logger = logging.getLogger(__name__)


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
        """
        Fetch artist artwork from MusicBrainz.

        Steps:
        1. Search for artist by name to get MBID
        2. Get artist relations to find image URLs
        3. Return highest quality image

        Args:
            artist_name: Artist name to search

        Returns:
            Dict with artwork_url and source, or None
        """
        try:
            # URL-encode artist name
            encoded_name = urllib.parse.quote(artist_name)

            # Search for artist
            search_url = (
                f"https://musicbrainz.org/ws/2/artist/"
                f"?query=artist:{encoded_name}&fmt=json&limit=1"
            )

            req = urllib.request.Request(search_url)
            req.add_header('User-Agent', self.user_agent)

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = _read_json_response(response)

            if not data.get('artists') or len(data['artists']) == 0:
                return None

            artist = data['artists'][0]
            mbid = artist.get('id')

            if not mbid:
                return None

            # Get artist relations to find images
            relations_url = (
                f"https://musicbrainz.org/ws/2/artist/{mbid}"
                f"?inc=url-rels&fmt=json"
            )

            req = urllib.request.Request(relations_url)
            req.add_header('User-Agent', self.user_agent)

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                relations_data = _read_json_response(response)

            # Look for image URLs in relations
            relations = relations_data.get('relations', [])
            for relation in relations:
                if relation.get('type') == 'image':
                    url_data = relation.get('url', {})
                    image_url = url_data.get('resource')
                    if image_url:
                        result = _validated_artwork_result(image_url, "musicbrainz")
                        if result:
                            return result

            return None

        except Exception as e:
            logger.debug(f"MusicBrainz fetch failed for {sanitize_log_value(artist_name)}: {e}")
            return None

    def _fetch_from_discogs(self, artist_name: str) -> dict[str, Any] | None:
        """
        Fetch artist artwork from Discogs API.

        Requires self.discogs_token to be set.

        Args:
            artist_name: Artist name to search

        Returns:
            Dict with artwork_url and source, or None
        """
        if not self.discogs_token:
            return None

        try:
            # URL-encode artist name
            encoded_name = urllib.parse.quote(artist_name)

            # Search for artist — token sent as Authorization header, not URL param (fixes #2244)
            search_url = (
                f"https://api.discogs.com/database/search"
                f"?q={encoded_name}&type=artist"
            )

            req = urllib.request.Request(search_url)
            req.add_header('Authorization', f'Discogs token={self.discogs_token}')
            req.add_header('User-Agent', self.user_agent)

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = _read_json_response(response)

            results = data.get('results', [])
            if not results:
                return None

            # Get first result's image
            artist = results[0]
            image_url = artist.get('cover_image') or artist.get('thumb')

            if image_url:
                return _validated_artwork_result(image_url, "discogs")

            return None

        except Exception as e:
            logger.debug(f"Discogs fetch failed for {sanitize_log_value(artist_name)}: {e}")
            return None

    def _fetch_from_lastfm(self, artist_name: str) -> dict[str, Any] | None:
        """
        Fetch artist artwork from Last.fm API.

        Requires self.lastfm_api_key to be set.

        Args:
            artist_name: Artist name to search

        Returns:
            Dict with artwork_url and source, or None
        """
        if not self.lastfm_api_key:
            return None

        try:
            # URL-encode artist name
            encoded_name = urllib.parse.quote(artist_name)

            # Get artist info
            info_url = (
                f"https://ws.audioscrobbler.com/2.0/"
                f"?method=artist.getinfo&artist={encoded_name}"
                f"&api_key={self.lastfm_api_key}&format=json"
            )

            req = urllib.request.Request(info_url)
            req.add_header('User-Agent', self.user_agent)

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = _read_json_response(response)

            artist = data.get('artist', {})
            images = artist.get('image', [])

            # Get largest image
            for img in reversed(images):  # Reverse to get largest first
                url = img.get('#text')
                if url:
                    result = _validated_artwork_result(url, "lastfm")
                    if result:
                        return result

            return None

        except Exception as e:
            logger.debug(f"Last.fm fetch failed for {sanitize_log_value(artist_name)}: {e}")
            return None

    def fetch_album_artwork(
        self,
        album_title: str,
        artist_name: str | None = None
    ) -> dict[str, Any] | None:
        """
        Fetch album artwork from available sources.

        Args:
            album_title: Album title to search for
            artist_name: Artist name for better search accuracy (optional)

        Returns:
            Dictionary with artwork_url and source, or None if not found
            Example: {'artwork_url': 'https://...', 'source': 'coverartarchive'}
        """
        # MusicBrainz release-group search + Cover Art Archive (always available,
        # no API key) — mirrors fetch_artist_artwork's source pattern (#4037).
        result = self._fetch_album_from_musicbrainz(album_title, artist_name)
        if result:
            return result

        logger.warning(f"No artwork found for album: {sanitize_log_value(album_title)}")
        return None

    def _fetch_album_from_musicbrainz(
        self,
        album_title: str,
        artist_name: str | None = None
    ) -> dict[str, Any] | None:
        """
        Fetch album artwork via MusicBrainz release-group + Cover Art Archive.

        Steps:
        1. Search release-groups by album title (and artist if given) -> MBID.
        2. Resolve the front cover via coverartarchive.org/release-group/{mbid}/front,
           following the redirect to the actual image (404 -> no cover).

        Returns:
            Dict with artwork_url and source, or None
        """
        try:
            query = f'releasegroup:"{album_title}"'
            if artist_name:
                query += f' AND artist:"{artist_name}"'
            encoded_query = urllib.parse.quote(query)

            search_url = (
                f"https://musicbrainz.org/ws/2/release-group/"
                f"?query={encoded_query}&fmt=json&limit=1"
            )
            req = urllib.request.Request(search_url)
            req.add_header('User-Agent', self.user_agent)

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = _read_json_response(response)

            groups = data.get('release-groups', [])
            if not groups:
                return None

            mbid = groups[0].get('id')
            if not mbid:
                return None

            # Cover Art Archive redirects /front to the actual image (404 if none).
            cover_url = f"https://coverartarchive.org/release-group/{mbid}/front"
            caa_req = urllib.request.Request(cover_url)
            caa_req.add_header('User-Agent', self.user_agent)

            try:
                with urllib.request.urlopen(caa_req, timeout=self.timeout) as caa_response:
                    resolved_url = caa_response.geturl()
            except urllib.error.HTTPError as http_err:
                if http_err.code == 404:
                    return None  # release-group has no front cover
                raise

            return _validated_artwork_result(resolved_url, "coverartarchive")

        except Exception as e:
            logger.debug(f"MusicBrainz/CAA album fetch failed for {sanitize_log_value(album_title)}: {e}")
            return None
