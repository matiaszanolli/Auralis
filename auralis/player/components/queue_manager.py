"""
Queue Manager
~~~~~~~~~~~~~

Track queue management for audio playback

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import Any

from .queue_navigation import QueueNavigationMixin
from .queue_shuffle import ShuffleMixin


class QueueManager(QueueNavigationMixin, ShuffleMixin):
    """Simple queue management for track playback"""

    def __init__(self) -> None:
        """Initialize queue manager"""
        self.tracks: list[dict[str, Any]] = []
        self.current_index = -1
        self.shuffle_enabled = False
        self.repeat_enabled = False
        self._lock = threading.RLock()
        self._pre_shuffle_tracks: list[dict[str, Any]] | None = None
        self._pre_shuffle_index: int = -1

    def add_track(self, track_info: dict[str, Any]) -> None:
        """Add a track to the queue"""
        with self._lock:
            self.tracks.append(track_info)
            self._invalidate_shuffle_snapshot_unlocked()

    def insert_track(self, index: int, track_info: dict[str, Any]) -> int:
        """Insert a track atomically and keep the current track selected.

        Returns the normalized insertion index.  QueueService previously
        rebuilt the whole queue with ``set_queue`` for positional inserts,
        which reused a stale numeric current index and changed the playing
        track whenever an item was inserted before it (#4776).
        """
        with self._lock:
            normalized_index = min(max(index, 0), len(self.tracks))
            self.tracks.insert(normalized_index, track_info)
            if self.current_index >= 0 and normalized_index <= self.current_index:
                self.current_index += 1
            self._invalidate_shuffle_snapshot_unlocked()
            return normalized_index

    def add_tracks(self, track_list: list[dict[str, Any]]) -> None:
        """Add multiple tracks to the queue"""
        with self._lock:
            self.tracks.extend(track_list)
            self._invalidate_shuffle_snapshot_unlocked()

    def _get_current_track_unlocked(self) -> dict[str, Any] | None:
        """Get current track info (caller must hold self._lock)."""
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def get_current_track(self) -> dict[str, Any] | None:
        """Get current track info"""
        with self._lock:
            return self._get_current_track_unlocked()

    def clear(self) -> None:
        """Clear the queue"""
        with self._lock:
            self.tracks.clear()
            self.current_index = -1
            self._invalidate_shuffle_snapshot_unlocked()

    def _remove_track_unlocked(self, index: int) -> bool:
        """
        Remove a track at the specified index (caller must hold self._lock).

        Args:
            index: Index of track to remove

        Returns:
            True if track was removed, False if index was invalid
        """
        if 0 <= index < len(self.tracks):
            self.tracks.pop(index)
            self._invalidate_shuffle_snapshot_unlocked()

            # Adjust current_index if necessary
            if index < self.current_index:
                self.current_index -= 1
            elif index == self.current_index:
                # If we removed the current track, stay at the same index
                # (which now points to the next track)
                if self.current_index >= len(self.tracks):
                    self.current_index = len(self.tracks) - 1

            return True
        return False

    def remove_track(self, index: int) -> bool:
        """
        Remove a track at the specified index

        Args:
            index: Index of track to remove

        Returns:
            True if track was removed, False if index was invalid
        """
        with self._lock:
            return self._remove_track_unlocked(index)

    def remove_if_index_matches_current(self, index: int) -> tuple[bool, bool]:
        """
        Atomically check whether `index` is the current track and remove it (#5360).

        Closes the TOCTOU gap between reading `current_index == index` and
        calling `remove_track(index)` as two separate lock acquisitions —
        auto-advance, next/previous, or a second concurrent remove could
        move `current_index` in that gap, producing a stale "was current"
        determination for the #2403 reload/stop follow-up (which relies on
        knowing whether the just-removed track was the one playing). Same
        single-acquisition shape as `advance_if_next_matches()`.

        Args:
            index: Index of the track to remove.

        Returns:
            (removed, was_current): `removed` is True if the track was
            removed (index was valid at the instant of removal); `was_current`
            is True if that track was the current track at that same instant.
        """
        with self._lock:
            was_current = (index == self.current_index)
            removed = self._remove_track_unlocked(index)
            return removed, was_current

    def reorder_tracks(self, new_order: list[int]) -> bool:
        """
        Reorder tracks according to new index order

        Args:
            new_order: List of indices representing new order

        Returns:
            True if reordering was successful, False otherwise
        """
        with self._lock:
            if len(new_order) != len(self.tracks):
                return False

            # Verify all indices are valid
            if set(new_order) != set(range(len(self.tracks))):
                return False

            # Preserve the exact queue item, including filepath-only entries
            # and duplicate track IDs. QueueController.set_queue commonly
            # stores entries without an id, for which the old implementation
            # always reset current_index to zero (#4776).
            current_track = self._get_current_track_unlocked()

            # Reorder tracks
            self.tracks = [self.tracks[i] for i in new_order]
            self._invalidate_shuffle_snapshot_unlocked()

            # Update current_index to point to the same object (#2159/#4776).
            if current_track is not None:
                self.current_index = next(
                    i for i, track in enumerate(self.tracks) if track is current_track
                )

            return True

    def move_track(self, from_index: int, to_index: int) -> bool:
        """Move one queue item atomically while preserving the current item."""
        with self._lock:
            queue_size = len(self.tracks)
            if not (0 <= from_index < queue_size and 0 <= to_index < queue_size):
                return False

            current_track = self._get_current_track_unlocked()
            moved_track = self.tracks.pop(from_index)
            self.tracks.insert(to_index, moved_track)
            self._invalidate_shuffle_snapshot_unlocked()

            if current_track is not None:
                self.current_index = next(
                    i for i, track in enumerate(self.tracks) if track is current_track
                )
            return True

    def get_queue(self) -> list[dict[str, Any]]:
        """
        Get the entire queue

        Returns:
            List of track info dictionaries
        """
        with self._lock:
            return self.tracks.copy()

    def get_queue_size(self) -> int:
        """
        Get the size of the queue

        Returns:
            Number of tracks in queue
        """
        with self._lock:
            return len(self.tracks)

    def get_queue_info(self) -> dict[str, Any]:
        """
        Return a fully atomic composite snapshot of queue state (fixes #2470).
        Holds _lock for the entire read so that concurrent remove_track() /
        next_track() calls cannot produce an inconsistent dict where
        current_track is absent from tracks or current_index is stale.
        """
        with self._lock:
            tracks_copy = self.tracks.copy()
            idx = self.current_index
            current = tracks_copy[idx] if 0 <= idx < len(tracks_copy) else None
            return {
                'tracks': tracks_copy,
                'current_index': idx,
                'current_track': current,
                'track_count': len(tracks_copy),
                'has_next': idx < len(tracks_copy) - 1,
                'has_previous': idx > 0,
                'shuffle_enabled': self.shuffle_enabled,
                'repeat_enabled': self.repeat_enabled,
            }


