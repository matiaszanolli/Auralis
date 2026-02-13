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
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


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

        logger.warning(f"No artwork found for artist: {artist_name}")
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
                data = json.loads(response.read().decode('utf-8'))

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
                relations_data = json.loads(response.read().decode('utf-8'))

            # Look for image URLs in relations
            relations = relations_data.get('relations', [])
            for relation in relations:
                if relation.get('type') == 'image':
                    url_data = relation.get('url', {})
                    image_url = url_data.get('resource')
                    if image_url:
                        return {
                            'artwork_url': image_url,
                            'source': 'musicbrainz'
                        }

            return None

        except Exception as e:
            logger.debug(f"MusicBrainz fetch failed for {artist_name}: {e}")
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

            # Search for artist
            search_url = (
                f"https://api.discogs.com/database/search"
                f"?q={encoded_name}&type=artist&token={self.discogs_token}"
            )

            req = urllib.request.Request(search_url)
            req.add_header('User-Agent', self.user_agent)

            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))

            results = data.get('results', [])
            if not results:
                return None

            # Get first result's image
            artist = results[0]
            image_url = artist.get('cover_image') or artist.get('thumb')

            if image_url:
                return {
                    'artwork_url': image_url,
                    'source': 'discogs'
                }

            return None

        except Exception as e:
            logger.debug(f"Discogs fetch failed for {artist_name}: {e}")
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
                data = json.loads(response.read().decode('utf-8'))

            artist = data.get('artist', {})
            images = artist.get('image', [])

            # Get largest image
            for img in reversed(images):  # Reverse to get largest first
                url = img.get('#text')
                if url:
                    return {
                        'artwork_url': url,
                        'source': 'lastfm'
                    }

            return None

        except Exception as e:
            logger.debug(f"Last.fm fetch failed for {artist_name}: {e}")
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
        """
        # For now, just log that this is not implemented
        # Can be added later following the same pattern as artist artwork
        logger.info(f"Album artwork fetching not yet implemented for: {album_title}")
        return None
