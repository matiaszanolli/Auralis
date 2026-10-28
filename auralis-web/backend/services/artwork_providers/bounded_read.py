"""
Bounded response reads for the artwork providers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``StreamReader.read(n)`` returns whatever is buffered, up to ``n`` bytes, not
``n`` bytes, so ``read(limit + 1)`` followed by ``len(data) > limit`` never fires
for a body bigger than the first buffered chunk: the over-limit branch was dead
and any cover above ~128 KB was saved truncated (#6190). ``resp.json()`` had no
cap at all (#6191). Both providers read through here instead.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json
from typing import Any

import aiohttp

_CHUNK_BYTES = 64 * 1024


async def read_bounded(resp: aiohttp.ClientResponse, limit: int) -> bytes | None:
    """Read the whole body, or None as soon as it exceeds ``limit`` bytes."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in resp.content.iter_chunked(_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


async def read_bounded_json(resp: aiohttp.ClientResponse, limit: int) -> Any | None:
    """Decode a JSON body of at most ``limit`` bytes; None when it is larger.

    Malformed JSON raises ``ValueError`` like ``resp.json()`` does.
    """
    body = await read_bounded(resp, limit)
    if body is None:
        return None
    return json.loads(body.decode("utf-8"))
