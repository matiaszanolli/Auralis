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
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import hashlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urljoin

import aiohttp

from auralis.utils.artwork_security import (
    MAX_ARTWORK_PAYLOAD_BYTES as _MAX_ARTWORK_BYTES,
)
from auralis.utils.artwork_security import detect_image_extension as _detect_image_extension
from auralis.utils.artwork_security import validate_artwork_url as _validate_artwork_url
from auralis.utils.logging import sanitize_log_value

logger = logging.getLogger(__name__)

# _detect_image_extension used to be defined here; it now lives in
# auralis.utils.artwork_security so library/artwork.py's embedded/folder
# extractor can share it too (#4849) instead of re-trusting a tag's declared
# MIME. Re-imported under the original name above so this module's own call
# site and tests/backend/test_artwork_extension_detection.py's import both
# keep working unchanged.


# #4686: aiohttp's default ClientTimeout is total=300s, and the downloader
# walks up to four remote calls per album in sequence, so one host that accepts
# the connection and never answers could hold a worker for ~20 minutes with
# nothing logged. Bound every request, and bound the album's whole chain too, so
# adding another fallback source cannot multiply the worst case again.
_ARTWORK_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5)
_ARTWORK_LOOKUP_BUDGET_S = 45.0

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
# Cover Art Archive needs two hops (coverartarchive.org -> archive.org ->
# an ia*.us.archive.org mirror); anything far past that is not a CDN.
_MAX_ARTWORK_REDIRECTS = 5


@asynccontextmanager
async def _get_trusted_artwork(
    session: aiohttp.ClientSession,
    url: str,
    source: str,
    headers: dict[str, str] | None = None,
) -> AsyncIterator[aiohttp.ClientResponse | None]:
    """GET an artwork image, validating each redirect hop before requesting it.

    aiohttp follows redirects by default, so the old check on the final
    ``resp.url`` ran only after every intermediate hop had already been sent a
    real request, loopback and LAN addresses included (#5330). Redirects are
    followed here one hop at a time instead. Yields the 200 response, or None
    when a hop is untrusted, the chain is too long, or the final status is not
    200.
    """
    for _ in range(_MAX_ARTWORK_REDIRECTS + 1):
        if not _validate_artwork_url(url):
            logger.warning(f"Rejecting untrusted {source} artwork URL: {url!r}")
            break
        async with session.get(url, headers=headers, allow_redirects=False) as resp:
            location = (
                resp.headers.get("Location")
                if resp.status in _REDIRECT_STATUSES
                else None
            )
            if location is None:
                yield resp if resp.status == 200 else None
                return
        url = urljoin(url, location)
    else:
        logger.warning(
            f"{source} artwork exceeded {_MAX_ARTWORK_REDIRECTS} redirects"
        )
    yield None


