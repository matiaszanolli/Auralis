# -*- coding: utf-8 -*-

"""
Auralis Library Manager - Backward Compatibility Wrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module maintains backward compatibility while the actual implementation
has been refactored into repository modules under auralis/library/repositories/

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

DEPRECATED: Use repository classes directly for new code
"""

import os
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .models import Base, Track, Album, Artist, Genre, Playlist
from .migrations import check_and_migrate_database
from .repositories import (
    TrackRepository,
    AlbumRepository,
    ArtistRepository,
    PlaylistRepository,
    StatsRepository,
    FingerprintRepository,
    QueueRepository
)
from .cache import cached_query, invalidate_cache, get_cache_stats
from ..utils.logging import info, warning, error


class LibraryManager:
    """
    High-level library management system for Auralis

    This class now acts as a facade to the repository layer.
    For new code, consider using repositories directly.

    Provides API for:
    - Database operations
    - Track/playlist management
    - Search and filtering
    - Statistics and analysis
    """

    def __init__(self, database_path: Optional[str] = None) -> None:
        """
        Initialize library manager

        Args:
            database_path: Path to SQLite database file
        """
        if database_path is None:
            # Default to user's music directory
            music_dir = Path.home() / "Music" / "Auralis"
            music_dir.mkdir(parents=True, exist_ok=True)
            database_path = str(music_dir / "auralis_library.db")

        self.database_path = database_path

        # Check and migrate database before initializing engine
        info("Checking database version...")
        if not check_and_migrate_database(database_path, auto_backup=True):
            error("Database migration failed!")
            raise Exception("Failed to migrate database to current version")

        # CRITICAL: Configure SQLite for safe, frequent fingerprint writes
        # WAL mode + synchronous=NORMAL enables fast writes with durability guarantees
        # AGGRESSIVE: Longer timeout for higher contention with 32 workers
        connect_args = {
            'timeout': 60,  # Increased from 30s (2x workers = 2x timeout)
            'check_same_thread': False,
        }

        # AGGRESSIVE: Increase connection pool size to support 32 concurrent workers
        # Each worker may need its own connection during database operations
        self.engine = create_engine(
            f"sqlite:///{database_path}",
            echo=False,
            connect_args=connect_args,
            pool_pre_ping=True,  # Verify connections before use
            pool_size=32,  # Match number of workers (was 5 default)
            max_overflow=32,  # Allow up to 32 additional connections if needed
        )

        # Configure SQLite pragmas for reliable fingerprinting persistence
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Set SQLite pragmas for safe, fast writes"""
            cursor = dbapi_connection.cursor()
            # Enable Write-Ahead Logging for better concurrent write performance
            cursor.execute("PRAGMA journal_mode=WAL")
            # Set synchronous to NORMAL (safer than OFF, faster than FULL)
            # Ensures fingerprints are durably written to WAL before returning
            cursor.execute("PRAGMA synchronous=NORMAL")
            # AGGRESSIVE: Increase cache size to 256MB for 4x faster queries
            # With 32 workers all querying database, larger cache reduces disk I/O
            cursor.execute("PRAGMA cache_size=-262144")  # 256MB cache (4x from 64MB)
            # Optimize for frequent writes
            cursor.execute("PRAGMA temp_store=MEMORY")
            # Foreign key enforcement for data integrity
            cursor.execute("PRAGMA foreign_keys=ON")
            # Increase max page count for larger working set
            cursor.execute("PRAGMA max_page_count=1073741823")  # ~4GB max database
            cursor.close()

        self.SessionLocal = sessionmaker(bind=self.engine)

        # Create tables if they don't exist (for fresh databases)
        Base.metadata.create_all(self.engine)

        # Initialize repositories (album repository first for artwork extraction)
        self.albums = AlbumRepository(self.SessionLocal)
        self.tracks = TrackRepository(self.SessionLocal, album_repository=self.albums)
        self.artists = ArtistRepository(self.SessionLocal)
        self.playlists = PlaylistRepository(self.SessionLocal)
        self.stats = StatsRepository(self.SessionLocal)
        self.fingerprints = FingerprintRepository(self.SessionLocal)
        self.queue = QueueRepository(self.SessionLocal)

        # Thread-safe locking for delete operations (prevents race conditions)
        self._delete_lock = threading.RLock()
        # Track IDs that have been successfully deleted (for race condition prevention)
        self._deleted_track_ids: Set[int] = set()

        # Clean up incomplete fingerprints from interrupted sessions (crash recovery)
        self._cleanup_incomplete_fingerprints()

        info(f"Auralis Library Manager initialized: {database_path}")

    def _cleanup_incomplete_fingerprints(self) -> None:
        """
        Clean up incomplete fingerprints from interrupted fingerprinting sessions.

        When workers claim tracks, they create placeholder fingerprints (with LUFS=-100)
        to prevent race conditions. If the system crashes before processing completes,
        these placeholders remain in the database and must be cleaned up on restart
        so those tracks can be re-processed.

        This is CRITICAL for resumable large-scale fingerprinting jobs.
        """
        try:
            # Use repository pattern for database operation
            count = self.fingerprints.cleanup_incomplete_fingerprints()

            if count > 0:
                warning(
                    f"Cleaned up {count} incomplete fingerprints from "
                    f"interrupted session. These tracks will be re-processed."
                )
            else:
                info("No incomplete fingerprints found - resuming clean session")

        except Exception as e:
            error(f"Error cleaning up incomplete fingerprints: {e}")

    def get_session(self) -> Any:
        """Get a new database session"""
        return self.SessionLocal()

    # Track operations (delegate to TrackRepository)
    def add_track(self, track_info: Dict[str, Any]) -> Optional[Track]:
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

    def get_track(self, track_id: int) -> Optional[Track]:
        """Get track by ID"""
        return self.tracks.get_by_id(track_id)

    def get_track_by_path(self, filepath: str) -> Optional[Track]:
        """Get track by file path"""
        return self.tracks.get_by_path(filepath)

    def get_track_by_filepath(self, filepath: str) -> Optional[Track]:
        """Get track by file path (alias)"""
        return self.tracks.get_by_filepath(filepath)

    def update_track_by_filepath(self, filepath: str, track_info: Dict[str, Any]) -> Optional[Track]:
        """Update track by filepath"""
        return self.tracks.update_by_filepath(filepath, track_info)

    @cached_query(ttl=60)
    def search_tracks(self, query: str, limit: int = 50, offset: int = 0) -> Tuple[List[Track], int]:
        """Search tracks by title, artist, album, or genre

        Returns:
            Tuple of (matching tracks, total count)
        """
        return self.tracks.search(query, limit, offset)

    @cached_query(ttl=300)
    def get_tracks_by_genre(self, genre_name: str, limit: int = 100) -> List[Track]:
        """Get tracks by genre"""
        return self.tracks.get_by_genre(genre_name, limit)

    @cached_query(ttl=300)
    def get_tracks_by_artist(self, artist_name: str, limit: int = 100) -> List[Track]:
        """Get tracks by artist"""
        return self.tracks.get_by_artist(artist_name, limit)

    @cached_query(ttl=180)
    def get_recent_tracks(self, limit: int = 50, offset: int = 0) -> Tuple[List[Track], int]:
        """Get recently added tracks (cached for 3 minutes)

        Returns:
            Tuple of (track list, total count)
        """
        return self.tracks.get_recent(limit, offset)

    @cached_query(ttl=120)
    def get_popular_tracks(self, limit: int = 50, offset: int = 0) -> Tuple[List[Track], int]:
        """Get most played tracks (cached for 2 minutes)

        Returns:
            Tuple of (track list, total count)
        """
        return self.tracks.get_popular(limit, offset)

    @cached_query(ttl=180)
    def get_favorite_tracks(self, limit: int = 50, offset: int = 0) -> Tuple[List[Track], int]:
        """Get favorite tracks (cached for 3 minutes)

        Returns:
            Tuple of (track list, total count)
        """
        return self.tracks.get_favorites(limit, offset)

    @cached_query(ttl=300)
    def get_all_tracks(self, limit: int = 50, offset: int = 0, order_by: str = 'title') -> Tuple[List[Track], int]:
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

    def find_reference_tracks(self, track: Track, limit: int = 5) -> List[Track]:
        """Find similar tracks for reference"""
        return self.tracks.find_similar(track, limit)

    # Playlist operations (delegate to PlaylistRepository)
    def create_playlist(self, name: str, description: str = "", track_ids: Optional[List[int]] = None) -> Optional[Playlist]:
        """Create a new playlist"""
        return self.playlists.create(name, description, track_ids or [])

    def get_playlist(self, playlist_id: int) -> Optional[Playlist]:
        """Get playlist by ID"""
        return self.playlists.get_by_id(playlist_id)

    def get_all_playlists(self) -> List[Playlist]:
        """Get all playlists"""
        return self.playlists.get_all()

    def update_playlist(self, playlist_id: int, update_data: Dict[str, Any]) -> bool:
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
    def get_library_stats(self) -> Dict[str, Any]:
        """Get library statistics"""
        return self.stats.get_library_stats()

    # Scanner operations (delegate to Scanner)
    def scan_directories(self, directories: List[str], **kwargs: Any) -> Any:
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
    def get_recommendations(self, track: Track, limit: int = 10) -> List[Track]:
        """Get track recommendations based on listening history"""
        # Simplified recommendation - just return similar tracks
        return self.tracks.find_similar(track, limit)

    # Cache management
    def get_cache_stats(self) -> Dict[str, Any]:
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
            # Check if this track has already been deleted by another thread
            if track_id in self._deleted_track_ids:
                return False

            # Use repository for database operation (repositories handle sessions)
            try:
                success = self.tracks.delete(track_id)

                if success:
                    # Mark this track as deleted to prevent any issues
                    self._deleted_track_ids.add(track_id)

                    # Invalidate queries that might include the deleted track
                    invalidate_cache('get_all_tracks', 'get_track', 'search_tracks',
                                     'get_favorite_tracks', 'get_recent_tracks', 'get_popular_tracks')

                    info(f"Deleted track {track_id}")

                return success
            except Exception as e:
                error(f"Failed to delete track {track_id}: {e}")
                return False

    def update_track(self, track_id: int, track_info: Dict[str, Any]) -> Optional[Track]:
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
