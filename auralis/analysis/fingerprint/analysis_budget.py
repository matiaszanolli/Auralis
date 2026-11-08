"""
Memory budget for concurrent fingerprint analyses.

Whole-track analysis (algorithm v13) peaks at roughly 85 MB per minute of analysed
audio inside the analyzer -- about 8x the 22.05 kHz stereo input: ~300 MB for a
4 min track, ~1.2 GB for 13 min. The 90 s window it replaced needed ~130-200 MB.
The fingerprint queue runs up to dozens of workers, so without a shared bound the
peak would scale with the worker count. This gate bounds the analyzer at about
3.4 GB however many workers there are, weighting each job by its minutes of audio.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

#: Minutes of audio the analyzer may hold in flight across ALL workers at once.
ANALYSIS_BUDGET_MINUTES: float = 40.0


class AnalysisBudget:
    """Weighted gate on concurrent analyses, by minutes of audio.

    A job is always admitted when nothing else is running, so a track longer than
    the whole budget cannot deadlock; otherwise it waits for room.
    """

    def __init__(self, capacity_minutes: float = ANALYSIS_BUDGET_MINUTES) -> None:
        self._capacity = capacity_minutes
        self._in_flight = 0.0
        self._cond = threading.Condition()

    @contextmanager
    def reserve(self, minutes: float) -> Iterator[None]:
        with self._cond:
            self._cond.wait_for(
                lambda: self._in_flight == 0.0 or self._in_flight + minutes <= self._capacity
            )
            self._in_flight += minutes
        try:
            yield
        finally:
            with self._cond:
                self._in_flight -= minutes
                self._cond.notify_all()


#: The process-wide gate every fingerprint computation goes through.
analysis_budget = AnalysisBudget()
