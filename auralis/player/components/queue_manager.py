# -*- coding: utf-8 -*-

"""
Queue Manager
~~~~~~~~~~~~~

Track queue management for audio playback

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import List, Dict, Any, Optional


class QueueManager:
    """Simple queue management for track playback"""

    def __init__(self):
        """Initialize queue manager"""
        self.tracks: List[Dict[str, Any]] = []
        self.current_index = -1
        self.shuffle_enabled = False
        self.repeat_enabled = False

    def add_track(self, track_info: Dict[str, Any]):
        """Add a track to the queue"""
        self.tracks.append(track_info)

    def add_tracks(self, track_list: List[Dict[str, Any]]):
        """Add multiple tracks to the queue"""
        self.tracks.extend(track_list)

    def get_current_track(self) -> Optional[Dict[str, Any]]:
        """Get current track info"""
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def next_track(self) -> Optional[Dict[str, Any]]:
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

    def previous_track(self) -> Optional[Dict[str, Any]]:
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

    def clear(self):
        """Clear the queue"""
        self.tracks.clear()
        self.current_index = -1


def create_queue_manager() -> QueueManager:
    """
    Factory function to create queue manager

    Returns:
        QueueManager instance
    """
    return QueueManager()
