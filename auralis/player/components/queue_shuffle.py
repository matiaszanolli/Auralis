"""
Shuffle / unshuffle for QueueManager (split from queue_manager.py, #5836): the
pre-shuffle snapshot and the one place that invalidates it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import random
import threading
from typing import Any
from collections.abc import Callable


class ShuffleMixin:
    """Snapshot-backed shuffle; ``tracks`` and ``_lock`` belong to QueueManager."""

    tracks: list[dict[str, Any]]
    current_index: int
    _lock: "threading.RLock"
    _pre_shuffle_tracks: list[dict[str, Any]] | None
    _pre_shuffle_index: int

    # Provided by QueueManager itself; shared with QueueNavigationMixin's host.
    _get_current_track_unlocked: "Callable[[], dict[str, Any] | None]"

    def _invalidate_shuffle_snapshot_unlocked(self) -> None:
        """
        Drop the pre-shuffle snapshot (caller must hold self._lock).

        #4525: any mutation of self.tracks while shuffled makes the snapshot
        stale — restoring it in unshuffle() would silently discard the
        mutation. Declining to restore (unshuffle() returns False once the
        snapshot is None) is safer than resurrecting/dropping tracks.
        """
        self._pre_shuffle_tracks = None
        self._pre_shuffle_index = -1

    def shuffle(self) -> None:
        """Shuffle the queue, keeping the current track in place"""
        with self._lock:
            if len(self.tracks) <= 1:
                return

            # Snapshot the original order so unshuffle() can restore it.
            # #5315: only on the not-shuffled -> shuffled transition. A
            # second shuffle() call while a snapshot is already held would
            # otherwise re-snapshot the *current* (already-shuffled) order,
            # permanently losing the true original — unshuffle() would then
            # restore the wrong order. `_pre_shuffle_tracks is None` is
            # exactly "no snapshot held", which _invalidate_shuffle_snapshot_
            # unlocked() (called by every queue-shape mutator) also resets to,
            # so a mutation-then-reshuffle still re-snapshots correctly.
            if self._pre_shuffle_tracks is None:
                self._pre_shuffle_tracks = list(self.tracks)
                self._pre_shuffle_index = self.current_index

            current_track = self._get_current_track_unlocked()
            current_track_id = current_track.get('id') if current_track else None

            # Shuffle all tracks
            random.shuffle(self.tracks)

            # If there was a current track, move it to the front
            if current_track_id is not None:
                for i, track in enumerate(self.tracks):
                    if track.get('id') == current_track_id:
                        # Swap current track to position 0
                        self.tracks[0], self.tracks[i] = self.tracks[i], self.tracks[0]
                        self.current_index = 0
                        break

    def unshuffle(self) -> bool:
        """Restore the pre-shuffle queue order. Returns True if restored."""
        with self._lock:
            if self._pre_shuffle_tracks is None:
                return False

            current_track = self._get_current_track_unlocked()
            current_track_id = current_track.get('id') if current_track else None

            self.tracks = self._pre_shuffle_tracks
            self.current_index = self._pre_shuffle_index

            # If the current track moved, find it in the restored order
            if current_track_id is not None:
                for i, track in enumerate(self.tracks):
                    if track.get('id') == current_track_id:
                        self.current_index = i
                        break

            self._pre_shuffle_tracks = None
            self._pre_shuffle_index = -1
            return True
