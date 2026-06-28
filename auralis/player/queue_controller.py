"""
QueueController - Manages playlist queue and track navigation

Responsibilities:
- Queue management (add, remove, navigate)
- Track sequencing (next, previous)
- Shuffle and repeat modes
- Playlist loading
"""

from typing import Any
from collections.abc import Callable

from ..utils.logging import error, info, warning
from .components import QueueManager


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
        library_manager: Any | None = None
    ) -> None:
        """
        Initialize queue controller.

        Args:
            get_repository_factory: Callable that returns RepositoryFactory instance (REQUIRED)
            library_manager: Deprecated, kept for backward compatibility only
        """
        self.queue: Any = QueueManager()
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
    def tracks(self) -> list[dict[str, Any]]:
        """Get list of tracks in queue (already locked via QueueManager.get_queue)."""
        return self.queue.get_queue()  # type: ignore[no-any-return]

    # #3783: route every read/write of QueueManager attributes through the
    # _lock that QueueManager itself uses for its mutators. CPython's GIL
    # kept simple-attribute reads torn-free historically, but free-threaded
    # builds (PEP 703) need explicit synchronization here, and the previous
    # raw `self.queue.current_index` accesses violated the QueueManager
    # invariant that the lock protects the full state transition.

    @property
    def current_index(self) -> int:
        """Get current track index (#3783: locked via QueueManager._lock)."""
        with self.queue._lock:
            return self.queue.current_index  # type: ignore[no-any-return]

    @current_index.setter
    def current_index(self, value: int) -> None:
        """Set current track index (#3783: locked)."""
        with self.queue._lock:
            self.queue.current_index = value

    @property
    def shuffle_enabled(self) -> bool:
        """Get shuffle mode status (#3783: locked)."""
        with self.queue._lock:
            return self.queue.shuffle_enabled  # type: ignore[no-any-return]

    @shuffle_enabled.setter
    def shuffle_enabled(self, value: bool) -> None:
        """Set shuffle mode (#3783: locked)."""
        with self.queue._lock:
            self.queue.shuffle_enabled = value

    @property
    def repeat_enabled(self) -> bool:
        """Get repeat mode status (#3783: locked)."""
        with self.queue._lock:
            return self.queue.repeat_enabled  # type: ignore[no-any-return]

    @repeat_enabled.setter
    def repeat_enabled(self, value: bool) -> None:
        """Set repeat mode (#3783: locked)."""
        with self.queue._lock:
            self.queue.repeat_enabled = value

    def add_tracks(self, track_list: list[dict[str, Any]]) -> None:
        """Add multiple tracks to queue"""
        for track_info in track_list:
            self.add_track(track_info)

    def clear(self) -> None:
        """Clear all tracks from queue (backward compatibility alias)"""
        self.clear_queue()

    def next_track(self) -> dict[str, Any] | None:
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

    def advance_if_next_matches(self, expected: dict[str, Any]) -> dict[str, Any] | None:
        """
        #3352 (PTS-9): atomic peek+advance for gapless prebuffer commit.

        Used by `GaplessPlaybackEngine.advance_with_prebuffer` to close the
        TOCTOU window between the peek that chose what to load and the
        next_track() that committed the queue advance. Returns the advanced
        track on success, None if the queue mutated between peek and commit
        so the slot no longer holds the expected track.
        """
        advanced: Any = self.queue.advance_if_next_matches(expected)
        if advanced:
            info(f"Advancing to next track: {advanced.get('title', 'Unknown')}")
        return advanced  # type: ignore[no-any-return]

    def previous_track(self) -> dict[str, Any] | None:
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

    def rollback_index(self, saved_index: int) -> None:
        """#3668: locked rollback of the queue's current_index for use by
        previous_track() when a file load fails."""
        self.queue.rollback_index(saved_index)

    def snapshot_index(self) -> int:
        """#3726: atomic locked read of the queue's current_index. Use as
        the rollback baseline in previous_track() so a concurrent
        next_track/remove_track/reorder_tracks cannot make the saved
        index stale relative to the queue contents."""
        return self.queue.snapshot_index()

    def get_current_track(self) -> dict[str, Any] | None:
        """Get current track from queue"""
        return self.queue.get_current_track()  # type: ignore[no-any-return]

    def peek_next_track(self) -> dict[str, Any] | None:
        """
        Peek at next track without advancing queue.

        Useful for prebuffering the next track.
        """
        return self.queue.peek_next()  # type: ignore[no-any-return]

    def add_track(self, track_info: dict[str, Any]) -> None:
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

            # Snapshot playlist.tracks before iteration so a concurrent
            # queue modification cannot cause RuntimeError mid-loop (fixes #2492).
            for track in list(playlist.tracks):
                track_info = track.to_dict()
                self.queue.add_track(track_info)

            # Clamp + write current_index atomically (#4098). The length read and
            # the write must happen under one held lock (RLock, re-entrant) so a
            # concurrent queue shrink can't leave the index out of bounds in the
            # gap between the snapshot and the write.
            with self.queue._lock:
                track_count = len(self.queue.tracks)
                if track_count:
                    self.queue.current_index = min(start_index, track_count - 1)

            if track_count:
                info(f"Loaded playlist: {playlist.name} ({track_count} tracks)")
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

    def get_queue_info(self) -> dict[str, Any]:
        """Get detailed queue information as an atomic snapshot (fixes #2470)."""
        return self.queue.get_queue_info()

    def set_shuffle(self, enabled: bool) -> None:
        """Enable/disable shuffle mode"""
        # Route through the locked property setter (#4096) — writing
        # self.queue.shuffle_enabled directly bypassed QueueManager._lock that
        # the shuffle_enabled reader (used by peek_next/next_track) holds.
        self.shuffle_enabled = enabled
        info(f"Shuffle {'enabled' if enabled else 'disabled'}")

    def set_repeat(self, enabled: bool) -> None:
        """Enable/disable repeat mode"""
        # Route through the locked property setter (#4096), as with set_shuffle.
        self.repeat_enabled = enabled
        info(f"Repeat {'enabled' if enabled else 'disabled'}")

    def is_queue_empty(self) -> bool:
        """Check if queue is empty"""
        return self.queue.get_queue_size() == 0

    def has_next_track(self) -> bool:
        """#3692: True iff a subsequent peek_next_track() would return a
        track. Used to gate the auto-advance thread spawn — `is_queue_empty()`
        returns False at end-of-queue if the current (last) track is still
        in the queue, so it can't tell us whether there's anything to
        advance TO."""
        return self.queue.peek_next() is not None

    def get_track_count(self) -> int:
        """Get number of tracks in queue"""
        return self.queue.get_queue_size()

    def get_queue_size(self) -> int:
        """Get queue size (alias for get_track_count)"""
        return self.queue.get_queue_size()

    def remove_track(self, index: int) -> bool:
        """Remove track at specified index"""
        return self.queue.remove_track(index)  # type: ignore[no-any-return]

    def get_queue(self) -> list[dict[str, Any]]:
        """Get full queue as list"""
        return self.queue.get_queue()  # type: ignore[no-any-return]

    def shuffle(self) -> None:
        """Shuffle the queue, keeping the current track in place."""
        self.queue.shuffle()

    def unshuffle(self) -> bool:
        """Restore the pre-shuffle queue order. Returns True if restored."""
        return self.queue.unshuffle()

    def reorder_tracks(self, new_order: list[int]) -> bool:
        """Reorder tracks according to new index order"""
        return self.queue.reorder_tracks(new_order)  # type: ignore[no-any-return]

    def set_queue(self, track_list: list[str | dict[str, Any]], start_index: int = 0) -> None:
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
        # Clamp + write current_index atomically under one held lock (#4098) to
        # avoid the TOCTOU between reading the length and writing the index.
        with self.queue._lock:
            track_count = len(self.queue.tracks)
            if track_count and start_index >= 0:
                self.queue.current_index = min(start_index, track_count - 1)
