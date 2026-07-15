#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test Folder Scanning System
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test the comprehensive folder scanning and library management features.

#4247: these tests previously verified outcomes via if/else print() branches
followed by `return True`/`return False`. pytest ignores return values, so a
`return False` path (and the try/except swallowing real exceptions) still
reported PASS — a scanner regression was invisible in CI. They now use plain
`assert`s so a misbehaving scanner actually fails the suite.
"""

import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def create_test_music_library(tmpdir):
    """Create a realistic test music library structure. Returns the list of
    created track paths."""
    test_files = []

    artists = [
        ("Artist A", ["Album 1", "Album 2"]),
        ("Artist B", ["Greatest Hits"]),
        ("Various Artists", ["Compilation"])
    ]

    for artist_name, albums in artists:
        artist_dir = tmpdir / artist_name
        artist_dir.mkdir()

        for album_name in albums:
            album_dir = artist_dir / album_name
            album_dir.mkdir()

            # Create 3-5 tracks per album
            track_count = 3 if album_name == "Compilation" else 4
            for track_num in range(1, track_count + 1):
                filename = f"{track_num:02d} - Track {track_num}.wav"
                track_path = album_dir / filename

                duration = 2.0 + track_num * 0.3
                sample_rate = 44100
                samples = int(duration * sample_rate)
                t = np.linspace(0, duration, samples)

                freq = 440 + track_num * 55
                audio = np.column_stack([
                    np.sin(2 * np.pi * freq * t) * 0.3,
                    np.sin(2 * np.pi * freq * t) * 0.28
                ]).astype(np.float32)

                sf.write(track_path, audio, sample_rate)
                test_files.append(track_path)

    # Add some files in root directory (loose files)
    for i in range(2):
        filename = f"loose_track_{i+1}.flac"
        track_path = tmpdir / filename

        duration = 1.5
        sample_rate = 48000
        samples = int(duration * sample_rate)
        t = np.linspace(0, duration, samples)

        audio = np.column_stack([
            np.sin(2 * np.pi * 330 * t) * 0.25,
            np.sin(2 * np.pi * 330 * t) * 0.23
        ]).astype(np.float32)

        sf.write(track_path, audio, sample_rate, format='FLAC')
        test_files.append(track_path)

    return test_files


def test_basic_scanning():
    """A recursive scan discovers every file, and a re-scan skips them all."""
    from auralis.library import LibraryManager, LibraryScanner

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        test_files = create_test_music_library(tmpdir)

        library = LibraryManager(str(tmpdir / "scan_test.db"))
        scanner = LibraryScanner(library)

        result = scanner.scan_single_directory(str(tmpdir), recursive=True)

        # Every created file must be discovered — a scanner regression that
        # misses files now fails instead of printing a warning (#4247).
        expected_files = len(test_files)
        assert result.files_found == expected_files, (
            f"expected {expected_files} files, found {result.files_found}"
        )

        # Library stats reflect the added tracks.
        stats = library.get_library_stats()
        assert stats['total_tracks'] == result.files_added

        # Re-scan must skip all previously-added files.
        result2 = scanner.scan_single_directory(
            str(tmpdir), recursive=True, skip_existing=True
        )
        assert result2.files_skipped == result.files_added, (
            f"expected {result.files_added} skipped, got {result2.files_skipped}"
        )


def test_metadata_extraction():
    """_extract_audio_info returns correct metadata and converts to track info."""
    from auralis.library import LibraryManager, LibraryScanner

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        test_file = tmpdir / "metadata_test.wav"
        duration = 2.0
        sample_rate = 44100
        samples = int(duration * sample_rate)
        t = np.linspace(0, duration, samples)
        audio = np.column_stack([
            np.sin(2 * np.pi * 440 * t) * 0.3,
            np.sin(2 * np.pi * 440 * t) * 0.28
        ]).astype(np.float32)
        sf.write(test_file, audio, sample_rate)

        library = LibraryManager(str(tmpdir / "metadata_test.db"))
        scanner = LibraryScanner(library)

        # #4247: the old test called scanner._extract_audio_info /
        # _audio_info_to_track_info, which no longer exist — the extraction was
        # refactored onto the audio_analyzer / metadata_extractor components. The
        # old try/except swallowed the resulting AttributeError and returned
        # False, so this test silently "passed" while verifying nothing.
        audio_info = scanner.audio_analyzer.extract_audio_info(str(test_file))
        assert audio_info is not None, "failed to extract audio info"
        assert audio_info.sample_rate == sample_rate
        assert audio_info.channels == 2
        assert audio_info.duration == pytest.approx(duration, abs=0.1)
        assert audio_info.filesize > 0

        track_info = scanner.metadata_extractor.audio_info_to_track_info(audio_info)
        assert track_info['title']
        assert track_info['duration'] == pytest.approx(duration, abs=0.1)


def test_scanning_performance():
    """A larger scan processes every file. Throughput is measured but NOT
    asserted — a slow CI box must not fail the suite."""
    from auralis.library import LibraryManager, LibraryScanner

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        test_files = []
        for artist_num in range(5):  # 5 artists
            artist_dir = tmpdir / f"Artist_{artist_num + 1}"
            artist_dir.mkdir()

            for album_num in range(4):  # 4 albums each
                album_dir = artist_dir / f"Album_{album_num + 1}"
                album_dir.mkdir()

                for track_num in range(5):  # 5 tracks each
                    track_path = album_dir / f"{track_num + 1:02d}_track.wav"

                    duration = 0.5  # Short for speed
                    sample_rate = 22050  # Lower sample rate for speed
                    samples = int(duration * sample_rate)
                    t = np.linspace(0, duration, samples)

                    audio = np.column_stack([
                        np.sin(2 * np.pi * 440 * t) * 0.2,
                        np.sin(2 * np.pi * 440 * t) * 0.18
                    ]).astype(np.float32)

                    sf.write(track_path, audio, sample_rate)
                    test_files.append(track_path)

        library = LibraryManager(str(tmpdir / "perf_test.db"))
        scanner = LibraryScanner(library)

        start_time = time.time()
        result = scanner.scan_single_directory(str(tmpdir), recursive=True)
        scan_time = time.time() - start_time

        # Correctness: every file must be processed.
        assert result.files_processed == len(test_files)

        files_per_second = result.files_processed / scan_time if scan_time > 0 else 0
        print(f"Scan performance: {files_per_second:.1f} files/second")


def test_scanner_integration():
    """LibraryManager.scan_directories / scan_single_directory add the file."""
    from auralis.library import LibraryManager

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        test_dir = tmpdir / "music"
        test_dir.mkdir()

        test_file = test_dir / "integration_test.wav"
        duration = 1.0
        sample_rate = 44100
        samples = int(duration * sample_rate)
        t = np.linspace(0, duration, samples)
        audio = np.column_stack([
            np.sin(2 * np.pi * 440 * t) * 0.3,
            np.sin(2 * np.pi * 440 * t) * 0.28
        ]).astype(np.float32)
        sf.write(test_file, audio, sample_rate)

        library = LibraryManager(str(tmpdir / "integration_test.db"))

        result = library.scan_directories([str(test_dir)])
        assert result is not None
        assert result.files_found >= 1

        result2 = library.scan_single_directory(str(test_dir))
        assert result2 is not None

        stats = library.get_library_stats()
        assert stats['total_tracks'] >= 1
