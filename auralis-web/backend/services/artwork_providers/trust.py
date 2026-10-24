"""
Trusted Artwork Fetch
~~~~~~~~~~~~~~~~~~~~~

``_get_trusted_artwork`` — the SSRF-guarded redirect follower both artwork
providers use (every hop must stay on the provider's trusted hosts). Split
from artwork_downloader.py in #6271.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urljoin
import logging

import aiohttp

from auralis.utils.artwork_security import validate_artwork_url as _validate_artwork_url

logger = logging.getLogger(__name__)

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
