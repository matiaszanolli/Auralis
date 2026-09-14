"""
QueueManager.remove_if_index_matches_current — #5360 regression coverage.

QueueService.remove_track_from_queue's `was_current` check and the
subsequent removal used to be two separate lock acquisitions
(`index == queue_manager.current_index`, then `remove_track(index)`).
Auto-advance, next/previous, or a second concurrent remove could move
current_index in the gap, producing a stale was_current value for the
#2403 reload/stop follow-up. This method closes the gap: both the check
and the removal happen under one lock acquisition, mirroring the existing
advance_if_next_matches() peek-and-commit pattern (#3352).
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.player.components.queue_manager import QueueManager


def _make_track(track_id: int) -> dict:
    return {"id": track_id, "title": f"Track {track_id}", "duration": 180}


class TestRemoveIfIndexMatchesCurrent:
    def setup_method(self) -> None:
        self.qm = QueueManager()
        self.qm.add_tracks([_make_track(i) for i in range(5)])
        self.qm.set_track_by_index(2)

    def test_removing_the_current_track_reports_was_current_true(self) -> None:
        removed, was_current = self.qm.remove_if_index_matches_current(2)

        assert removed is True
        assert was_current is True
        assert [t["id"] for t in self.qm.tracks] == [0, 1, 3, 4]

    def test_removing_a_non_current_track_reports_was_current_false(self) -> None:
        removed, was_current = self.qm.remove_if_index_matches_current(0)

        assert removed is True
        assert was_current is False
        assert [t["id"] for t in self.qm.tracks] == [1, 2, 3, 4]

    def test_invalid_index_reports_removed_false(self) -> None:
        removed, was_current = self.qm.remove_if_index_matches_current(99)

        assert removed is False
        assert was_current is False
        assert len(self.qm.tracks) == 5

    def test_current_index_adjusts_the_same_way_as_remove_track(self) -> None:
        """The atomic method must not change remove_track's existing
        index-adjustment semantics — only how was_current is determined."""
        # Removing an earlier track shifts current_index down by one.
        self.qm.remove_if_index_matches_current(0)
        assert self.qm.current_index == 1  # was 2, now the same track at index 1

    def test_concurrent_advance_cannot_interleave_with_check_and_remove(self) -> None:
        """Proves the was_current check and the removal are genuinely
        inseparable: a concurrent next_track() must block for the whole
        duration of the atomic call, not observe or act on a half-done
        state in between."""
        entered_critical_section = threading.Event()
        release_critical_section = threading.Event()
        real_remove_unlocked = self.qm._remove_track_unlocked

        def _slow_remove_unlocked(index):
            # Still inside `with self._lock:` at this point — a concurrent
            # next_track() (which also needs self._lock) can only run once
            # this call, and the lock acquisition holding it, returns.
            entered_critical_section.set()
            release_critical_section.wait(timeout=2.0)
            return real_remove_unlocked(index)

        self.qm._remove_track_unlocked = _slow_remove_unlocked

        advance_completed = threading.Event()

        def _advance() -> None:
            entered_critical_section.wait(timeout=2.0)
            self.qm.next_track()
            advance_completed.set()

        advancer = threading.Thread(target=_advance)
        advancer.start()

        result = self.qm.remove_if_index_matches_current(2)

        # If next_track() had managed to interleave (the check-and-remove
        # was NOT one lock acquisition), advance_completed would already be
        # set by the time remove_if_index_matches_current returns.
        assert not advance_completed.is_set(), (
            "a concurrent next_track() interleaved between the was_current "
            "check and the removal — the two are not atomic"
        )

        release_critical_section.set()
        advancer.join(timeout=2.0)

        assert result == (True, True)
