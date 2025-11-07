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
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base, Track, Album, Artist, Genre, Playlist
from .migrations import check_and_migrate_database
from .repositories import (
    TrackRepository,
    AlbumRepository,
    ArtistRepository,
    PlaylistRepository,
    StatsRepository,
    FingerprintRepository
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

    def __init__(self, database_path: Optional[str] = None):
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

        self.engine = create_engine(f"sqlite:///{database_path}", echo=False)
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

        info(f"Auralis Library Manager initialized: {database_path}")

    def get_session(self):
        """Get a new database session"""
        return self.SessionLocal()

    # Track operations (delegate to TrackRepository)
    def add_track(self, track_info: Dict[str, Any]) -> Optional[Track]:
        """Add a track to the library"""
        track = self.tracks.add(track_info)
        if track:
            # Cache keys are hashed, so pattern matching doesn't work
            # Clear entire cache to ensure consistency
            invalidate_cache()  # Clear all
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

    @cached_query(ttl=60)  # Cache for 1 minute (search results change frequently)
    def search_tracks(self, query: str, limit: int = 50, offset: int = 0) -> List[Track]:
        """Search tracks by title, artist, album, or genre"""
        return self.tracks.search(query, limit, offset)

    @cached_query(ttl=300)  # Cache for 5 minutes
    def get_tracks_by_genre(self, genre_name: str, limit: int = 100) -> List[Track]:
        """Get tracks by genre"""
        return self.tracks.get_by_genre(genre_name, limit)

    @cached_query(ttl=300)  # Cache for 5 minutes
    def get_tracks_by_artist(self, artist_name: str, limit: int = 100) -> List[Track]:
        """Get tracks by artist"""
        return self.tracks.get_by_artist(artist_name, limit)

    @cached_query(ttl=180)  # Cache for 3 minutes (recent tracks don't change often)
    def get_recent_tracks(self, limit: int = 50, offset: int = 0) -> List[Track]:
        """Get recently added tracks (cached for 3 minutes)"""
        return self.tracks.get_recent(limit, offset)

    @cached_query(ttl=120)  # Cache for 2 minutes (play counts change more frequently)
    def get_popular_tracks(self, limit: int = 50, offset: int = 0) -> List[Track]:
        """Get most played tracks (cached for 2 minutes)"""
        return self.tracks.get_popular(limit, offset)

    @cached_query(ttl=180)  # Cache for 3 minutes
    def get_favorite_tracks(self, limit: int = 50, offset: int = 0) -> List[Track]:
        """Get favorite tracks (cached for 3 minutes)"""
        return self.tracks.get_favorites(limit, offset)

    @cached_query(ttl=300)  # Cache for 5 minutes
    def get_all_tracks(self, limit: int = 50, offset: int = 0, order_by: str = 'title') -> tuple[List[Track], int]:
        """Get all tracks with pagination (cached for 5 minutes)

        Args:
            limit: Maximum number of tracks to return
            offset: Number of tracks to skip
            order_by: Column to order by

        Returns:
            Tuple of (tracks list, total count)
        """
        return self.tracks.get_all(limit, offset, order_by)

    def record_track_play(self, track_id: int):
        """Record that a track was played"""
        self.tracks.record_play(track_id)
        # Cache keys are hashed, so pattern matching doesn't work
        # Clear entire cache to ensure consistency
        invalidate_cache()  # Clear all

    def set_track_favorite(self, track_id: int, favorite: bool = True):
        """Set track favorite status"""
        self.tracks.set_favorite(track_id, favorite)
        # Cache keys are hashed, so pattern matching doesn't work
        # Clear entire cache to ensure consistency
        invalidate_cache()  # Clear all

    def find_reference_tracks(self, track: Track, limit: int = 5) -> List[Track]:
        """Find similar tracks for reference"""
        return self.tracks.find_similar(track, limit)

    # Playlist operations (delegate to PlaylistRepository)
    def create_playlist(self, name: str, description: str = "", track_ids: List[int] = None) -> Optional[Playlist]:
        """Create a new playlist"""
        return self.playlists.create(name, description, track_ids)

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
    def scan_directories(self, directories: List[str], **kwargs):
        """Scan directories for audio files"""
        from .scanner import LibraryScanner
        scanner = LibraryScanner(self)
        return scanner.scan_directories(directories, **kwargs)

    def scan_single_directory(self, directory: str, **kwargs):
        """Scan single directory for audio files"""
        from .scanner import LibraryScanner
        scanner = LibraryScanner(self)
        return scanner.scan_directory(directory, **kwargs)

    # Cleanup operations
    def cleanup_library(self):
        """Remove tracks with missing files"""
        session = self.get_session()
        try:
            tracks = session.query(Track).all()
            removed_count = 0

            for track in tracks:
                if not os.path.exists(track.filepath):
                    session.delete(track)
                    removed_count += 1

            session.commit()
            info(f"Removed {removed_count} tracks with missing files")

        except Exception as e:
            session.rollback()
            error(f"Failed to cleanup library: {e}")
        finally:
            session.close()

    # Recommendations (could be moved to dedicated recommendation service)
    def get_recommendations(self, track: Track, limit: int = 10) -> List[Track]:
        """Get track recommendations based on listening history"""
        # Simplified recommendation - just return similar tracks
        return self.tracks.find_similar(track, limit)

    # Cache management
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics for performance monitoring.

        Returns:
            Dictionary with cache stats including hits, misses, size, hit_rate
        """
        return get_cache_stats()

    def clear_cache(self):
        """Clear all cached query results"""
        invalidate_cache()
        info("Cache cleared")

    def invalidate_track_caches(self):
        """Invalidate all track-related caches (after adding/removing tracks)"""
        invalidate_cache('get_recent_tracks')
        invalidate_cache('get_all_tracks')
        invalidate_cache('search_tracks')
        invalidate_cache('get_favorite_tracks')
        invalidate_cache('get_popular_tracks')

    def delete_track(self, track_id: int) -> bool:
        """
        Delete a track and invalidate caches

        Args:
            track_id: Track ID to delete

        Returns:
            True if deleted, False if not found
        """
        result = self.tracks.delete(track_id)
        if result:
            # Cache keys are hashed, so pattern matching doesn't work
            # Clear entire cache to ensure consistency
            invalidate_cache()  # Clear all
        return result

    def update_track(self, track_id: int, track_info: dict) -> Optional[Track]:
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
            # Cache keys are hashed, so pattern matching doesn't work
            # Clear entire cache to ensure consistency
            invalidate_cache()  # Clear all
        return track
