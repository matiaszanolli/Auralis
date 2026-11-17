"""
Chunk single-flight
~~~~~~~~~~~~~~~~~~~

One DSP render per chunk cache key, however many streams ask for it (#5258).

Every stream leases its own HybridProcessor (#6091), so two streams that miss the
cache for the same chunk - a rapid double seek, two clients on one track, or a
stream racing its own proactive buffer - rendered it twice on two processors. The
registry is process-wide and keyed on ``ChunkPathCache.cache_key()``, the identity
of the durable WAV: the first caller (the leader) renders and writes it, the others
(followers) wait for the leader to finish and then read the file it left.

A follower never inherits the leader's failure. When the leader was cancelled or
raised there is no file, the follower's re-lookup misses, and it claims the key
itself. Different keys never wait on each other.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

# How often a waiting follower re-checks its own stream's cancel flag.
FOLLOWER_POLL_S = 0.1


@dataclass(eq=False)
class ChunkFlight:
    """One in-flight render. ``leader`` is True for the caller that must do the work."""

    key: str
    leader: bool
    _done: threading.Event = field(default_factory=threading.Event, repr=False)

    def wait_for_leader(self, check_cancelled: Callable[[], None]) -> None:
        """Block until the leader finishes, polling ``check_cancelled`` (raises to abandon)."""
        while not self._done.wait(FOLLOWER_POLL_S):
            check_cancelled()


class ChunkSingleFlight:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._leaders: dict[str, ChunkFlight] = {}

    def claim(self, key: str) -> ChunkFlight:
        """Become the leader for ``key``, or get the running leader's flight to wait on."""
        with self._lock:
            running = self._leaders.get(key)
            if running is not None:
                return ChunkFlight(key, leader=False, _done=running._done)
            flight = ChunkFlight(key, leader=True)
            self._leaders[key] = flight
            return flight

    def release(self, flight: ChunkFlight) -> None:
        """The leader is done (rendered, cancelled or failed): wake every follower."""
        with self._lock:
            if self._leaders.get(flight.key) is flight:
                del self._leaders[flight.key]
        flight._done.set()

    def in_flight(self) -> int:
        with self._lock:
            return len(self._leaders)


chunk_flights = ChunkSingleFlight()
