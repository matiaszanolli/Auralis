"""
Queue navigation for QueueManager (split from queue_manager.py, #5836): peek,
advance, step back, compare-and-set rollback and jump-to-index. Every method
takes ``_lock`` for its whole read-modify-write.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import Any


def _track_matches(candidate: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Identity check for two track dicts — id first, then file path."""
    cand_id = candidate.get('id')
    exp_id = expected.get('id')
    if cand_id is not None and exp_id is not None:
        return bool(cand_id == exp_id)
    cand_path = candidate.get('file_path') or candidate.get('path')
    exp_path = expected.get('file_path') or expected.get('path')
    return cand_path is not None and bool(cand_path == exp_path)


class QueueNavigationMixin:
    """Index movement; ``tracks``, ``current_index`` and ``_lock`` belong to QueueManager."""

    tracks: list[dict[str, Any]]
    current_index: int
    repeat_enabled: bool
    _lock: "threading.RLock"

    def _get_current_track_unlocked(self) -> dict[str, Any] | None:
        raise NotImplementedError

    def peek_next(self) -> dict[str, Any] | None:
        """
        Get the next track without moving the queue position.
        Used for pre-buffering in gapless playback.

        Returns:
            Next track info or None if no next track
        """
        with self._lock:
            if not self.tracks:
                return None

            next_index = self.current_index + 1

            if next_index < len(self.tracks):
                return self.tracks[next_index]
            elif self.repeat_enabled:
                return self.tracks[0]  # Will loop back to start
            else:
                return None

    def next_track(self) -> dict[str, Any] | None:
        """Move to next track"""
        with self._lock:
            if not self.tracks:
                return None

            if self.current_index < len(self.tracks) - 1:
                self.current_index += 1
            elif self.repeat_enabled:
                self.current_index = 0
            else:
                return None

            return self._get_current_track_unlocked()

    def advance_if_next_matches(self, expected: dict[str, Any]) -> dict[str, Any] | None:
        """
        Atomically advance to next track only if the slot still matches `expected`.

        #3352 (PTS-9): `advance_with_prebuffer` previously called
        `peek_next_track()` to choose what to load, processed audio for that
        track over a measurable gap, then called `next_track()` to commit the
        advance. Any queue mutation in between (`add_track`, `remove_track`,
        `reorder_tracks`, `shuffle`, `clear`) could leave the engine with
        prebuffered audio for one track but a queue index pointing at another.

        This method closes the gap: under a single lock acquisition it
        re-resolves what `next_track()` would do, verifies the resulting
        track still matches the one the caller peeked, and only then advances
        the index. On mismatch it returns None and leaves `current_index`
        untouched so the caller can fall back cleanly.

        Args:
            expected: The track dict returned by the prior `peek_next()` call.
                Matching uses `id` if present, otherwise `file_path`/`path`.

        Returns:
            The advanced-to track on success, None on mismatch / empty queue.
        """
        with self._lock:
            if not self.tracks:
                return None

            if self.current_index < len(self.tracks) - 1:
                target_index = self.current_index + 1
            elif self.repeat_enabled:
                target_index = 0
            else:
                return None

            candidate = self.tracks[target_index]
            if not _track_matches(candidate, expected):
                return None

            self.current_index = target_index
            return self._get_current_track_unlocked()

    def previous_track(self) -> dict[str, Any] | None:
        """Move to previous track"""
        with self._lock:
            if not self.tracks:
                return None

            if self.current_index > 0:
                self.current_index -= 1
            elif self.repeat_enabled:
                self.current_index = len(self.tracks) - 1
            else:
                return None

            return self._get_current_track_unlocked()

    def snapshot_index(self) -> int:
        """
        Atomically read self.current_index under self._lock.

        #3726: callers that need to capture the index for later rollback
        must read it under the same lock that mutators write through.
        Previously `previous_track()` read `queue.current_index` as a raw
        attribute (the write side was already lock-protected by #3668).
        CPython's GIL keeps the int read torn-free, but a concurrent
        `next_track()` / `remove_track()` / `reorder_tracks()` can change
        the index's relationship to the queue contents between the snapshot
        and the eventual rollback, leaving the queue off-by-one.
        """
        with self._lock:
            return self.current_index

    def rollback_index(self, saved_index: int, expected_current: int | None = None) -> bool:
        """
        Restore current_index to a saved value under self._lock.

        #3668: previous_track() callers used to save the index, move it,
        and on file-load failure write `self.queue.queue.current_index =
        saved_index` directly. The bare write bypassed self._lock and could
        clobber a concurrent next_track() / remove_track() / reorder_tracks()
        modification. This method makes the rollback locked and explicit.

        #5582: the write is now a compare-and-set. previous_track() moves the
        index and then does a blocking load with no lock held; a queue edit in
        that window can move current_index somewhere else (the probe: remove
        the track before the saved slot and the unconditional write landed
        current_index == len(tracks), a state with no current track). Pass
        *expected_current* — the index previous_track() moved to — and the
        restore happens only if current_index still holds it. The restored
        value is clamped to the live queue bounds either way. Returns whether
        the rollback was applied.
        """
        with self._lock:
            if expected_current is not None and self.current_index != expected_current:
                return False
            self.current_index = max(-1, min(saved_index, len(self.tracks) - 1))
            return True

    def set_track_by_index(self, index: int) -> dict[str, Any] | None:
        """
        Set current track by index (jump to track in queue)

        Args:
            index: Index of track to play

        Returns:
            Track info if valid index, None otherwise
        """
        with self._lock:
            if 0 <= index < len(self.tracks):
                self.current_index = index
                return self._get_current_track_unlocked()
            return None