class ArtworkDownloader:
    """
    Service for downloading album artwork from online sources.

    Uses multiple sources with fallback:
    1. MusicBrainz Cover Art Archive (open source, no API key needed)
    2. iTunes Search API (free, no API key needed)
    3. Last.fm API (requires API key)
    """

    def __init__(self, cache_dir: str = "~/.auralis/artwork"):
        """
        Initialize artwork downloader.

        Args:
            cache_dir: Directory to cache downloaded artwork. Defaults to the
                single served directory ``~/.auralis/artwork`` — the same one
                the embedded extractor (``auralis/library/artwork.py``) writes
                to and the only one the GET endpoint
                (``routers/artwork.py``) will serve. A sibling
                ``~/.auralis/artwork_cache`` used to be the default, so every
                downloaded image failed the serving guard with 403 (#4408).
                Both writers share the ``album_{id}_{hash}.{ext}`` naming, so
                they coexist in this directory without collision.
        """
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # API endpoints
        self.musicbrainz_api = "https://musicbrainz.org/ws/2"
        self.coverart_api = "https://coverartarchive.org"
        self.itunes_api = "https://itunes.apple.com/search"

        # Shared session (fixes #3915 regression of #3558): reused across
        # calls with a small connection pool so bulk artwork backfills reuse
        # keep-alive connections instead of a fresh TCP/TLS handshake per
        # request. Created lazily on first use, not in __init__, because it
        # must be opened from within the event loop it will be used on.
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the shared HTTP session, creating it on first use."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=4, ttl_dns_cache=300),
                timeout=_ARTWORK_REQUEST_TIMEOUT,
            )
        return self._session

    async def close(self) -> None:
        """Close the shared HTTP session, releasing pooled connections.

        Call from application shutdown (see close_artwork_downloader()).
        """
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def download_artwork(
        self,
        artist: str,
        album: str,
        album_id: int
    ) -> str | None:
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
            return await asyncio.wait_for(
                self._lookup(artist, album, album_id),
                timeout=_ARTWORK_LOOKUP_BUDGET_S,
            )
        except TimeoutError:
            logger.warning(
                f"Artwork lookup for '{sanitize_log_value(album)}' by "
                f"'{sanitize_log_value(artist)}' timed out after "
                f"{_ARTWORK_LOOKUP_BUDGET_S:.0f}s"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to download artwork: {e}")
            return None

    async def _lookup(self, artist: str, album: str, album_id: int) -> str | None:
        """Walk the source chain; bounded as a whole by download_artwork."""
        # Try MusicBrainz first (best quality, open source)
        artwork_path = await self._try_musicbrainz(artist, album, album_id)
        if artwork_path:
            logger.info(f"Downloaded artwork from MusicBrainz for '{sanitize_log_value(album)}' by '{sanitize_log_value(artist)}'")
            return artwork_path

        # Fallback to iTunes
        artwork_path = await self._try_itunes(artist, album, album_id)
        if artwork_path:
            logger.info(f"Downloaded artwork from iTunes for '{sanitize_log_value(album)}' by '{sanitize_log_value(artist)}'")
            return artwork_path

        logger.warning(f"No artwork found for '{sanitize_log_value(album)}' by '{sanitize_log_value(artist)}'")
        return None

    async def _try_musicbrainz(
        self,
        artist: str,
        album: str,
        album_id: int
    ) -> str | None:
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
            session = self._get_session()
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

            async with session.get(
                search_url, params=params, headers=headers, allow_redirects=False
            ) as resp:  # type: ignore[arg-type]
                if resp.status != 200:
                    return None

                data = await resp.json()
                releases = data.get("releases", [])

                if not releases:
                    return None

                release_id = releases[0]["id"]

            # Get cover art
            coverart_url = f"{self.coverart_api}/release/{release_id}/front"

            # Every redirect hop is validated before it is requested (#2576, #5330).
            async with _get_trusted_artwork(
                session, coverart_url, "MusicBrainz", headers
            ) as resp:
                if resp is None:
                    return None

                # Size-limited read to prevent memory exhaustion (#2576)
                content_length = resp.content_length or 0
                if content_length > _MAX_ARTWORK_BYTES:
                    logger.warning(f"MusicBrainz artwork too large: {content_length} bytes")
                    return None
                artwork_data = await resp.content.read(_MAX_ARTWORK_BYTES + 1)
                if len(artwork_data) > _MAX_ARTWORK_BYTES:
                    logger.warning(f"MusicBrainz artwork exceeded {_MAX_ARTWORK_BYTES} byte limit")
                    return None
                return await self._save_artwork(artwork_data, album_id, "jpg")

        except TimeoutError:
            # #4686: hit _ARTWORK_REQUEST_TIMEOUT. WARNING, not the debug level
            # other lookup failures use, so a black-holing host is visible.
            logger.warning("MusicBrainz artwork request timed out")
            return None
        except Exception as e:
            logger.debug(f"MusicBrainz lookup failed: {e}")
            return None

    async def _try_itunes(
        self,
        artist: str,
        album: str,
        album_id: int
    ) -> str | None:
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
            session = self._get_session()
            # Search iTunes
            params = {
                "term": f"{artist} {album}",
                "media": "music",
                "entity": "album",
                "limit": 1
            }

            async with session.get(
                self.itunes_api, params=params, allow_redirects=False
            ) as resp:  # type: ignore[arg-type]
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

            # Download artwork (size-limited, #2576). The response-supplied URL
            # and every redirect hop are validated before being requested
            # (#2416, #5330).
            async with _get_trusted_artwork(session, artwork_url, "iTunes") as resp:
                if resp is None:
                    return None

                content_length = resp.content_length or 0
                if content_length > _MAX_ARTWORK_BYTES:
                    logger.warning(f"iTunes artwork too large: {content_length} bytes")
                    return None
                artwork_data = await resp.content.read(_MAX_ARTWORK_BYTES + 1)
                if len(artwork_data) > _MAX_ARTWORK_BYTES:
                    logger.warning(f"iTunes artwork exceeded {_MAX_ARTWORK_BYTES} byte limit")
                    return None
                return await self._save_artwork(artwork_data, album_id, "jpg")

        except TimeoutError:
            # #4686: hit _ARTWORK_REQUEST_TIMEOUT. WARNING, not the debug level
            # other lookup failures use, so a black-holing host is visible.
            logger.warning("iTunes artwork request timed out")
            return None
        except Exception as e:
            logger.debug(f"iTunes lookup failed: {e}")
            return None

    async def _save_artwork(self, data: bytes, album_id: int, ext: str = "jpg") -> str:
        """
        Save artwork data to cache directory.

        Args:
            data: Image data bytes
            album_id: Album ID
            ext: Fallback extension used only when the bytes are unrecognised;
                the real extension is sniffed from magic bytes (#4419).

        Returns:
            str: Path to saved artwork file
        """
        # Sniff the true format from magic bytes so a downloaded PNG/WebP is not
        # mislabelled .jpg and later served with the wrong Content-Type (#4419).
        ext = _detect_image_extension(data, default=ext)

        # Create unique filename based on album ID and data hash
        data_hash = hashlib.md5(data).hexdigest()[:8]
        filename = f"album_{album_id}_{data_hash}.{ext}"
        filepath = self.cache_dir / filename

        # Offload the blocking write so the event loop isn't stalled during
        # bulk artwork backfills (#3915).
        await asyncio.to_thread(filepath.write_bytes, data)

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


async def close_artwork_downloader() -> None:
    """Close the global artwork downloader's HTTP session, if one was ever
    created. Call from application shutdown (#3915)."""
    if _artwork_downloader is not None:
        await _artwork_downloader.close()
