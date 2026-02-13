"""
Queue Manager
~~~~~~~~~~~~~

Track queue management for audio playback

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import random
from typing import Any


class QueueManager:
    """Simple queue management for track playback"""

    def __init__(self) -> None:
        """Initialize queue manager"""
        self.tracks: list[dict[str, Any]] = []
        self.current_index = -1
        self.shuffle_enabled = False
        self.repeat_enabled = False

    def add_track(self, track_info: dict[str, Any]) -> None:
        """Add a track to the queue"""
        self.tracks.append(track_info)

    def add_tracks(self, track_list: list[dict[str, Any]]) -> None:
        """Add multiple tracks to the queue"""
        self.tracks.extend(track_list)

    def get_current_track(self) -> dict[str, Any] | None:
        """Get current track info"""
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def peek_next(self) -> dict[str, Any] | None:
        """
        Get the next track without moving the queue position.
        Used for pre-buffering in gapless playback.

        Returns:
            Next track info or None if no next track
        """
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
        if not self.tracks:
            return None

        if self.current_index < len(self.tracks) - 1:
            self.current_index += 1
        elif self.repeat_enabled:
            self.current_index = 0
        else:
            return None

        return self.get_current_track()

    def previous_track(self) -> dict[str, Any] | None:
        """Move to previous track"""
        if not self.tracks:
            return None

        if self.current_index > 0:
            self.current_index -= 1
        elif self.repeat_enabled:
            self.current_index = len(self.tracks) - 1
        else:
            return None

        return self.get_current_track()

    def clear(self) -> None:
        """Clear the queue"""
        self.tracks.clear()
        self.current_index = -1

    def remove_track(self, index: int) -> bool:
        """
        Remove a track at the specified index

        Args:
            index: Index of track to remove

        Returns:
            True if track was removed, False if index was invalid
        """
        if 0 <= index < len(self.tracks):
            self.tracks.pop(index)

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

    def remove_tracks(self, indices: list[int]) -> int:
        """
        Remove multiple tracks at specified indices

        Args:
            indices: List of track indices to remove

        Returns:
            Number of tracks actually removed
        """
        # Sort indices in reverse order to avoid index shifting issues
        sorted_indices = sorted(set(indices), reverse=True)
        removed_count = 0

        for index in sorted_indices:
            if self.remove_track(index):
                removed_count += 1

        return removed_count

    def reorder_tracks(self, new_order: list[int]) -> bool:
        """
        Reorder tracks according to new index order

        Args:
            new_order: List of indices representing new order

        Returns:
            True if reordering was successful, False otherwise
        """
        if len(new_order) != len(self.tracks):
            return False

        # Verify all indices are valid
        if set(new_order) != set(range(len(self.tracks))):
            return False

        # Find current track ID to maintain playback
        current_track = self.get_current_track()
        current_track_id = current_track.get('id') if current_track else None

        # Reorder tracks
        self.tracks = [self.tracks[i] for i in new_order]

        # Update current_index to point to the same track
        if current_track_id is not None:
            for i, track in enumerate(self.tracks):
                if track.get('id') == current_track_id:
                    self.current_index = i
                    break

        return True

    def shuffle(self) -> None:
        """Shuffle the queue, keeping the current track in place"""
        if len(self.tracks) <= 1:
            return

        current_track = self.get_current_track()
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

    def get_queue(self) -> list[dict[str, Any]]:
        """
        Get the entire queue

        Returns:
            List of track info dictionaries
        """
        return self.tracks.copy()

    def get_queue_size(self) -> int:
        """
        Get the size of the queue

        Returns:
            Number of tracks in queue
        """
        return len(self.tracks)

    def set_track_by_index(self, index: int) -> dict[str, Any] | None:
        """
        Set current track by index (jump to track in queue)

        Args:
            index: Index of track to play

        Returns:
            Track info if valid index, None otherwise
        """
        if 0 <= index < len(self.tracks):
            self.current_index = index
            return self.get_current_track()
        return None


def create_queue_manager() -> QueueManager:
    """
    Factory function to create queue manager

    Returns:
        QueueManager instance
    """
    return QueueManager()
