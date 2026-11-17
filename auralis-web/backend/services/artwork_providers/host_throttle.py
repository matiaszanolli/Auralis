"""A minimum spacing between outbound requests to the same artwork host (#5069).

The route that triggers a download is per album, so the path-prefix rate limiter cannot see an
unbounded key space of ``/albums/{id}/artwork/download`` paths (#4728), and nothing else limited how
fast a loop of requests could drive the providers. MusicBrainz asks clients for at most one request
a second and blocks those that exceed it; iTunes answers roughly twenty a minute before returning
errors. Spacing request starts per host here bounds the outbound rate whoever is asking.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import time
from collections.abc import Mapping


class HostThrottle:
    """Hands out request slots at least ``min_intervals[host]`` seconds apart."""

    def __init__(self, min_intervals: Mapping[str, float]) -> None:
        self._intervals = dict(min_intervals)
        self._locks: dict[str, asyncio.Lock] = {}
        self._next_slot: dict[str, float] = {}

    async def wait(self, host: str) -> None:
        """Return when the caller may send its next request to ``host``; unknown hosts never wait."""
        interval = self._intervals.get(host, 0.0)
        if interval <= 0:
            return
        lock = self._locks.setdefault(host, asyncio.Lock())  # created inside the running loop
        async with lock:
            delay = self._next_slot.get(host, 0.0) - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_slot[host] = time.monotonic() + interval
