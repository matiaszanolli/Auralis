"""
Memory budget for concurrent fingerprint analyses.

Whole-track analysis (algorithm v13) peaks at roughly 85 MB per minute of analysed
audio inside the analyzer -- about 8x the 22.05 kHz stereo input: ~300 MB for a
4 min track, ~1.2 GB for 13 min. The 90 s window it replaced needed ~130-200 MB.
The fingerprint queue runs up to dozens of workers, so without a shared bound the
peak would scale with the worker count. This gate bounds the analyzer at about
3.4 GB however many workers there are, weighting each job by its minutes of audio.
Callers reserve BEFORE decoding, so a waiting job holds no buffer either (#6338).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import heapq
import itertools
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

#: Minutes of audio the analyzer may hold in flight across ALL workers at once.
ANALYSIS_BUDGET_MINUTES: float = 40.0

#: How often a waiter with a ``should_stop`` predicate re-checks it. The predicate
#: is usually a plain flag or ``Event.is_set`` that cannot notify the gate itself.
STOP_POLL_S: float = 0.25

_INTERACTIVE, _BACKGROUND = 0, 1


class AnalysisCancelled(Exception):
    """``reserve()`` gave up waiting because its ``should_stop`` predicate fired."""


class AnalysisBudget:
    """Fair, weighted gate on concurrent analyses, by minutes of audio.

    Waiters are admitted strictly in ticket order -- interactive (a track the
    user is waiting to hear) ahead of background, FIFO within each class -- so a
    long job at the head blocks smaller later ones instead of starving behind
    them (#6336). A job is always admitted when nothing else is running, so a
    track longer than the whole budget cannot deadlock.
    """

    def __init__(self, capacity_minutes: float = ANALYSIS_BUDGET_MINUTES) -> None:
        self._capacity = capacity_minutes
        self._in_flight = 0.0
        # Counted separately: float minutes added and removed in different
        # orders need not return to exactly 0.0, and "nothing running" must.
        self._running = 0
        self._waiting: list[tuple[int, int]] = []  # heap of (class, ticket)
        self._tickets = itertools.count()
        self._cond = threading.Condition()

    def _admissible(self, key: tuple[int, int], minutes: float) -> bool:
        return self._waiting[0] == key and (
            self._running == 0 or self._in_flight + minutes <= self._capacity
        )

    def _wait_turn(
        self, key: tuple[int, int], minutes: float, should_stop: Callable[[], bool] | None
    ) -> None:
        """Block (holding ``self._cond``) until ``key`` is admissible or stopped."""
        while True:
            if should_stop is not None and should_stop():
                raise AnalysisCancelled("analysis wait cancelled")
            if self._admissible(key, minutes):
                return
            self._cond.wait(STOP_POLL_S if should_stop is not None else None)

    @contextmanager
    def reserve(
        self,
        minutes: float,
        *,
        interactive: bool = False,
        should_stop: Callable[[], bool] | None = None,
    ) -> Iterator[None]:
        """Hold ``minutes`` of the budget for the ``with`` body.

        Raises ``AnalysisCancelled`` -- without admitting -- once ``should_stop()``
        returns True while waiting.
        """
        with self._cond:
            key = (_INTERACTIVE if interactive else _BACKGROUND, next(self._tickets))
            heapq.heappush(self._waiting, key)
            try:
                self._wait_turn(key, minutes, should_stop)
            except BaseException:
                self._waiting.remove(key)
                heapq.heapify(self._waiting)
                self._cond.notify_all()  # the next waiter may now be at the head
                raise
            heapq.heappop(self._waiting)
            self._in_flight += minutes
            self._running += 1
            self._cond.notify_all()  # the new head may fit alongside this job
        try:
            yield
        finally:
            with self._cond:
                self._in_flight -= minutes
                self._running -= 1
                self._cond.notify_all()


#: The process-wide gate every fingerprint computation goes through.
analysis_budget = AnalysisBudget()
