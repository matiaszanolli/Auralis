"""A minimum spacing between outbound requests to the same artwork host (#5069, #6548).

The route that triggers a download is per album, so the path-prefix rate limiter cannot see an
unbounded key space of ``/albums/{id}/artwork/download`` paths (#4728), and nothing else limited how
fast a loop of requests could drive the providers. MusicBrainz asks clients for at most one request
a second and blocks those that exceed it (by User-Agent, which every Auralis install shares); iTunes
answers roughly twenty a minute before returning errors. Spacing request starts per host here bounds
the outbound rate whoever is asking: the backend downloader awaits ``wait()``, the synchronous
``fetch_artwork`` CLI calls ``wait_blocking()`` (#6548).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import threading
import time
from collections.abc import Mapping

# MusicBrainz's published limit is one request a second; a little slack keeps clock jitter under it.
MUSICBRAINZ_MIN_INTERVAL_S = 1.1


class HostThrottle:
    """Hands out request slots at least ``min_intervals[host]`` seconds apart.

    A caller reserves the next free slot under a lock and then sleeps until it, so concurrent
    callers queue in order without holding the lock while they wait.
    """

    def __init__(self, min_intervals: Mapping[str, float]) -> None:
        self._intervals = dict(min_intervals)
        self._lock = threading.Lock()
        self._next_slot: dict[str, float] = {}

    def _reserve(self, host: str) -> float:
        """Take the next slot for ``host``; returns how long to sleep until it. Unknown hosts: 0."""
        interval = self._intervals.get(host, 0.0)
        if interval <= 0:
            return 0.0
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next_slot.get(host, 0.0))
            self._next_slot[host] = slot + interval
        return slot - now

    async def wait(self, host: str) -> None:
        """Return when the caller may send its next request to ``host``."""
        delay = self._reserve(host)
        if delay > 0:
            await asyncio.sleep(delay)

    def wait_blocking(self, host: str) -> None:
        """``wait()`` for synchronous callers (the CLI)."""
        delay = self._reserve(host)
        if delay > 0:
            time.sleep(delay)

    def back_off(self, host: str, seconds: float) -> None:
        """Push ``host``'s next slot at least ``seconds`` out: it answered 429/503 (#6548)."""
        with self._lock:
            resume = time.monotonic() + seconds
            self._next_slot[host] = max(self._next_slot.get(host, 0.0), resume)
