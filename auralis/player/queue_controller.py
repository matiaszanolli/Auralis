# -*- coding: utf-8 -*-

"""
QueueController - Manages playlist queue and track navigation

Responsibilities:
- Queue management (add, remove, navigate)
- Track sequencing (next, previous)
- Shuffle and repeat modes
- Playlist loading
"""

from typing import Dict, Any, Optional, List, Union, Callable
from .components import QueueManager
from ..library.repositories.factory import RepositoryFactory
from ..utils.logging import info, warning, error


class QueueController:
    """
    Manages playback queue and track navigation.

    Decoupled from playback state, audio I/O, and prebuffering.
    Only responsible for queue operations and track sequencing.

    Phase 6C: Fully migrated to RepositoryFactory pattern (no LibraryManager fallback)
    """

    def __init__(
        self,
        get_repository_factory: Callable[[], Any],
        library_manager: Optional[Any] = None
    ) -> None:
        """
        Initialize queue controller.

        Args:
            get_repository_factory: Callable that returns RepositoryFactory instance (REQUIRED)
            library_manager: Deprecated, kept for backward compatibility only
        """
        self.queue: Any = QueueManager()  # type: ignore[no-untyped-call]
        self.get_repository_factory = get_repository_factory

    def _get_repos(self) -> Any:
        """Get repository factory for data access."""
        try:
            factory = self.get_repository_factory()
            if factory:
                return factory
        except (TypeError, AttributeError) as e:
            error(f"Failed to get repository factory: {e}")

        raise RuntimeError(
            "Repository factory not available. "
            "Ensure get_repository_factory is properly configured during startup."
        )

    # Backward compatibility properties for old test code
    @property
    def tracks(self) -> List[Dict[str, Any]]:
        """Get list of tracks in queue"""
        return self.queue.tracks  # type: ignore[no-any-return]

    @property
    def current_index(self) -> int:
        """Get current track index"""
        return self.queue.current_index  # type: ignore[no-any-return]

    @current_index.setter
    def current_index(self, value: int) -> None:
        """Set current track index"""
        self.queue.current_index = value

    @property
    def shuffle_enabled(self) -> bool:
        """Get shuffle mode status"""
        return self.queue.shuffle_enabled  # type: ignore[no-any-return]

    @shuffle_enabled.setter
    def shuffle_enabled(self, value: bool) -> None:
        """Set shuffle mode"""
        self.queue.shuffle_enabled = value

    @property
    def repeat_enabled(self) -> bool:
        """Get repeat mode status"""
        return self.queue.repeat_enabled  # type: ignore[no-any-return]

    @repeat_enabled.setter
    def repeat_enabled(self, value: bool) -> None:
        """Set repeat mode"""
        self.queue.repeat_enabled = value

    def add_tracks(self, track_list: List[Dict[str, Any]]) -> None:
        """Add multiple tracks to queue"""
        for track_info in track_list:
            self.add_track(track_info)

    def clear(self) -> None:
        """Clear all tracks from queue (backward compatibility alias)"""
        self.clear_queue()

    def next_track(self) -> Optional[Dict[str, Any]]:
        """
        Get next track from queue.

        Returns:
            Track info dict or None if queue empty
        """
        next_track: Any = self.queue.next_track()
        if next_track:
            info(f"Advancing to next track: {next_track.get('title', 'Unknown')}")
        else:
            info("No next track in queue")
        return next_track  # type: ignore[no-any-return]

    def previous_track(self) -> Optional[Dict[str, Any]]:
        """
        Get previous track from queue.

        Returns:
            Track info dict or None if at start
        """
        prev_track: Any = self.queue.previous_track()
        if prev_track:
            info(f"Moved to previous track: {prev_track.get('title', 'Unknown')}")
        else:
            info("No previous track in queue")
        return prev_track  # type: ignore[no-any-return]

    def get_current_track(self) -> Optional[Dict[str, Any]]:
        """Get current track from queue"""
        return self.queue.get_current_track()  # type: ignore[no-any-return]

    def peek_next_track(self) -> Optional[Dict[str, Any]]:
        """
        Peek at next track without advancing queue.

        Useful for prebuffering the next track.
        """
        return self.queue.peek_next()  # type: ignore[no-any-return]

    def add_track(self, track_info: Dict[str, Any]) -> None:
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
            repos = self._get_repos()
            track = repos.tracks.get_by_id(track_id)
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
            repos = self._get_repos()
            tracks, _ = repos.tracks.search(query, limit=limit)
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
            repos = self._get_repos()
            playlist = repos.playlists.get_by_id(playlist_id)
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

    def clear_queue(self) -> None:
        """Clear all tracks from queue"""
        self.queue.clear()
        info("Queue cleared")

    def get_queue_info(self) -> Dict[str, Any]:
        """Get detailed queue information"""
        current: Optional[Dict[str, Any]] = self.get_current_track()
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

    def set_shuffle(self, enabled: bool) -> None:
        """Enable/disable shuffle mode"""
        self.queue.shuffle_enabled = enabled
        info(f"Shuffle {'enabled' if enabled else 'disabled'}")

    def set_repeat(self, enabled: bool) -> None:
        """Enable/disable repeat mode"""
        self.queue.repeat_enabled = enabled
        info(f"Repeat {'enabled' if enabled else 'disabled'}")

    def is_queue_empty(self) -> bool:
        """Check if queue is empty"""
        return len(self.queue.tracks) == 0

    def get_track_count(self) -> int:
        """Get number of tracks in queue"""
        return len(self.queue.tracks)

    def get_queue_size(self) -> int:
        """Get queue size (alias for get_track_count)"""
        return len(self.queue.tracks)

    def remove_track(self, index: int) -> bool:
        """Remove track at specified index"""
        return self.queue.remove_track(index)  # type: ignore[no-any-return]

    def get_queue(self) -> List[Dict[str, Any]]:
        """Get full queue as list"""
        return self.queue.get_queue()  # type: ignore[no-any-return]

    def reorder_tracks(self, new_order: List[int]) -> bool:
        """Reorder tracks according to new index order"""
        return self.queue.reorder_tracks(new_order)  # type: ignore[no-any-return]

    def set_queue(self, track_list: List[Union[str, Dict[str, Any]]], start_index: int = 0) -> None:
        """Set queue with track list (for backward compatibility)"""
        # Clear existing queue
        self.queue.clear()
        # Add new tracks (assuming track_list items are file paths or track info)
        for track in track_list:
            if isinstance(track, dict):
                self.queue.add_track(track)
            else:
                # Assume it's a filepath
                self.queue.add_track({'filepath': track})
        if self.queue.tracks and start_index >= 0:
            self.queue.current_index = min(start_index, len(self.queue.tracks) - 1)
