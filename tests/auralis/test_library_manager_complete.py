#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Complete Library Manager Coverage Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests targeting 50%+ coverage for LibraryManager (currently 20%)
This test focuses on the actual interface and methods from manager.py
"""

import numpy as np
import tempfile
import os
import sys
import shutil
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath('../..'))

from auralis.library.manager import LibraryManager
from auralis.library.models import Track, Album, Artist, Genre, Playlist
import soundfile as sf

class TestLibraryManagerComplete:
    """Complete LibraryManager coverage tests"""

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
            del self.manager  # Close any sessions
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_test_audio_files(self):
        """Create test audio files"""
        sample_rate = 44100
        duration = 2.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)
        audio = 0.5 * np.sin(2 * np.pi * 440 * t)

        test_files = [
            "track1.wav", "track2.wav", "track3.wav", "track4.wav", "track5.wav"
        ]

        for filename in test_files:
            filepath = os.path.join(self.audio_dir, filename)
            sf.write(filepath, audio, sample_rate)

    def test_initialization_and_session_management(self):
        """Test initialization and session management"""
        self.setUp()

        # Test basic initialization
        assert self.manager is not None
        assert self.manager.database_path == self.db_path
        assert os.path.exists(self.db_path)

        # Test session creation
        session = self.manager.get_session()
        assert session is not None
        session.close()

        # Test with default database path
        default_manager = LibraryManager()  # Should create default path
        assert default_manager.database_path is not None
        del default_manager

        self.tearDown()

    def test_track_operations_comprehensive(self):
        """Test comprehensive track operations"""
        self.setUp()

        # Test adding tracks
        track_info1 = {
            'title': 'Test Track 1',
            'filepath': os.path.join(self.audio_dir, 'track1.wav'),
            'artist': 'Test Artist 1',
            'album': 'Test Album 1',
            'duration': 180.5,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'filesize': 1024000,
            'genre': 'Rock'
        }

        track1 = self.manager.add_track(track_info1)
        assert track1 is not None
        assert track1.title == 'Test Track 1'
        assert track1.filepath == track_info1['filepath']

        # Test duplicate track detection
        duplicate_track = self.manager.add_track(track_info1)
        assert duplicate_track is not None
        assert duplicate_track.id == track1.id  # Should return existing track

        # Add more tracks for comprehensive testing
        for i in range(2, 6):
            track_info = {
                'title': f'Test Track {i}',
                'filepath': os.path.join(self.audio_dir, f'track{i}.wav'),
                'artist': f'Test Artist {(i-1)%3 + 1}',  # Rotate between 3 artists
                'album': f'Test Album {(i-1)%2 + 1}',    # Rotate between 2 albums
                'duration': 160 + i*10,
                'sample_rate': 44100,
                'channels': 2,
                'format': 'WAV',
                'filesize': 1000000 + i*10000,
                'genre': ['Rock', 'Jazz', 'Classical', 'Electronic'][i%4],
                'year': 2020 + i
            }
            added_track = self.manager.add_track(track_info)
            assert added_track is not None

        self.tearDown()

    def test_track_retrieval_methods(self):
        """Test various track retrieval methods"""
        self.setUp()

        # Add test data
        test_tracks = []
        for i in range(1, 6):
            track_info = {
                'title': f'Track {i}',
                'filepath': os.path.join(self.audio_dir, f'track{i}.wav'),
                'artist': f'Artist {(i-1)%3 + 1}',
                'album': f'Album {(i-1)%2 + 1}',
                'duration': 150 + i*15,
                'sample_rate': 44100,
                'genre': ['Rock', 'Jazz', 'Pop'][i%3]
            }
            track = self.manager.add_track(track_info)
            test_tracks.append(track)

        # Test get_track by ID
        retrieved = self.manager.get_track(test_tracks[0].id)
        assert retrieved is not None
        assert retrieved.title == 'Track 1'

        # Test get_track_by_path
        path_track = self.manager.get_track_by_path(test_tracks[0].filepath)
        assert path_track is not None
        assert path_track.id == test_tracks[0].id

        # Test get_tracks_by_artist
        artist_tracks = self.manager.get_tracks_by_artist('Artist 1')
        assert len(artist_tracks) >= 1
        for track in artist_tracks:
            assert track.artist == 'Artist 1'

        # Test get_tracks_by_genre
        rock_tracks = self.manager.get_tracks_by_genre('Rock')
        assert isinstance(rock_tracks, list)

        # Test get_recent_tracks
        recent_tracks = self.manager.get_recent_tracks(limit=3)
        assert len(recent_tracks) <= 3

        # Test get_popular_tracks
        popular_tracks = self.manager.get_popular_tracks(limit=3)
        assert isinstance(popular_tracks, list)

        # Test get_favorite_tracks
        favorite_tracks = self.manager.get_favorite_tracks(limit=3)
        assert isinstance(favorite_tracks, list)

        self.tearDown()

    def test_search_functionality(self):
        """Test search functionality"""
        self.setUp()

        # Add searchable test data
        search_tracks = [
            {'title': 'Beatles Song', 'artist': 'The Beatles', 'album': 'Abbey Road', 'filepath': os.path.join(self.audio_dir, 'track1.wav')},
            {'title': 'Rock Anthem', 'artist': 'Queen', 'album': 'Greatest Hits', 'filepath': os.path.join(self.audio_dir, 'track2.wav')},
            {'title': 'Jazz Standard', 'artist': 'Miles Davis', 'album': 'Kind of Blue', 'filepath': os.path.join(self.audio_dir, 'track3.wav')},
        ]

        added_tracks = []
        for track_info in search_tracks:
            track_info.update({'duration': 180, 'sample_rate': 44100})
            track = self.manager.add_track(track_info)
            added_tracks.append(track)

        # Test various search queries
        # Search by title
        title_results = self.manager.search_tracks('Beatles', limit=10)
        assert len(title_results) >= 1
        assert any('Beatles' in track.title for track in title_results)

        # Search by artist
        artist_results = self.manager.search_tracks('Queen', limit=10)
        assert len(artist_results) >= 1

        # Search by album
        album_results = self.manager.search_tracks('Abbey Road', limit=10)
        assert len(album_results) >= 1

        # Search with different limits
        limited_results = self.manager.search_tracks('', limit=2)  # Empty query should return all, limited
        assert len(limited_results) <= 2

        self.tearDown()

    def test_playlist_operations(self):
        """Test comprehensive playlist operations"""
        self.setUp()

        # Add some tracks first
        tracks = []
        for i in range(1, 6):
            track_info = {
                'title': f'Playlist Track {i}',
                'filepath': os.path.join(self.audio_dir, f'track{i}.wav'),
                'artist': f'Artist {i}',
                'duration': 180,
                'sample_rate': 44100
            }
            track = self.manager.add_track(track_info)
            tracks.append(track)

        # Test create_playlist
        playlist = self.manager.create_playlist(
            name='Test Playlist',
            description='A test playlist for coverage',
            track_ids=[tracks[0].id, tracks[1].id, tracks[2].id]
        )
        assert playlist is not None
        assert playlist.name == 'Test Playlist'

        # Test get_playlist
        retrieved_playlist = self.manager.get_playlist(playlist.id)
        assert retrieved_playlist is not None
        assert retrieved_playlist.name == 'Test Playlist'

        # Test get_all_playlists
        all_playlists = self.manager.get_all_playlists()
        assert len(all_playlists) >= 1
        assert any(p.id == playlist.id for p in all_playlists)

        # Test add_track_to_playlist
        success = self.manager.add_track_to_playlist(playlist.id, tracks[3].id)
        assert success is True

        # Test adding invalid track to playlist
        invalid_success = self.manager.add_track_to_playlist(playlist.id, 99999)
        assert invalid_success is False

        # Test create_playlist with empty track list
        empty_playlist = self.manager.create_playlist(
            name='Empty Playlist',
            description='Empty test playlist'
        )
        assert empty_playlist is not None

        self.tearDown()

    def test_track_interaction_features(self):
        """Test track interaction features (play recording, favorites)"""
        self.setUp()

        # Add test track
        track_info = {
            'title': 'Interactive Track',
            'filepath': os.path.join(self.audio_dir, 'track1.wav'),
            'artist': 'Test Artist',
            'duration': 180,
            'sample_rate': 44100
        }
        track = self.manager.add_track(track_info)

        # Test record_track_play
        initial_plays = track.play_count or 0
        self.manager.record_track_play(track.id)

        # Get updated track
        updated_track = self.manager.get_track(track.id)
        assert updated_track.play_count > initial_plays

        # Test set_track_favorite
        self.manager.set_track_favorite(track.id, favorite=True)

        favorited_track = self.manager.get_track(track.id)
        assert favorited_track.favorite is True

        # Test unfavorite
        self.manager.set_track_favorite(track.id, favorite=False)

        unfavorited_track = self.manager.get_track(track.id)
        assert unfavorited_track.favorite is False

        self.tearDown()

    def test_reference_track_finding(self):
        """Test reference track finding functionality"""
        self.setUp()

        # Add tracks with similar characteristics
        reference_tracks = []
        for i in range(1, 6):
            track_info = {
                'title': f'Reference Track {i}',
                'filepath': os.path.join(self.audio_dir, f'track{i}.wav'),
                'artist': 'Similar Artist',
                'album': 'Similar Album',
                'genre': 'Rock',
                'duration': 180 + i*5,  # Similar durations
                'sample_rate': 44100,
                'tempo': 120 + i*2      # Similar tempos
            }
            track = self.manager.add_track(track_info)
            reference_tracks.append(track)

        # Test find_reference_tracks
        target_track = reference_tracks[0]
        similar_tracks = self.manager.find_reference_tracks(target_track, limit=3)

        assert isinstance(similar_tracks, list)
        assert len(similar_tracks) <= 3
        # Should not include the target track itself
        assert target_track.id not in [t.id for t in similar_tracks]

        self.tearDown()

    def test_library_statistics(self):
        """Test library statistics functionality"""
        self.setUp()

        # Add diverse test data
        for i in range(1, 11):  # Add 10 tracks
            track_info = {
                'title': f'Stats Track {i}',
                'filepath': os.path.join(self.audio_dir, f'track{i % 5 + 1}.wav'),  # Reuse files
                'artist': f'Artist {i % 4 + 1}',  # 4 different artists
                'album': f'Album {i % 3 + 1}',    # 3 different albums
                'genre': ['Rock', 'Jazz', 'Pop', 'Classical'][i % 4],  # 4 genres
                'duration': 150 + i*10,
                'sample_rate': 44100,
                'filesize': 1000000 + i*100000,
                'year': 2020 + (i % 5)
            }
            self.manager.add_track(track_info)

        # Test get_library_stats
        stats = self.manager.get_library_stats()

        assert isinstance(stats, dict)
        assert 'total_tracks' in stats
        assert stats['total_tracks'] == 10

        assert 'total_artists' in stats
        assert stats['total_artists'] >= 4

        assert 'total_albums' in stats
        assert stats['total_albums'] >= 3

        assert 'total_duration' in stats
        assert stats['total_duration'] > 0

        assert 'total_filesize' in stats
        assert stats['total_filesize'] > 0

        # Test additional stats if they exist
        if 'genres' in stats:
            assert isinstance(stats['genres'], (list, dict))

        if 'years' in stats:
            assert isinstance(stats['years'], (list, dict))

        self.tearDown()

    def test_recommendations_system(self):
        """Test recommendation system"""
        self.setUp()

        # Add tracks for recommendation testing
        recommendation_tracks = []
        for i in range(1, 8):
            track_info = {
                'title': f'Rec Track {i}',
                'filepath': os.path.join(self.audio_dir, f'track{i % 5 + 1}.wav'),
                'artist': f'Rec Artist {i % 3 + 1}',
                'genre': ['Rock', 'Jazz', 'Pop'][i % 3],
                'duration': 180,
                'sample_rate': 44100,
                'tempo': 120 + i*5,
                'energy': 0.5 + (i % 3) * 0.2
            }
            track = self.manager.add_track(track_info)
            recommendation_tracks.append(track)

        # Test get_recommendations
        target_track = recommendation_tracks[0]
        recommendations = self.manager.get_recommendations(target_track, limit=5)

        assert isinstance(recommendations, list)
        assert len(recommendations) <= 5
        # Should not include the target track itself
        assert target_track.id not in [r.id for r in recommendations]

        self.tearDown()

    def test_error_handling_and_edge_cases(self):
        """Test error handling and edge cases"""
        self.setUp()

        # Test get_track with invalid ID
        invalid_track = self.manager.get_track(99999)
        assert invalid_track is None

        # Test get_track_by_path with invalid path
        invalid_path_track = self.manager.get_track_by_path('/nonexistent/path.wav')
        assert invalid_path_track is None

        # Test search with empty query
        empty_search = self.manager.search_tracks('')
        assert isinstance(empty_search, list)

        # Test get_playlist with invalid ID
        invalid_playlist = self.manager.get_playlist(99999)
        assert invalid_playlist is None

        # Test add_track_to_playlist with invalid IDs
        invalid_add = self.manager.add_track_to_playlist(99999, 99999)
        assert invalid_add is False

        # Test record_track_play with invalid ID
        try:
            self.manager.record_track_play(99999)
            # Should handle gracefully without crashing
        except Exception:
            pass  # Some exceptions are acceptable

        # Test set_track_favorite with invalid ID
        try:
            self.manager.set_track_favorite(99999, True)
            # Should handle gracefully
        except Exception:
            pass

        # Test add_track with minimal info
        minimal_track_info = {
            'title': 'Minimal Track',
            'filepath': '/minimal/path.wav'
        }
        minimal_track = self.manager.add_track(minimal_track_info)
        # Should either succeed or fail gracefully
        assert minimal_track is None or minimal_track.title == 'Minimal Track'

        self.tearDown()

    def test_database_integrity_operations(self):
        """Test database integrity and cleanup operations"""
        self.setUp()

        # Add some test data
        track_info = {
            'title': 'Integrity Test Track',
            'filepath': os.path.join(self.audio_dir, 'track1.wav'),
            'artist': 'Test Artist',
            'duration': 180,
            'sample_rate': 44100
        }
        track = self.manager.add_track(track_info)

        # Create playlist
        playlist = self.manager.create_playlist('Integrity Playlist', 'Test')

        # Test various operations that stress database integrity
        # Add same track multiple times (should handle duplicates)
        for _ in range(3):
            duplicate = self.manager.add_track(track_info)
            assert duplicate.id == track.id

        # Test concurrent-like operations
        session = self.manager.get_session()
        # Query multiple tables
        tracks_count = session.query(Track).count()
        playlists_count = session.query(Playlist).count()
        session.close()

        assert tracks_count >= 1
        assert playlists_count >= 1

        # Test stats after various operations
        final_stats = self.manager.get_library_stats()
        assert final_stats['total_tracks'] >= 1

        self.tearDown()

if __name__ == '__main__':
    import pytest
    pytest.main([__file__])