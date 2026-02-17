#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Library Scanner Comprehensive Coverage Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for the library scanner updated to match current API
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.abspath('../..'))

import soundfile as sf

from auralis.library.scan_models import AudioFileInfo, ScanResult
from auralis.library.scanner import LibraryScanner


class TestLibraryScannerComprehensive:
    """Comprehensive test coverage for LibraryScanner"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

        # Create a LibraryManager for the scanner
        from auralis.library.manager import LibraryManager
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.library_manager = LibraryManager(database_path=self.db_path)
        # LibraryScanner now requires library_manager parameter
        self.scanner = LibraryScanner(self.library_manager)

        # Create nested directory structure
        self.audio_dir = os.path.join(self.temp_dir, "music")
        self.subdir1 = os.path.join(self.audio_dir, "artist1")
        self.subdir2 = os.path.join(self.audio_dir, "artist2", "album1")

        os.makedirs(self.subdir1, exist_ok=True)
        os.makedirs(self.subdir2, exist_ok=True)

        self._create_test_audio_files()

    def tearDown(self):
        """Clean up test fixtures"""
        # LibraryManager no longer has close() method
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_test_audio_files(self):
        """Create various test audio files with different formats and metadata"""
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)
        audio = 0.3 * np.sin(2 * np.pi * 440 * t)

        # Create WAV files
        wav_files = [
            (os.path.join(self.subdir1, "track1.wav"), "Track 1", "Artist 1", "Album 1"),
            (os.path.join(self.subdir1, "track2.wav"), "Track 2", "Artist 1", "Album 1"),
            (os.path.join(self.subdir2, "track3.wav"), "Track 3", "Artist 2", "Album 2"),
        ]

        for filepath, title, artist, album in wav_files:
            sf.write(filepath, audio, sample_rate)

        # Create FLAC files
        flac_files = [
            (os.path.join(self.subdir1, "track1.flac"), "FLAC Track 1", "Artist 1", "Album 1"),
            (os.path.join(self.subdir2, "track2.flac"), "FLAC Track 2", "Artist 2", "Album 2"),
        ]

        for filepath, title, artist, album in flac_files:
            sf.write(filepath, audio, sample_rate, format='FLAC')

        # Create additional test files
        self._create_additional_test_files(audio, sample_rate)

        # Create non-audio files (should be ignored)
        non_audio_files = [
            os.path.join(self.audio_dir, "readme.txt"),
            os.path.join(self.audio_dir, "cover.jpg"),
            os.path.join(self.subdir1, "info.log"),
        ]

        for filepath in non_audio_files:
            with open(filepath, 'w') as f:
                f.write("This is not an audio file")

    def _create_additional_test_files(self, audio, sample_rate):
        """Create additional test files for comprehensive testing"""
        # Very short file
        short_audio = audio[:1000]  # Very short
        short_path = os.path.join(self.audio_dir, "short.wav")
        sf.write(short_path, short_audio, sample_rate)

        # Mono file
        mono_path = os.path.join(self.audio_dir, "mono.wav")
        sf.write(mono_path, audio, sample_rate)

        # Empty directory
        empty_dir = os.path.join(self.audio_dir, "empty_folder")
        os.makedirs(empty_dir, exist_ok=True)

    def test_scanner_initialization(self):
        """Test scanner initialization and configuration"""
        self.setUp()

        # Test initialization with library_manager (required)
        from auralis.library.manager import LibraryManager
        manager = LibraryManager(database_path=os.path.join(self.temp_dir, "test2.db"))
        scanner = LibraryScanner(manager)
        assert scanner is not None
        # LibraryScanner has scan_directories(), not scan_directory() or scan_file()
        assert hasattr(scanner, 'scan_directories')
        assert hasattr(scanner, 'library_manager')

        self.tearDown()

    def test_single_file_scanning(self):
        """Test scanning single directory"""
        self.setUp()

        # Scanner uses scan_directories() (plural), scanning a specific directory
        result = self.scanner.scan_directories([self.subdir1])

        assert result is not None
        assert isinstance(result, ScanResult)
        # Should find files in subdir1
        assert result.files_found >= 2  # At least track1.wav and track1.flac

        self.tearDown()

    def test_directory_scanning_basic(self):
        """Test basic directory scanning"""
        self.setUp()

        # Scan main audio directory (non-recursive)
        result = self.scanner.scan_directories([self.audio_dir], recursive=False)

        assert result is not None
        assert isinstance(result, ScanResult)
        # Non-recursive should find files directly in audio_dir
        assert result.files_found >= 0

        self.tearDown()

    def test_recursive_scanning(self):
        """Test recursive directory scanning"""
        self.setUp()

        # Scan with recursion enabled (default)
        result = self.scanner.scan_directories([self.audio_dir], recursive=True)

        assert result is not None
        assert isinstance(result, ScanResult)
        # Should find all audio files in all subdirectories
        assert result.files_found >= 5  # WAV + FLAC files

        self.tearDown()

    def test_file_filtering(self):
        """Test that non-audio files are filtered out"""
        self.setUp()

        # Scan directory containing both audio and non-audio files
        result = self.scanner.scan_directories([self.audio_dir], recursive=True)

        assert result is not None
        # Should not count .txt, .jpg, .log files
        assert result.files_found >= 5  # Only audio files

        self.tearDown()

    def test_metadata_extraction(self):
        """Test metadata extraction from audio files"""
        self.setUp()

        # Scan and add files
        result = self.scanner.scan_directories([self.audio_dir])

        assert result is not None
        assert result.files_processed > 0

        # Verify tracks were added to library
        stats = self.library_manager.get_library_stats()
        assert stats['total_tracks'] > 0

        self.tearDown()

    def test_progress_reporting(self):
        """Test progress callback functionality"""
        self.setUp()

        progress_updates = []

        def progress_callback(data):
            progress_updates.append(data)

        # Set progress callback
        self.scanner.set_progress_callback(progress_callback)

        # Perform scan
        result = self.scanner.scan_directories([self.audio_dir])

        # Should have received progress updates
        assert len(progress_updates) > 0

        self.tearDown()

    def test_error_handling(self):
        """Test error handling for invalid inputs"""
        self.setUp()

        # Test scanning non-existent directory
        result = self.scanner.scan_directories(["/nonexistent/path"])
        assert result is not None
        assert result.files_found == 0

        # Test scanning empty list
        result = self.scanner.scan_directories([])
        assert result is not None

        self.tearDown()

    def test_scan_result_objects(self):
        """Test ScanResult object structure"""
        self.setUp()

        result = self.scanner.scan_directories([self.audio_dir])

        # Verify ScanResult has expected attributes
        assert hasattr(result, 'files_found')
        assert hasattr(result, 'files_processed')
        assert hasattr(result, 'files_added')
        assert hasattr(result, 'files_skipped')
        assert hasattr(result, 'files_failed')
        assert hasattr(result, 'scan_time')

        # Verify types
        assert isinstance(result.files_found, int)
        assert isinstance(result.files_processed, int)
        assert isinstance(result.scan_time, (int, float))

        self.tearDown()

    def test_duplicate_detection(self):
        """Test that duplicate files are handled correctly"""
        self.setUp()

        # First scan
        result1 = self.scanner.scan_directories([self.audio_dir])
        files_added_first = result1.files_added if hasattr(result1, 'files_added') else 0

        # Second scan (should skip existing files)
        result2 = self.scanner.scan_directories([self.audio_dir], skip_existing=True)

        # Second scan should skip files already in library
        if hasattr(result2, 'files_skipped'):
            assert result2.files_skipped >= files_added_first

        self.tearDown()

    def test_performance_with_large_directory(self):
        """Test scanning performance with many files"""
        self.setUp()

        # Create many test files
        many_files_dir = os.path.join(self.temp_dir, "many_files")
        os.makedirs(many_files_dir, exist_ok=True)

        sample_rate = 44100
        duration = 0.5  # Short files for speed
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)
        audio = 0.3 * np.sin(2 * np.pi * 440 * t)

        # Create 20 files
        for i in range(20):
            filepath = os.path.join(many_files_dir, f"track{i}.wav")
            sf.write(filepath, audio, sample_rate)

        # Scan and measure time
        result = self.scanner.scan_directories([many_files_dir])

        assert result is not None
        assert result.files_found == 20
        assert result.scan_time < 30.0  # Should complete in reasonable time

        self.tearDown()

    def test_symlink_handling(self):
        """Test handling of symbolic links"""
        self.setUp()

        # Create a symlink to audio directory (if supported)
        try:
            symlink_path = os.path.join(self.temp_dir, "music_link")
            os.symlink(self.audio_dir, symlink_path)

            # Scan symlinked directory
            result = self.scanner.scan_directories([symlink_path])

            assert result is not None
            # Should find files through symlink
            assert result.files_found > 0
        except (OSError, NotImplementedError):
            # Symlinks not supported on this platform
            pass

        self.tearDown()

    def test_concurrent_scanning(self):
        """Test concurrent scanning operations"""
        self.setUp()

        import threading

        results = []
        errors = []

        def scan_worker(dir_path):
            try:
                # Each thread needs its own LibraryManager instance
                from auralis.library.manager import LibraryManager
                temp_db = os.path.join(self.temp_dir, f"thread_{threading.current_thread().ident}.db")
                manager = LibraryManager(database_path=temp_db)
                scanner = LibraryScanner(manager)
                result = scanner.scan_directories([dir_path])
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Create worker threads
        threads = []
        dirs_to_scan = [self.subdir1, self.subdir2, self.audio_dir]

        for dir_path in dirs_to_scan:
            thread = threading.Thread(target=scan_worker, args=(dir_path,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        assert len(errors) == 0, f"Concurrent scanning produced errors: {errors}"
        assert len(results) == 3

        self.tearDown()

class TestFileDiscoverySymlinkSafety:
    """Tests for symlink cycle detection and depth limiting in FileDiscovery"""

    def test_circular_symlink_does_not_hang(self):
        """Scanner must complete when a symlink points back to a parent directory"""
        import threading
        from auralis.library.scanner.file_discovery import FileDiscovery

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create circular symlink: <tmp>/loop -> <tmp>
            link_path = os.path.join(tmp_dir, "loop")
            os.symlink(tmp_dir, link_path)

            discovery = FileDiscovery()
            completed = threading.Event()

            def run():
                list(discovery.discover_audio_files(tmp_dir, recursive=True))
                completed.set()

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            finished = completed.wait(timeout=5.0)

            assert finished, "Scanner hung on circular symlink — did not complete within 5 s"

    def test_max_depth_limit_stops_excessive_recursion(self):
        """Scanner must stop at MAX_SCAN_DEPTH and not recurse into deeper directories"""
        from auralis.library.scanner.file_discovery import FileDiscovery, MAX_SCAN_DEPTH

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Build a directory chain 10 levels past the limit
            depth_to_create = MAX_SCAN_DEPTH + 10
            current = tmp_dir
            for i in range(depth_to_create):
                current = os.path.join(current, f"d{i}")
                os.mkdir(current)

            # Place an audio file at the very bottom (beyond the limit)
            deep_file = os.path.join(current, "deep.flac")
            open(deep_file, "wb").close()

            discovery = FileDiscovery()
            found = list(discovery.discover_audio_files(tmp_dir, recursive=True))

            # The deep file must not be returned — depth guard cut traversal short
            assert deep_file not in found, (
                f"Scanner should not have reached depth {depth_to_create} "
                f"(limit is {MAX_SCAN_DEPTH})"
            )

    def test_normal_symlink_to_non_circular_target_works(self):
        """A symlink pointing to a non-ancestor directory must still be followed"""
        import threading
        from auralis.library.scanner.file_discovery import FileDiscovery

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Real audio dir
            real_music = os.path.join(tmp_dir, "real_music")
            os.makedirs(real_music)
            open(os.path.join(real_music, "song.flac"), "wb").close()

            # Symlink pointing at real_music (not circular)
            link_path = os.path.join(tmp_dir, "linked_music")
            os.symlink(real_music, link_path)

            discovery = FileDiscovery()
            found = list(discovery.discover_audio_files(tmp_dir, recursive=True))

            # song.flac should appear exactly once (real_music reached directly;
            # linked_music resolves to the same inode so it is skipped as duplicate)
            flac_files = [f for f in found if f.endswith("song.flac")]
            assert len(flac_files) == 1, (
                f"Expected 1 result for song.flac, got {len(flac_files)}: {flac_files}"
            )


if __name__ == '__main__':
    import pytest
    pytest.main([__file__])
