# -*- coding: utf-8 -*-

"""
QueueController - Manages playlist queue and track navigation

Responsibilities:
- Queue management (add, remove, navigate)
- Track sequencing (next, previous)
- Shuffle and repeat modes
- Playlist loading
"""

from typing import Dict, Any, Optional, List
from .components import QueueManager
from ..library.manager import LibraryManager
from ..utils.logging import debug, info, warning, error


class QueueController:
    """
    Manages playback queue and track navigation.

    Decoupled from playback state, audio I/O, and prebuffering.
    Only responsible for queue operations and track sequencing.
    """

    def __init__(self, library_manager: Optional[LibraryManager] = None):
        self.queue = QueueManager()
        self.library = library_manager or LibraryManager()

    # Backward compatibility properties for old test code
    @property
    def tracks(self) -> List[Dict[str, Any]]:
        """Get list of tracks in queue"""
        return self.queue.tracks

    @property
    def current_index(self) -> int:
        """Get current track index"""
        return self.queue.current_index

    @current_index.setter
    def current_index(self, value: int):
        """Set current track index"""
        self.queue.current_index = value

    @property
    def shuffle_enabled(self) -> bool:
        """Get shuffle mode status"""
        return self.queue.shuffle_enabled

    @shuffle_enabled.setter
    def shuffle_enabled(self, value: bool):
        """Set shuffle mode"""
        self.queue.shuffle_enabled = value

    @property
    def repeat_enabled(self) -> bool:
        """Get repeat mode status"""
        return self.queue.repeat_enabled

    @repeat_enabled.setter
    def repeat_enabled(self, value: bool):
        """Set repeat mode"""
        self.queue.repeat_enabled = value

    def add_tracks(self, track_list: List[Dict[str, Any]]):
        """Add multiple tracks to queue"""
        for track_info in track_list:
            self.add_track(track_info)

    def clear(self):
        """Clear all tracks from queue (backward compatibility alias)"""
        self.clear_queue()

    def next_track(self) -> Optional[Dict[str, Any]]:
        """
        Get next track from queue.

        Returns:
            Track info dict or None if queue empty
        """
        next_track = self.queue.next_track()
        if next_track:
            info(f"Advancing to next track: {next_track.get('title', 'Unknown')}")
        else:
            info("No next track in queue")
        return next_track

    def previous_track(self) -> Optional[Dict[str, Any]]:
        """
        Get previous track from queue.

        Returns:
            Track info dict or None if at start
        """
        prev_track = self.queue.previous_track()
        if prev_track:
            info(f"Moved to previous track: {prev_track.get('title', 'Unknown')}")
        else:
            info("No previous track in queue")
        return prev_track

    def get_current_track(self) -> Optional[Dict[str, Any]]:
        """Get current track from queue"""
        return self.queue.get_current_track()

    def peek_next_track(self) -> Optional[Dict[str, Any]]:
        """
        Peek at next track without advancing queue.

        Useful for prebuffering the next track.
        """
        return self.queue.peek_next()

    def add_track(self, track_info: Dict[str, Any]):
        """Add a track to the queue"""
        self.queue.add_track(track_info)
        info(f"Added to queue: {track_info.get('title', 'Unknown')}")

    def add_track_from_library(self, track_id: int) -> bool:
        """
        Add a track from library by ID.

        Returns:
            bool: True if successful
        """
        try:
            track = self.library.get_track(track_id)
            if track:
                self.add_track(track.to_dict())
                return True
            return False
        except Exception as e:
            error(f"Failed to add track from library: {e}")
            return False

    def search_and_add(self, query: str, limit: int = 10) -> int:
        """
        Search library and add results to queue.

        Returns:
            Number of tracks added
        """
        try:
            tracks = self.library.search_tracks(query, limit)
            for track in tracks:
                self.add_track(track.to_dict())
            info(f"Added {len(tracks)} tracks to queue from search: {query}")
            return len(tracks)
        except Exception as e:
            error(f"Failed to search and add: {e}")
            return 0

    def load_playlist(self, playlist_id: int, start_index: int = 0) -> bool:
        """
        Load a playlist from library.

        Args:
            playlist_id: Database ID of playlist
            start_index: Index of track to start at

        Returns:
            bool: True if successful
        """
        try:
            playlist = self.library.get_playlist(playlist_id)
            if not playlist:
                error(f"Playlist not found: {playlist_id}")
                return False

            # Clear and reload queue
            self.queue.clear()

            for track in playlist.tracks:
                track_info = track.to_dict()
                self.queue.add_track(track_info)

            if self.queue.tracks:
                self.queue.current_index = min(start_index, len(self.queue.tracks) - 1)
                info(f"Loaded playlist: {playlist.name} ({len(playlist.tracks)} tracks)")
                return True

            warning(f"Playlist is empty: {playlist.name}")
            return False

        except Exception as e:
            error(f"Failed to load playlist: {e}")
            return False

    def clear_queue(self):
        """Clear all tracks from queue"""
        self.queue.clear()
        info("Queue cleared")

    def get_queue_info(self) -> Dict[str, Any]:
        """Get detailed queue information"""
        current = self.get_current_track()
        return {
            'tracks': self.queue.tracks.copy(),
            'current_index': self.queue.current_index,
            'current_track': current,
            'track_count': len(self.queue.tracks),
            'has_next': self.queue.current_index < len(self.queue.tracks) - 1,
            'has_previous': self.queue.current_index > 0,
            'shuffle_enabled': self.queue.shuffle_enabled,
            'repeat_enabled': self.queue.repeat_enabled,
        }

    def set_shuffle(self, enabled: bool):
        """Enable/disable shuffle mode"""
        self.queue.shuffle_enabled = enabled
        info(f"Shuffle {'enabled' if enabled else 'disabled'}")

    def set_repeat(self, enabled: bool):
        """Enable/disable repeat mode"""
        self.queue.repeat_enabled = enabled
        info(f"Repeat {'enabled' if enabled else 'disabled'}")

    def is_queue_empty(self) -> bool:
        """Check if queue is empty"""
        return len(self.queue.tracks) == 0

    def get_track_count(self) -> int:
        """Get number of tracks in queue"""
        return len(self.queue.tracks)
