"""
Bulk queue population for QueueController (split from queue_controller.py,
#5836): library lookups, playlist loading and ``set_queue``. Each replaces the
queue contents as one atomic unit under the queue's lock (#5355) and notifies
the change listener after releasing it.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

from ..utils.logging import error, info, warning
from .components import QueueManager
from .repository_access import resolve_repository_factory


class QueueLoadingMixin:
    """Loads tracks into the queue; the queue and listener plumbing live on QueueController."""

    queue: QueueManager
    get_repository_factory: Callable[[], Any]

    # Provided by QueueController.
    add_track: "Callable[[dict[str, Any]], None]"
    _notify_changed: "Callable[[], None]"

    def add_tracks(self, track_list: list[dict[str, Any]]) -> None:
        """Add multiple tracks to queue"""
        for track_info in track_list:
            self.add_track(track_info)

    def add_track_from_library(self, track_id: int) -> bool:
        """
        Add a track from library by ID.

        Returns:
            bool: True if successful
        """
        try:
            repos = resolve_repository_factory(self.get_repository_factory)
            track = repos.tracks.get_by_id(track_id)
            if track:
                self.add_track(track.to_dict())
                return True
            return False
        except Exception as e:
            error(f"Failed to add track from library: {e}")
            return False

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
            repos = resolve_repository_factory(self.get_repository_factory)
            playlist = repos.playlists.get_by_id(playlist_id)
            if not playlist:
                error(f"Playlist not found: {playlist_id}")
                return False

            # #5355: hold the queue's lock across the whole clear-repopulate-
            # and-index-write sequence as one atomic unit — RLock, so the
            # per-call clear()/add_track() acquisitions below are cheap
            # re-entries, not a new contention point. Without this, a reader
            # (has_next_track()/peek_next_track(), from the audio thread's
            # end-of-track check or the gapless prebuffer thread) could
            # observe a momentarily empty queue between clear() and the
            # repopulating add_track() calls.
            # Snapshot playlist.tracks before iteration so a concurrent queue
            # modification cannot cause RuntimeError mid-loop (fixes #2492), and
            # serialise every row before taking the lock: to_dict() is O(n) work
            # the audio thread must not wait behind (#6084).
            track_infos = [track.to_dict() for track in list(playlist.tracks)]
            with self.queue._lock:
                self.queue.clear()
                for track_info in track_infos:
                    self.queue.add_track(track_info)

                # Clamp + write current_index atomically (#4098): the length
                # read and the write happen under the same held lock so a
                # concurrent queue shrink can't leave the index out of bounds
                # in the gap between the snapshot and the write.
                track_count = len(self.queue.tracks)
                if track_count:
                    self.queue.current_index = min(start_index, track_count - 1)
            self._notify_changed()

            if track_count:
                info(f"Loaded playlist: {playlist.name} ({track_count} tracks)")
                return True

            warning(f"Playlist is empty: {playlist.name}")
            return False

        except Exception as e:
            error(f"Failed to load playlist: {e}")
            return False

    def set_queue(self, track_list: list[str | dict[str, Any]], start_index: int = 0) -> None:
        """Replace the queue with ``track_list`` (filepaths or track dicts) and select ``start_index``."""
        # #5355: hold the queue's lock across the whole clear-repopulate-and-
        # index-write sequence as one atomic unit — see load_playlist() for
        # the full rationale (same pattern, same fix).
        with self.queue._lock:
            # Clear existing queue
            self.queue.clear()
            # Add new tracks (assuming track_list items are file paths or track info)
            for track in track_list:
                if isinstance(track, dict):
                    self.queue.add_track(track)
                else:
                    # Assume it's a filepath
                    self.queue.add_track({'filepath': track})
            # Clamp + write current_index atomically (#4098) — the length
            # read and the write happen under the same held lock to avoid
            # the TOCTOU between reading the length and writing the index.
            track_count = len(self.queue.tracks)
            if track_count and start_index >= 0:
                self.queue.current_index = min(start_index, track_count - 1)
        self._notify_changed()
