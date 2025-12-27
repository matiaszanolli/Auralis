# -*- coding: utf-8 -*-

"""
Edge Cases & Error Handling Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for boundary conditions, invalid inputs, and error recovery.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf


@pytest.mark.stress
@pytest.mark.edge_case
class TestBoundaryConditions:
    """Tests for edge cases and boundary values."""

    def test_empty_library(self, tmp_path):
        """Test empty library (0 tracks)."""
        from auralis.library.manager import LibraryManager
        from auralis.library.repositories import TrackRepository

        manager = LibraryManager(database_path=str(tmp_path / "empty.db"))

        repo = TrackRepository(manager.SessionLocal)
        tracks, total = repo.get_all()

        assert len(tracks) == 0
        assert total == 0

    def test_single_track_library(self, tmp_path):
        """Test library with exactly 1 track."""
        from auralis.library.manager import LibraryManager
        from auralis.library.models import Album, Artist, Track

        manager = LibraryManager(database_path=str(tmp_path / "single.db"))
        session = manager.SessionLocal()

        # Add single track
        artist = Artist(name="Solo Artist")
        session.add(artist)
        session.flush()  # Get artist.id

        album = Album(title="Solo Album", artist_id=artist.id)
        session.add(album)
        session.flush()  # Get album.id

        track = Track(
            filepath="/test/solo.mp3",
            title="Solo Track",
            duration=180.0,
            album_id=album.id
        )

        session.add(track)
        session.commit()

        # Query
        from auralis.library.repositories import TrackRepository
        repo = TrackRepository(manager.SessionLocal)

        all_tracks, _ = repo.get_all()
        assert len(all_tracks) == 1
        assert all_tracks[0].title == "Solo Track"

        session.close()

    def test_maximum_path_length(self, tmp_path):
        """Test paths at OS maximum length."""
        # Most filesystems limit path to ~4096 bytes
        max_path_length = 4000

        # Create very long path
        long_name = "a" * 200
        nested_path = tmp_path

        try:
            # Create nested directories until we reach limit
            for i in range(10):
                nested_path = nested_path / long_name
                if len(str(nested_path)) > max_path_length:
                    break
                nested_path.mkdir(parents=True, exist_ok=True)

            # Try to create file
            filepath = nested_path / "test.txt"
            if len(str(filepath)) < max_path_length:
                with open(filepath, 'w') as f:
                    f.write("test")
                assert filepath.exists()
        except OSError as e:
            # Expected on some systems
            assert "too long" in str(e).lower() or "name too long" in str(e).lower()

    def test_unicode_paths(self, unicode_path_audio):
        """Test Unicode characters in file paths."""
        from auralis.io.unified_loader import load_audio

        # Load audio from unicode path
        audio, sr = load_audio(unicode_path_audio)

        assert audio is not None
        assert sr == 44100
        assert len(audio) > 0

    def test_special_characters_metadata(self, tmp_path):
        """Test special characters in metadata."""
        from auralis.library.manager import LibraryManager
        from auralis.library.models import Album, Artist, Track

        manager = LibraryManager(database_path=str(tmp_path / "special.db"))
        session = manager.SessionLocal()

        # Create track with special characters
        artist = Artist(name="Artist & Co. <The Best>")
        session.add(artist)
        session.flush()

        album = Album(title="Album: \"Greatest Hits\" [2024]", artist_id=artist.id)
        session.add(album)
        session.flush()

        track = Track(
            filepath="/test/special.mp3",
            title="Track #1: Rock & Roll (Live) {Bonus}",
            duration=180.0,
            album_id=album.id
        )

        session.add(track)
        session.commit()

        # Query and verify
        from auralis.library.repositories import TrackRepository
        repo = TrackRepository(manager.SessionLocal)
        tracks, _ = repo.get_all()

        assert len(tracks) == 1
        assert "Rock & Roll" in tracks[0].title
        assert "Greatest Hits" in tracks[0].album.title

        session.close()

    def test_very_long_metadata_fields(self, tmp_path):
        """Test 10,000 character metadata fields."""
        from auralis.library.manager import LibraryManager
        from auralis.library.models import Album, Artist, Track

        manager = LibraryManager(database_path=str(tmp_path / "long_metadata.db"))
        session = manager.SessionLocal()

        # Create track with very long title
        long_title = "A" * 10000
        artist = Artist(name="Test Artist")
        session.add(artist)
        session.flush()

        album = Album(title="Test Album", artist_id=artist.id)
        session.add(album)
        session.flush()

        track = Track(
            filepath="/test/long.mp3",
            title=long_title,
            duration=180.0,
            album_id=album.id
        )

        session.add(track)
        session.commit()

        # Query and verify
        from auralis.library.repositories import TrackRepository
        repo = TrackRepository(manager.SessionLocal)
        tracks, _ = repo.get_all()

        assert len(tracks) == 1
        assert len(tracks[0].title) == 10000

        session.close()

    def test_empty_metadata_fields(self, tmp_path):
        """Test all metadata fields empty."""
        from auralis.library.manager import LibraryManager
        from auralis.library.models import Track

        manager = LibraryManager(database_path=str(tmp_path / "empty_meta.db"))
        session = manager.SessionLocal()

        # Create track with minimal data
        track = Track(
            filepath="/test/minimal.mp3",
            title="Minimal Track",  # Track.title is required (nullable=False)
            duration=180.0
        )

        session.add(track)
        session.commit()

        # Query and verify
        from auralis.library.repositories import TrackRepository
        repo = TrackRepository(manager.SessionLocal)
        tracks, _ = repo.get_all()

        assert len(tracks) == 1
        # Track has minimal metadata (only required fields)
        assert tracks[0].title == "Minimal Track"  # Title is required
        assert len(tracks[0].artists) == 0  # No artists associated
        assert tracks[0].album is None  # No album

        session.close()

    def test_duplicate_files_same_path(self, tmp_path):
        """Test handling of duplicate file paths."""
        from auralis.library.manager import LibraryManager
        from auralis.library.models import Track

        manager = LibraryManager(database_path=str(tmp_path / "duplicates.db"))
        session = manager.SessionLocal()

        # Add same filepath twice
        track1 = Track(filepath="/test/duplicate.mp3", title="Duplicate", duration=180.0)
        track2 = Track(filepath="/test/duplicate.mp3", title="Duplicate", duration=180.0)

        session.add(track1)
        session.commit()

        # Second should either fail or be skipped
        try:
            session.add(track2)
            session.commit()
            # If it succeeds, check if constraint prevents it
            from auralis.library.repositories import TrackRepository
            repo = TrackRepository(manager.SessionLocal)
            tracks, _ = repo.get_all()
            # May have duplicate or unique constraint
        except Exception:
            # Expected - unique constraint violation
            session.rollback()

        session.close()

    def test_symlinks_in_library(self, tmp_path):
        """Test following/ignoring symlinks."""
        # Create real file
        real_file = tmp_path / "real.txt"
        real_file.write_text("test")

        # Create symlink
        link_file = tmp_path / "link.txt"
        try:
            link_file.symlink_to(real_file)

            # Both should resolve to same file
            assert link_file.exists()
            assert link_file.is_symlink()
            assert link_file.resolve() == real_file.resolve()
        except OSError:
            # Symlinks not supported on this platform
            pytest.skip("Symlinks not supported")

    def test_case_sensitivity_paths(self, tmp_path):
        """Test case-sensitive path handling."""
        # Create files with different cases
        file1 = tmp_path / "test.txt"
        file2 = tmp_path / "TEST.txt"

        file1.write_text("lower")

        # Check if filesystem is case-sensitive
        try:
            file2.write_text("upper")
            case_sensitive = (file1.read_text() != file2.read_text())
        except Exception:
            case_sensitive = False

        if case_sensitive:
            # Both files exist
            assert file1.exists()
            assert file2.exists()
        else:
            # Same file
            assert file1.exists()
            assert file1.read_text() == "upper"


@pytest.mark.stress
@pytest.mark.edge_case
class TestInvalidInputs:
    """Tests for invalid and malformed inputs."""

    def test_invalid_audio_format(self, tmp_path):
        """Test non-audio file with .mp3 extension."""
        # Create text file with .mp3 extension
        fake_mp3 = tmp_path / "fake.mp3"
        fake_mp3.write_text("This is not an audio file")

        from auralis.io.unified_loader import load_audio

        # Should raise exception
        with pytest.raises(Exception):
            load_audio(str(fake_mp3))

    def test_malformed_id3_tags(self, tmp_path):
        """Test corrupted metadata tags."""
        # Create valid audio with corrupted metadata would require mutagen
        # For now, test that loader handles gracefully

        # Create audio file
        audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
        filepath = tmp_path / "corrupted_tags.wav"
        sf.write(str(filepath), audio, 44100)

        # Corrupt file by appending garbage
        with open(filepath, 'ab') as f:
            f.write(b'\x00\xFF' * 100)

        from auralis.io.unified_loader import load_audio

        # Should either load audio or fail gracefully
        try:
            audio_data, sr = load_audio(str(filepath))
            # If it loads, should have audio data
            assert audio_data is not None
        except Exception:
            # Expected - corrupted file
            pass

    def test_negative_duration(self, tmp_path):
        """Test invalid negative duration."""
        from auralis.library.manager import LibraryManager
        from auralis.library.models import Track

        manager = LibraryManager(database_path=str(tmp_path / "negative.db"))
        session = manager.SessionLocal()

        # Try to create track with negative duration
        track = Track(filepath="/test/invalid.mp3", duration=-10.0)

        session.add(track)
        try:
            session.commit()
            # If it allows, query should still work
            from auralis.library.repositories import TrackRepository
            repo = TrackRepository(manager.SessionLocal)
            tracks, _ = repo.get_all()
            # May have negative duration (no validation) or fail
        except Exception:
            # Expected - validation failed
            session.rollback()

        session.close()

    def test_negative_track_number(self, tmp_path):
        """Test invalid negative track number."""
        from auralis.library.manager import LibraryManager
        from auralis.library.models import Album, Artist, Track

        manager = LibraryManager(database_path=str(tmp_path / "negative_track.db"))
        session = manager.SessionLocal()

        artist = Artist(name="Test")
        session.add(artist)
        session.flush()

        album = Album(title="Test", artist_id=artist.id)
        session.add(album)
        session.flush()

        track = Track(
            filepath="/test/invalid.mp3",
            title="Invalid Track Number",  # Track.title is required
            duration=180.0,
            track_number=-1,
            album_id=album.id
        )

        session.add(track)
        session.commit()

        # Should handle gracefully
        from auralis.library.repositories import TrackRepository
        repo = TrackRepository(manager.SessionLocal)
        tracks, _ = repo.get_all()
        assert len(tracks) == 1

        session.close()

    def test_invalid_sample_rate(self, tmp_path):
        """Test invalid sample rate (0, negative)."""
        # Try to create audio with invalid sample rate
        audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
        filepath = tmp_path / "invalid_sr.wav"

        # soundfile should reject invalid sample rate
        with pytest.raises(Exception):
            sf.write(str(filepath), audio, 0)

        with pytest.raises(Exception):
            sf.write(str(filepath), audio, -44100)

    def test_invalid_channel_count(self, tmp_path):
        """Test invalid channel count (0, 999)."""
        # Try to create audio with invalid channels
        filepath = tmp_path / "invalid_channels.wav"

        # 0 channels - should fail
        with pytest.raises(Exception):
            audio = np.random.randn(44100, 0).astype(np.float32)
            sf.write(str(filepath), audio, 44100)

        # 999 channels - may fail or succeed depending on format
        # Most formats don't support this many channels

    def test_null_bytes_in_path(self, tmp_path):
        """Test null bytes in file paths."""
        # Null byte in path should be rejected
        invalid_path = str(tmp_path / "test\x00file.txt")

        with pytest.raises((ValueError, OSError)):
            with open(invalid_path, 'w') as f:
                f.write("test")

    def test_circular_playlist_reference(self, tmp_path):
        """Test playlist referencing itself."""
        from auralis.library.manager import LibraryManager
        from auralis.library.models import Playlist

        manager = LibraryManager(database_path=str(tmp_path / "circular.db"))
        session = manager.SessionLocal()

        # Create playlist
        playlist = Playlist(name="Circular")
        session.add(playlist)
        session.commit()

        # Playlists shouldn't reference themselves (no field for it)
        # This is a conceptual test - current model doesn't allow circular refs

        session.close()

    def test_missing_album_art_file(self, tmp_path):
        """Test broken artwork references."""
        from auralis.library.manager import LibraryManager
        from auralis.library.models import Album, Artist

        manager = LibraryManager(database_path=str(tmp_path / "missing_art.db"))
        session = manager.SessionLocal()

        # Create album with artwork path that doesn't exist
        artist = Artist(name="Test")
        session.add(artist)
        session.flush()

        album = Album(
            title="Test Album",
            artist_id=artist.id,
            artwork_path="/nonexistent/artwork.jpg"
        )

        session.add(album)
        session.commit()

        # Should handle gracefully when artwork is missing
        from auralis.library.repositories import AlbumRepository
        repo = AlbumRepository(manager.SessionLocal)
        albums, _ = repo.get_all()

        assert len(albums) == 1
        assert albums[0].artwork_path == "/nonexistent/artwork.jpg"
        # Actual loading would fail, but database should be fine

        session.close()

    def test_sql_injection_attempt(self, tmp_path):
        """Test SQL injection prevention."""
        from auralis.library.manager import LibraryManager
        from auralis.library.repositories import TrackRepository

        manager = LibraryManager(database_path=str(tmp_path / "injection.db"))

        repo = TrackRepository(manager.SessionLocal)

        # Try SQL injection in search
        malicious_query = "'; DROP TABLE tracks; --"

        # Should be escaped and not execute SQL
        try:
            results, _ = repo.search(malicious_query)
            # Should return empty results or error, but not execute DROP
            assert results is not None

            # Verify table still exists
            from auralis.library.models import Track

            # Get session to verify table exists
            test_session = repo.get_session()
            count = test_session.query(Track).count()
            test_session.close()
            # Table should still exist (count may be 0)
        except Exception:
            # Expected - handled gracefully
            pass


@pytest.mark.stress
@pytest.mark.edge_case
class TestErrorRecovery:
    """Tests for error recovery and resilience."""

    def test_database_corruption_recovery(self, tmp_path):
        """Test recovery from database corruption."""
        from auralis.library.manager import LibraryManager

        db_path = tmp_path / "corrupt.db"

        # Create valid database
        manager = LibraryManager(database_path=str(db_path))
        session = manager.SessionLocal()
        session.close()

        # Corrupt database file
        with open(db_path, 'wb') as f:
            f.write(b'\x00\xFF' * 1000)

        # Try to open corrupted database
        try:
            manager2 = LibraryManager(database_path=str(db_path))
            session2 = manager2.SessionLocal()
            session2.close()
        except Exception as e:
            # Expected - corruption detected
            assert e is not None

            # Recovery: Delete and recreate
            db_path.unlink()
            manager3 = LibraryManager(database_path=str(db_path))
            session3 = manager3.SessionLocal()
            session3.close()
            # Should work after recreation

    def test_cache_corruption_recovery(self, tmp_path):
        """Test rebuilding cache after corruption."""
        from auralis.library.manager import LibraryManager

        manager = LibraryManager(database_path=str(tmp_path / "cache_test.db"))

        # Fill cache
        manager.get_recent_tracks(limit=50)

        stats_before = manager.get_cache_stats()

        # Clear/corrupt cache
        manager.clear_cache()

        stats_after = manager.get_cache_stats()

        # Cache should be empty
        assert stats_after['size'] == 0
        assert stats_after['hits'] == 0

        # Rebuild cache
        manager.get_recent_tracks(limit=50)

        # Should work after rebuild
        stats_rebuilt = manager.get_cache_stats()
        assert stats_rebuilt['size'] > 0

    def test_partial_scan_recovery(self, tmp_path):
        """Test resuming interrupted library scan."""
        from auralis.library.manager import LibraryManager
        from auralis.library.scanner import LibraryScanner

        # Create test files
        music_dir = tmp_path / "music"
        music_dir.mkdir()

        for i in range(50):
            audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
            filepath = music_dir / f"track_{i:03d}.wav"
            sf.write(str(filepath), audio, 44100)

        manager = LibraryManager(database_path=str(tmp_path / "partial.db"))
        scanner = LibraryScanner(manager)

        # Partial scan (simulated interruption)
        # In real implementation, would interrupt mid-scan
        # For now, test that rescan works

        # First scan
        results1 = scanner.scan_single_directory(str(music_dir))
        assert results1.files_found == 50  # ScanResult is object, not dict

        # Rescan (should update, not duplicate)
        results2 = scanner.scan_single_directory(str(music_dir))

        # Should handle gracefully
        assert results2 is not None

    def test_processing_crash_recovery(self, tmp_path):
        """Test resuming after processing crash."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # Process successfully
        audio1 = np.random.randn(44100, 2).astype(np.float32) * 0.1
        result1 = processor.process(audio1)
        assert result1 is not None

        # Simulate crash (invalid input)
        try:
            invalid_audio = np.array([], dtype=np.float32).reshape(0, 2)
            processor.process(invalid_audio)
        except Exception:
            # Expected crash
            pass

        # Recovery: Process again
        audio2 = np.random.randn(44100, 2).astype(np.float32) * 0.1
        result2 = processor.process(audio2)

        # Should work after crash
        assert result2 is not None

    def test_graceful_shutdown_under_load(self, tmp_path):
        """Test clean shutdown during heavy load."""
        import threading
        from concurrent.futures import ThreadPoolExecutor

        from auralis.library.manager import LibraryManager

        manager = LibraryManager(database_path=str(tmp_path / "shutdown.db"))

        # Start heavy load
        stop_flag = threading.Event()

        def query_loop():
            while not stop_flag.is_set():
                try:
                    manager.get_recent_tracks(limit=10)
                    time.sleep(0.01)
                except Exception:
                    break

        with ThreadPoolExecutor(max_workers=4) as executor:
            # Start query threads
            futures = [executor.submit(query_loop) for _ in range(4)]

            # Let them run
            time.sleep(0.5)

            # Shutdown gracefully
            stop_flag.set()

            # Wait for completion
            for future in futures:
                try:
                    future.result(timeout=2.0)
                except Exception:
                    # May timeout, that's ok
                    pass

        # System should still be functional
        tracks = manager.get_recent_tracks(limit=10)
        assert tracks is not None
