"""
MusicBrainz Cover Art Archive provider
~~~~~~~~~~~~~~~~~~~~~~~

Split out of ``ArtworkDownloader`` (#6271): the provider takes the downloader
as its first argument (the #4245 coordinator pattern — the class method stays
a thin delegator so ``patch.object(downloader, ...)`` keeps working).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import aiohttp

from auralis.utils.artwork_security import (
    MAX_ARTWORK_PAYLOAD_BYTES as _MAX_ARTWORK_BYTES,
)
from services.artwork_providers.bounded_read import read_bounded, read_bounded_json
from services.artwork_providers.trust import _get_trusted_artwork

if TYPE_CHECKING:
    from services.artwork_downloader import ArtworkDownloader

logger = logging.getLogger(__name__)


async def try_musicbrainz(
    downloader: "ArtworkDownloader",
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
        session = downloader._get_session()
        # Search for release
        search_url = f"{downloader.musicbrainz_api}/release/"
        params: dict[str, str | int] = {
            "query": f'artist:"{artist}" AND release:"{album}"',
            "fmt": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "Auralis/1.0 (https://github.com/matiaszanolli/Auralis)"
        }

        async with session.get(
            search_url, params=params, headers=headers, allow_redirects=False
        ) as resp:
            if resp.status != 200:
                return None

            data = await read_bounded_json(resp, _MAX_ARTWORK_BYTES)
            if data is None:
                logger.warning(f"MusicBrainz search response exceeded {_MAX_ARTWORK_BYTES} byte limit")
                return None
            releases = data.get("releases", [])

            if not releases:
                return None

            release_id = releases[0]["id"]

        # Get cover art
        coverart_url = f"{downloader.coverart_api}/release/{release_id}/front"

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
            artwork_data = await read_bounded(resp, _MAX_ARTWORK_BYTES)
            if artwork_data is None:
                logger.warning(f"MusicBrainz artwork exceeded {_MAX_ARTWORK_BYTES} byte limit")
                return None
            return await downloader._save_artwork(artwork_data, album_id, "jpg")

    except TimeoutError:
        # #4686: hit _ARTWORK_REQUEST_TIMEOUT. WARNING, not the debug level
        # other lookup failures use, so a black-holing host is visible.
        logger.warning("MusicBrainz artwork request timed out")
        return None
    except Exception as e:
        logger.debug(f"MusicBrainz lookup failed: {e}")
        return None
