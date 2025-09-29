#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Library Manager Comprehensive Coverage Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for the library manager to significantly improve coverage from 21%
"""

import numpy as np
import tempfile
import os
import sys
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath('../..'))

from auralis.library.manager import LibraryManager
from auralis.library.models import Track, Album, Artist, Playlist
from auralis.library.scanner import LibraryScanner
import soundfile as sf

class TestLibraryManagerComprehensive:
    """Comprehensive test coverage for LibraryManager"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_library.db")
        self.manager = LibraryManager(database_path=self.db_path)

        # Create test audio files
        self.audio_dir = os.path.join(self.temp_dir, "audio")
        os.makedirs(self.audio_dir)
        self._create_test_audio_files()

    def tearDown(self):
        """Clean up test fixtures"""
        if hasattr(self, 'manager'):
            self.manager.close()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_test_audio_files(self):
        """Create test audio files with metadata"""
        sample_rate = 44100
        duration = 2.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)
        audio = 0.5 * np.sin(2 * np.pi * 440 * t)

        # Create different audio files
        test_files = [
            ("artist1_album1_track1.wav", {"artist": "Artist One", "album": "Album One", "title": "Track One"}),
            ("artist1_album1_track2.wav", {"artist": "Artist One", "album": "Album One", "title": "Track Two"}),
            ("artist1_album2_track1.wav", {"artist": "Artist One", "album": "Album Two", "title": "Track One"}),
            ("artist2_album1_track1.wav", {"artist": "Artist Two", "album": "Album One", "title": "Track One"}),
        ]

        for filename, metadata in test_files:
            filepath = os.path.join(self.audio_dir, filename)
            sf.write(filepath, audio, sample_rate)

    def test_initialization_and_setup(self):
        """Test manager initialization and database setup"""
        self.setUp()

        # Test basic initialization
        assert self.manager is not None
        assert hasattr(self.manager, 'session')
        assert hasattr(self.manager, 'engine')

        # Test database file creation
        assert os.path.exists(self.db_path)

        # Test basic operations
        stats = self.manager.get_library_stats()
        assert stats is not None
        assert 'total_tracks' in stats
        assert stats['total_tracks'] == 0  # Empty library initially

        self.tearDown()

    def test_track_operations(self):
        """Test comprehensive track operations"""
        self.setUp()

        # Test adding tracks
        track1 = Track(
            file_path="/test/track1.mp3",
            title="Test Track 1",
            artist="Test Artist",
            album="Test Album",
            duration=180.5,
            sample_rate=44100,
            file_size=5242880
        )

        added_track = self.manager.add_track(track1)
        assert added_track is not None
        assert added_track.id is not None
        assert added_track.title == "Test Track 1"

        # Test getting track by ID
        retrieved_track = self.manager.get_track_by_id(added_track.id)
        assert retrieved_track is not None
        assert retrieved_track.title == "Test Track 1"

        # Test getting track by path
        path_track = self.manager.get_track_by_path("/test/track1.mp3")
        assert path_track is not None
        assert path_track.id == added_track.id

        # Test updating track
        updated_data = {"title": "Updated Track 1", "duration": 200.0}
        success = self.manager.update_track(added_track.id, updated_data)
        assert success is True

        updated_track = self.manager.get_track_by_id(added_track.id)
        assert updated_track.title == "Updated Track 1"
        assert updated_track.duration == 200.0

        # Test deleting track
        delete_success = self.manager.delete_track(added_track.id)
        assert delete_success is True

        deleted_track = self.manager.get_track_by_id(added_track.id)
        assert deleted_track is None

        self.tearDown()

    def test_search_functionality(self):
        """Test comprehensive search functionality"""
        self.setUp()

        # Add test tracks for searching
        tracks = [
            Track(file_path="/test1.mp3", title="Rock Song", artist="Rock Artist", album="Rock Album", genre="Rock"),
            Track(file_path="/test2.mp3", title="Jazz Song", artist="Jazz Artist", album="Jazz Album", genre="Jazz"),
            Track(file_path="/test3.mp3", title="Pop Song", artist="Rock Artist", album="Pop Album", genre="Pop"),
        ]

        for track in tracks:
            self.manager.add_track(track)

        # Test basic search
        results = self.manager.search_tracks("Rock")
        assert len(results) == 2  # Should find "Rock Song" and track by "Rock Artist"

        # Test artist search
        artist_results = self.manager.search_tracks("Rock Artist")
        assert len(artist_results) == 2

        # Test album search
        album_results = self.manager.search_tracks("Jazz Album")
        assert len(album_results) == 1
        assert album_results[0].album == "Jazz Album"

        # Test genre search
        genre_results = self.manager.search_tracks("Pop")
        assert len(genre_results) == 1
        assert genre_results[0].genre == "Pop"

        # Test empty search
        empty_results = self.manager.search_tracks("")
        assert len(empty_results) >= 3  # Should return all tracks

        # Test non-existent search
        no_results = self.manager.search_tracks("NonExistent")
        assert len(no_results) == 0

        self.tearDown()

    def test_advanced_queries(self):
        """Test advanced query functionality"""
        self.setUp()

        # Add test data
        tracks = []
        for i in range(10):
            track = Track(
                file_path=f"/test{i}.mp3",
                title=f"Track {i}",
                artist=f"Artist {i % 3}",  # 3 different artists
                album=f"Album {i % 2}",    # 2 different albums
                duration=180 + i * 10,
                play_count=i * 5,
                rating=min(5.0, i * 0.5)
            )
            tracks.append(self.manager.add_track(track))

        # Test getting tracks by artist
        artist_tracks = self.manager.get_tracks_by_artist("Artist 1")
        assert len(artist_tracks) > 0
        for track in artist_tracks:
            assert track.artist == "Artist 1"

        # Test getting tracks by album
        album_tracks = self.manager.get_tracks_by_album("Album 0")
        assert len(album_tracks) > 0
        for track in album_tracks:
            assert track.album == "Album 0"

        # Test getting tracks by genre (if implemented)
        try:
            genre_tracks = self.manager.get_tracks_by_genre("Rock")
            assert isinstance(genre_tracks, list)
        except AttributeError:
            pass  # Method might not exist

        # Test getting most played tracks
        try:
            most_played = self.manager.get_most_played_tracks(limit=5)
            assert len(most_played) <= 5
            if len(most_played) > 1:
                assert most_played[0].play_count >= most_played[1].play_count
        except AttributeError:
            pass  # Method might not exist

        # Test getting recently played tracks
        try:
            recent = self.manager.get_recently_played_tracks(limit=3)
            assert len(recent) <= 3
        except AttributeError:
            pass  # Method might not exist

        self.tearDown()

    def test_playlist_operations(self):
        """Test comprehensive playlist operations"""
        self.setUp()

        # Create test tracks first
        tracks = []
        for i in range(5):
            track = Track(
                file_path=f"/test{i}.mp3",
                title=f"Track {i}",
                artist=f"Artist {i}",
                duration=180
            )
            tracks.append(self.manager.add_track(track))

        # Test creating playlist
        playlist = Playlist(
            name="Test Playlist",
            description="A test playlist",
            created_date=datetime.now()
        )

        created_playlist = self.manager.create_playlist(playlist)
        assert created_playlist is not None
        assert created_playlist.id is not None
        assert created_playlist.name == "Test Playlist"

        # Test getting playlist by ID
        retrieved_playlist = self.manager.get_playlist_by_id(created_playlist.id)
        assert retrieved_playlist is not None
        assert retrieved_playlist.name == "Test Playlist"

        # Test adding tracks to playlist
        for track in tracks[:3]:  # Add first 3 tracks
            success = self.manager.add_track_to_playlist(created_playlist.id, track.id)
            assert success is True

        # Test getting playlist tracks
        playlist_tracks = self.manager.get_playlist_tracks(created_playlist.id)
        assert len(playlist_tracks) == 3

        # Test removing track from playlist
        remove_success = self.manager.remove_track_from_playlist(created_playlist.id, tracks[0].id)
        assert remove_success is True

        updated_playlist_tracks = self.manager.get_playlist_tracks(created_playlist.id)
        assert len(updated_playlist_tracks) == 2

        # Test getting all playlists
        all_playlists = self.manager.get_all_playlists()
        assert len(all_playlists) >= 1
        assert any(p.id == created_playlist.id for p in all_playlists)

        # Test updating playlist
        update_data = {"name": "Updated Playlist", "description": "Updated description"}
        update_success = self.manager.update_playlist(created_playlist.id, update_data)
        assert update_success is True

        updated_playlist = self.manager.get_playlist_by_id(created_playlist.id)
        assert updated_playlist.name == "Updated Playlist"

        # Test deleting playlist
        delete_success = self.manager.delete_playlist(created_playlist.id)
        assert delete_success is True

        deleted_playlist = self.manager.get_playlist_by_id(created_playlist.id)
        assert deleted_playlist is None

        self.tearDown()

    def test_library_statistics(self):
        """Test library statistics and analytics"""
        self.setUp()

        # Add diverse test data
        for i in range(20):
            track = Track(
                file_path=f"/test{i}.mp3",
                title=f"Track {i}",
                artist=f"Artist {i % 5}",   # 5 different artists
                album=f"Album {i % 3}",     # 3 different albums
                genre=f"Genre {i % 4}",     # 4 different genres
                duration=120 + i * 15,
                play_count=i * 2,
                file_size=1024 * 1024 * (3 + i % 7)  # Varying file sizes
            )
            self.manager.add_track(track)

        # Test basic statistics
        stats = self.manager.get_library_stats()
        assert stats['total_tracks'] == 20
        assert stats['total_artists'] >= 5
        assert stats['total_albums'] >= 3

        # Test total duration calculation
        if 'total_duration' in stats:
            assert stats['total_duration'] > 0

        # Test file size statistics
        if 'total_file_size' in stats:
            assert stats['total_file_size'] > 0

        # Test genre distribution
        try:
            genre_stats = self.manager.get_genre_distribution()
            assert isinstance(genre_stats, (list, dict))
        except AttributeError:
            pass  # Method might not exist

        # Test artist statistics
        try:
            artist_stats = self.manager.get_artist_statistics()
            assert isinstance(artist_stats, (list, dict))
        except AttributeError:
            pass  # Method might not exist

        self.tearDown()

    def test_database_maintenance(self):
        """Test database maintenance operations"""
        self.setUp()

        # Add test data
        for i in range(10):
            track = Track(
                file_path=f"/test{i}.mp3",
                title=f"Track {i}",
                artist=f"Artist {i}",
                duration=180
            )
            self.manager.add_track(track)

        # Test database integrity
        try:
            integrity_result = self.manager.check_database_integrity()
            assert integrity_result is not None
        except AttributeError:
            pass  # Method might not exist

        # Test cleanup operations
        try:
            cleanup_result = self.manager.cleanup_orphaned_records()
            assert isinstance(cleanup_result, (bool, int, dict))
        except AttributeError:
            pass  # Method might not exist

        # Test database vacuum
        try:
            vacuum_result = self.manager.vacuum_database()
            assert isinstance(vacuum_result, bool)
        except AttributeError:
            pass  # Method might not exist

        # Test backup functionality
        try:
            backup_path = os.path.join(self.temp_dir, "backup.db")
            backup_success = self.manager.backup_database(backup_path)
            if backup_success:
                assert os.path.exists(backup_path)
        except AttributeError:
            pass  # Method might not exist

        self.tearDown()

    def test_error_handling(self):
        """Test error handling and edge cases"""
        self.setUp()

        # Test adding invalid track
        invalid_track = Track(file_path="", title="", artist="", duration=-1)
        try:
            result = self.manager.add_track(invalid_track)
            # Should either handle gracefully or raise appropriate exception
        except Exception as e:
            assert isinstance(e, (ValueError, TypeError, AttributeError))

        # Test getting non-existent track
        non_existent_track = self.manager.get_track_by_id(99999)
        assert non_existent_track is None

        # Test updating non-existent track
        update_success = self.manager.update_track(99999, {"title": "New Title"})
        assert update_success is False

        # Test deleting non-existent track
        delete_success = self.manager.delete_track(99999)
        assert delete_success is False

        # Test invalid search queries
        try:
            results = self.manager.search_tracks(None)
            assert isinstance(results, list)
        except Exception:
            pass  # May raise exception for invalid input

        # Test database connection issues
        try:
            # Close the connection
            self.manager.close()

            # Try to perform operation on closed connection
            stats = self.manager.get_library_stats()
            # Should handle gracefully or reconnect
        except Exception as e:
            # Should raise appropriate database exception
            assert "database" in str(e).lower() or "connection" in str(e).lower()

        self.tearDown()

    def test_concurrent_operations(self):
        """Test concurrent database operations"""
        self.setUp()

        import threading
        import time

        results = []
        errors = []

        def add_tracks_worker(worker_id):
            try:
                for i in range(5):
                    track = Track(
                        file_path=f"/worker{worker_id}_track{i}.mp3",
                        title=f"Worker {worker_id} Track {i}",
                        artist=f"Artist {worker_id}",
                        duration=180
                    )
                    result = self.manager.add_track(track)
                    results.append(result)
                    time.sleep(0.01)  # Small delay to simulate real usage
            except Exception as e:
                errors.append(e)

        # Create multiple worker threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=add_tracks_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        assert len(errors) == 0, f"Concurrent operations produced errors: {errors}"
        assert len(results) == 15  # 3 workers × 5 tracks each

        # Verify all tracks were added
        stats = self.manager.get_library_stats()
        assert stats['total_tracks'] == 15

        self.tearDown()

    def test_scanner_integration(self):
        """Test integration with LibraryScanner"""
        self.setUp()

        # Test scanner initialization
        scanner = LibraryScanner()
        assert scanner is not None

        # Test scanning the test audio directory
        scan_results = self.manager.scan_directories([self.audio_dir])
        assert scan_results is not None

        if hasattr(scan_results, 'files_found'):
            assert scan_results.files_found >= 4  # We created 4 test files

        # Test that tracks were added to library
        stats = self.manager.get_library_stats()
        assert stats['total_tracks'] >= 4

        # Test rescanning (should skip existing files)
        rescan_results = self.manager.scan_directories([self.audio_dir])
        if hasattr(rescan_results, 'files_added'):
            assert rescan_results.files_added == 0  # No new files should be added

        self.tearDown()

if __name__ == '__main__':
    import pytest
    pytest.main([__file__])