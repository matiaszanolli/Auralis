"""
Auralis Library Manager - Backward Compatibility Wrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module maintains backward compatibility while the actual implementation
lives in :class:`~auralis.library.database.LibraryDatabase` (bootstrap, engine,
sessions, scan slots, lifecycle) and the repository modules under
auralis/library/repositories/ (queries).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

DEPRECATED: Use LibraryDatabase + RepositoryFactory directly for new code.
"""

import warnings
from pathlib import Path
from typing import Any

from ..utils.logging import error, info
from .cache import cached_query, get_cache_stats, invalidate_cache
from .database import LibraryDatabase
from .models import Playlist, Track


class LibraryManager(LibraryDatabase):
    """
    ⚠️ DEPRECATED: Use ``LibraryDatabase`` + ``RepositoryFactory`` for new code.

    This class is maintained for backward compatibility only. It adds nothing
    but a legacy query facade — every method below forwards to a repository —
    on top of :class:`LibraryDatabase`, which owns the engine, sessions,
    migrations, scan slots and shutdown.

    For new code:

    ```python
    from auralis.library import LibraryDatabase

    db = LibraryDatabase()
    tracks, total = db.repositories.tracks.get_all(limit=50)
    ```

    Deprecated since v1.1.0; scheduled for removal in v2.0.0. As of #4619 it is
    no longer constructed anywhere on the production startup path — the backend
    and the artwork CLI build a ``LibraryDatabase`` instead — so removing it now
    only requires migrating the remaining test call sites off the legacy facade.

    Backward Compatibility:
    - All existing LibraryManager methods continue to work
    - __init__() emits a DeprecationWarning guiding users to the replacement
    - See MIGRATION_GUIDE.md for upgrade instructions

    Legacy API:
    - Track operations: add_track(), get_track(), search_tracks()
    - Playlist operations: create_playlist(), add_track_to_playlist()
    - Statistics: get_library_stats(), record_track_play()
    - Scanning: scan_directories()

    Query cache:
        The ``@cached_query`` methods below are the *only* users of
        ``auralis.library.cache``. Nothing in production reads through them
        any more, so the cache — and the invalidation calls paired with it —
        are live for legacy callers only.
    """

    def __init__(self, database_path: str | None = None) -> None:
        """
        Initialize library manager (deprecated - use LibraryDatabase instead).

        Args:
            database_path: Path to SQLite database file
        """
        # Emit deprecation warning on initialization
        warnings.warn(
            "LibraryManager is deprecated. Use LibraryDatabase (and its "
            "`repositories` RepositoryFactory) instead. "
            "See MIGRATION_GUIDE.md for migration instructions. "
            "This class will be removed in v2.0.0.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(database_path)

    # Track operations (delegate to TrackRepository)
    def add_track(self, track_info: dict[str, Any]) -> Track | None:
        """
        Add a track to the library with file path validation

        Args:
            track_info: Dictionary containing track metadata including filepath

        Returns:
            Track object if successful, None otherwise

        Raises:
            FileNotFoundError: If the track file does not exist
            ValueError: If no filepath provided in track_info
        """
        # Validate filepath exists before adding to database
        if 'filepath' not in track_info:
            raise ValueError("track_info must contain 'filepath' key")

        filepath = track_info['filepath']
        if not Path(filepath).exists():
            raise FileNotFoundError(f"Audio file not found: {filepath}")

        track = self.tracks.add(track_info)
        if track:
            # Invalidate queries that list tracks
            invalidate_cache('get_all_tracks', 'search_tracks', 'get_recent_tracks')
        return track

    def get_track(self, track_id: int) -> Track | None:
        """Get track by ID"""
        return self.tracks.get_by_id(track_id)

    # #4621: get_track_by_path()/get_track_by_filepath() removed — three names
    # for one lookup, none of them used by production code. Call
    # ``self.tracks.get_by_path(filepath)`` (the canonical repository method)
    # directly, as queue_service.py already does.

    def update_track_by_filepath(self, filepath: str, track_info: dict[str, Any]) -> Track | None:
        """Update track by filepath"""
        return self.tracks.update_by_filepath(filepath, track_info)

    @cached_query(ttl=60)
    def search_tracks(self, query: str, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """Search tracks by title, artist, album, or genre

        Returns:
            Tuple of (matching tracks, total count)
        """
        return self.tracks.search(query, limit, offset)

    @cached_query(ttl=300)
    def get_tracks_by_genre(self, genre_name: str, limit: int = 100) -> list[Track]:
        """Get tracks by genre"""
        return self.tracks.get_by_genre(genre_name, limit)

    @cached_query(ttl=300)
    def get_tracks_by_artist(self, artist_name: str, limit: int = 100) -> list[Track]:
        """Get tracks by artist"""
        return self.tracks.get_by_artist(artist_name, limit)

    @cached_query(ttl=180)
    def get_recent_tracks(self, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """Get recently added tracks (cached for 3 minutes)

        Returns:
            Tuple of (track list, total count)
        """
        return self.tracks.get_recent(limit, offset)

    @cached_query(ttl=120)
    def get_popular_tracks(self, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """Get most played tracks (cached for 2 minutes)

        Returns:
            Tuple of (track list, total count)
        """
        return self.tracks.get_popular(limit, offset)

    @cached_query(ttl=180)
    def get_favorite_tracks(self, limit: int = 50, offset: int = 0) -> tuple[list[Track], int]:
        """Get favorite tracks (cached for 3 minutes)

        Returns:
            Tuple of (track list, total count)
        """
        return self.tracks.get_favorites(limit, offset)

    @cached_query(ttl=300)
    def get_all_tracks(self, limit: int = 50, offset: int = 0, order_by: str = 'title') -> tuple[list[Track], int]:
        """Get all tracks with pagination (cached for 5 minutes)

        Args:
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip
            order_by: Column to order by

        Returns:
            Tuple of (tracks list, total count)
        """
        return self.tracks.get_all(limit, offset, order_by)

    def record_track_play(self, track_id: int) -> None:
        """Record that a track was played"""
        self.tracks.record_play(track_id)
        # Invalidate queries affected by play count/last_played changes
        invalidate_cache('get_popular_tracks', 'get_recent_tracks', 'get_all_tracks', 'get_track')

    def set_track_favorite(self, track_id: int, favorite: bool = True) -> None:
        """Set track favorite status"""
        self.tracks.set_favorite(track_id, favorite)
        # Only invalidate favorite-related queries
        invalidate_cache('get_favorite_tracks')

    def find_reference_tracks(self, track: Track, limit: int = 5) -> list[Track]:
        """Find similar tracks for reference"""
        return self.tracks.find_similar(track, limit)

    # Playlist operations (delegate to PlaylistRepository)
    def create_playlist(self, name: str, description: str = "", track_ids: list[int] | None = None) -> Playlist | None:
        """Create a new playlist"""
        return self.playlists.create(name, description, track_ids or [])

    def get_playlist(self, playlist_id: int) -> Playlist | None:
        """Get playlist by ID"""
        return self.playlists.get_by_id(playlist_id)

    def get_all_playlists(self, limit: int = 200, offset: int = 0) -> list[Playlist]:
        """Get a page of playlists

        Note:
            #4554: ``PlaylistRepository.get_all`` is paginated and now returns
            ``(playlists, total)``. This convenience wrapper keeps its
            list-returning shape and defaults to the API's maximum page size;
            callers that need to walk a very large collection should page
            through the repository directly.
        """
        playlists, _total = self.playlists.get_all(limit=limit, offset=offset)
        return playlists

    def update_playlist(self, playlist_id: int, update_data: dict[str, Any]) -> bool:
        """Update playlist"""
        return self.playlists.update(playlist_id, update_data)

    def delete_playlist(self, playlist_id: int) -> bool:
        """Delete playlist"""
        return self.playlists.delete(playlist_id)

    def add_track_to_playlist(self, playlist_id: int, track_id: int) -> bool:
        """Add track to playlist"""
        return self.playlists.add_track(playlist_id, track_id)

    def remove_track_from_playlist(self, playlist_id: int, track_id: int) -> bool:
        """Remove track from playlist"""
        return self.playlists.remove_track(playlist_id, track_id)

    def clear_playlist(self, playlist_id: int) -> bool:
        """Remove all tracks from playlist"""
        return self.playlists.clear(playlist_id)

    # Statistics operations (delegate to StatsRepository)
    def get_library_stats(self) -> dict[str, Any]:
        """Get library statistics"""
        return self.stats.get_library_stats()

    # Scanner operations (delegate to Scanner)
    def scan_directories(self, directories: list[str], **kwargs: Any) -> Any:
        """Scan directories for audio files"""
        from .scanner import LibraryScanner
        scanner = LibraryScanner(self)
        return scanner.scan_directories(directories, **kwargs)

    def scan_single_directory(self, directory: str, **kwargs: Any) -> Any:
        """Scan single directory for audio files"""
        from .scanner import LibraryScanner
        scanner = LibraryScanner(self)
        return scanner.scan_directories([directory], **kwargs)

    # Cleanup operations
    def cleanup_library(self) -> None:
        """Remove tracks with missing files (uses repository pattern)."""
        try:
            # Use repository pattern for database operation
            removed_count = self.tracks.cleanup_missing_files()
            info(f"Removed {removed_count} tracks with missing files")

        except Exception as e:
            error(f"Failed to cleanup library: {e}")

    # Recommendations (could be moved to dedicated recommendation service)
    def get_recommendations(self, track: Track, limit: int = 10) -> list[Track]:
        """Get track recommendations based on listening history"""
        # Simplified recommendation - just return similar tracks
        return self.tracks.find_similar(track, limit)

    # Cache management
    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics for performance monitoring.

        Returns:
            Dictionary with cache stats including hits, misses, size, hit_rate
        """
        return get_cache_stats()

    def clear_cache(self) -> None:
        """Clear all cached query results"""
        invalidate_cache()
        info("Cache cleared")

    def invalidate_track_caches(self) -> None:
        """Invalidate all track-related caches (after adding/removing tracks)"""
        invalidate_cache('get_recent_tracks')
        invalidate_cache('get_all_tracks')
        invalidate_cache('search_tracks')
        invalidate_cache('get_favorite_tracks')
        invalidate_cache('get_popular_tracks')

    def delete_track(self, track_id: int) -> bool:
        """
        Delete a track and invalidate caches (thread-safe with cache invalidation).

        Args:
            track_id: Track ID to delete

        Returns:
            True if deleted, False if not found or already deleted

        Notes:
            - Uses mutual exclusion lock to prevent race conditions
            - Only one delete operation per track ID can succeed
            - Multiple concurrent deletes will serialize safely
            - Delegates DB operation to TrackRepository.delete()
            - Preserves cache invalidation after successful deletion
        """
        with self._delete_lock:
            # Use repository for database operation (repositories handle sessions)
            # The DB itself prevents double-deletion - if track doesn't exist, returns False
            try:
                # Pre-invalidate: evict any cached entry BEFORE the DB row is removed so
                # that no concurrent reader can obtain a stale object whose row is already
                # gone.  A reader that misses the cache between here and the commit will
                # hit the DB and see the row still present — that is safe.
                invalidate_cache('get_all_tracks', 'get_track', 'search_tracks',
                                 'get_favorite_tracks', 'get_recent_tracks', 'get_popular_tracks')

                success = self.tracks.delete(track_id)

                if success:
                    # Post-invalidate: evict any entry that a concurrent reader may have
                    # re-populated between the pre-invalidate and the commit (#2432).
                    invalidate_cache('get_all_tracks', 'get_track', 'search_tracks',
                                     'get_favorite_tracks', 'get_recent_tracks', 'get_popular_tracks')

                    info(f"Deleted track {track_id}")

                return success
            except Exception as e:
                error(f"Failed to delete track {track_id}: {e}")
                return False

    def update_track(self, track_id: int, track_info: dict[str, Any]) -> Track | None:
        """
        Update a track and invalidate caches

        Args:
            track_id: Track ID to update
            track_info: Dictionary with updated track information

        Returns:
            Updated track or None if not found
        """
        track = self.tracks.update(track_id, track_info)
        if track:
            # Invalidate queries that might show updated metadata
            invalidate_cache('get_track', 'search_tracks', 'get_all_tracks')
        return track
