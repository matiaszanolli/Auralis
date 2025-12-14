"""
Artwork Downloader Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Automatically fetches album artwork from online sources.

Features:
- MusicBrainz Cover Art Archive (primary)
- iTunes Search API (fallback)
- Last.fm API (fallback)
- Image caching and optimization

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
import aiohttp
import asyncio
from pathlib import Path
from typing import Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)


class ArtworkDownloader:
    """
    Service for downloading album artwork from online sources.

    Uses multiple sources with fallback:
    1. MusicBrainz Cover Art Archive (open source, no API key needed)
    2. iTunes Search API (free, no API key needed)
    3. Last.fm API (requires API key)
    """

    def __init__(self, cache_dir: str = "~/.auralis/artwork_cache"):
        """
        Initialize artwork downloader.

        Args:
            cache_dir: Directory to cache downloaded artwork
        """
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # API endpoints
        self.musicbrainz_api = "https://musicbrainz.org/ws/2"
        self.coverart_api = "https://coverartarchive.org"
        self.itunes_api = "https://itunes.apple.com/search"

    async def download_artwork(
        self,
        artist: str,
        album: str,
        album_id: int
    ) -> Optional[str]:
        """
        Download artwork for an album from online sources.

        Args:
            artist: Artist name
            album: Album name
            album_id: Album ID (for unique cache naming)

        Returns:
            str: Path to downloaded artwork file, or None if not found
        """
        try:
            # Try MusicBrainz first (best quality, open source)
            artwork_path = await self._try_musicbrainz(artist, album, album_id)
            if artwork_path:
                logger.info(f"Downloaded artwork from MusicBrainz for '{album}' by '{artist}'")
                return artwork_path

            # Fallback to iTunes
            artwork_path = await self._try_itunes(artist, album, album_id)
            if artwork_path:
                logger.info(f"Downloaded artwork from iTunes for '{album}' by '{artist}'")
                return artwork_path

            logger.warning(f"No artwork found for '{album}' by '{artist}'")
            return None

        except Exception as e:
            logger.error(f"Failed to download artwork: {e}")
            return None

    async def _try_musicbrainz(
        self,
        artist: str,
        album: str,
        album_id: int
    ) -> Optional[str]:
        """
        Try to download artwork from MusicBrainz Cover Art Archive.

        Args:
            artist: Artist name
            album: Album name
            album_id: Album ID

        Returns:
            str: Path to downloaded artwork, or None if not found
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Search for release
                search_url = f"{self.musicbrainz_api}/release/"
                params = {
                    "query": f'artist:"{artist}" AND release:"{album}"',
                    "fmt": "json",
                    "limit": 1
                }
                headers = {
                    "User-Agent": "Auralis/1.0 (https://github.com/matiaszanolli/Auralis)"
                }

                async with session.get(search_url, params=params, headers=headers) as resp:  # type: ignore[arg-type]
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    releases = data.get("releases", [])

                    if not releases:
                        return None

                    release_id = releases[0]["id"]

                # Get cover art
                coverart_url = f"{self.coverart_api}/release/{release_id}/front"

                async with session.get(coverart_url, headers=headers) as resp:
                    if resp.status != 200:
                        return None

                    # Save artwork
                    artwork_data = await resp.read()
                    return self._save_artwork(artwork_data, album_id, "jpg")

        except Exception as e:
            logger.debug(f"MusicBrainz lookup failed: {e}")
            return None

    async def _try_itunes(
        self,
        artist: str,
        album: str,
        album_id: int
    ) -> Optional[str]:
        """
        Try to download artwork from iTunes Search API.

        Args:
            artist: Artist name
            album: Album name
            album_id: Album ID

        Returns:
            str: Path to downloaded artwork, or None if not found
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Search iTunes
                params = {
                    "term": f"{artist} {album}",
                    "media": "music",
                    "entity": "album",
                    "limit": 1
                }

                async with session.get(self.itunes_api, params=params) as resp:  # type: ignore[arg-type]
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    results = data.get("results", [])

                    if not results:
                        return None

                    # Get high-res artwork URL (replace 100x100 with larger size)
                    artwork_url = results[0].get("artworkUrl100", "")
                    if not artwork_url:
                        return None

                    # Request larger artwork (600x600)
                    artwork_url = artwork_url.replace("100x100", "600x600")

                # Download artwork
                async with session.get(artwork_url) as resp:
                    if resp.status != 200:
                        return None

                    artwork_data = await resp.read()
                    return self._save_artwork(artwork_data, album_id, "jpg")

        except Exception as e:
            logger.debug(f"iTunes lookup failed: {e}")
            return None

    def _save_artwork(self, data: bytes, album_id: int, ext: str) -> str:
        """
        Save artwork data to cache directory.

        Args:
            data: Image data bytes
            album_id: Album ID
            ext: File extension (jpg, png, etc.)

        Returns:
            str: Path to saved artwork file
        """
        # Create unique filename based on album ID and data hash
        data_hash = hashlib.md5(data).hexdigest()[:8]
        filename = f"album_{album_id}_{data_hash}.{ext}"
        filepath = self.cache_dir / filename

        # Save file
        with open(filepath, "wb") as f:
            f.write(data)

        return str(filepath)

    def clear_cache(self) -> None:
        """Clear all cached artwork files."""
        try:
            for file in self.cache_dir.glob("album_*.*"):
                file.unlink()
            logger.info("Artwork cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear artwork cache: {e}")


# Global instance
_artwork_downloader = None


def get_artwork_downloader() -> ArtworkDownloader:
    """Get or create global artwork downloader instance."""
    global _artwork_downloader
    if _artwork_downloader is None:
        _artwork_downloader = ArtworkDownloader()
    return _artwork_downloader
