"""
iTunes Search API artwork provider
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

from services.artwork_providers.bounded_read import read_bounded, read_bounded_json
from services.artwork_providers.trust import _get_trusted_artwork

from auralis.utils.artwork_security import MAX_ARTWORK_PAYLOAD_BYTES as _MAX_ARTWORK_BYTES

if TYPE_CHECKING:
    from services.artwork_downloader import ArtworkDownloader

logger = logging.getLogger(__name__)


async def try_itunes(
    downloader: "ArtworkDownloader",
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
        session = downloader._get_session()
        # Search iTunes
        params: dict[str, str | int] = {
            "term": f"{artist} {album}",
            "media": "music",
            "entity": "album",
            "limit": 1
        }

        async with session.get(
            downloader.itunes_api, params=params, allow_redirects=False
        ) as resp:
            if resp.status != 200:
                return None

            data = await read_bounded_json(resp, _MAX_ARTWORK_BYTES)
            if data is None:
                logger.warning(f"iTunes search response exceeded {_MAX_ARTWORK_BYTES} byte limit")
                return None
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

            artwork_data = await read_bounded(resp, _MAX_ARTWORK_BYTES)
            if artwork_data is None:
                logger.warning(f"iTunes artwork exceeded {_MAX_ARTWORK_BYTES} byte limit")
                return None
            return await downloader._save_artwork(artwork_data, album_id, "jpg")

    except TimeoutError:
        # #4686: hit _ARTWORK_REQUEST_TIMEOUT. WARNING, not the debug level
        # other lookup failures use, so a black-holing host is visible.
        logger.warning("iTunes artwork request timed out")
        return None
    except Exception as e:
        logger.debug(f"iTunes lookup failed: {e}")
        return None
