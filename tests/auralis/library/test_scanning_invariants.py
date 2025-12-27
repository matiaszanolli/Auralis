#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Library Scanning Invariant Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Critical invariant tests for library scanning that validate correctness,
completeness, and metadata extraction.

:copyright: (C) 2024 Auralis Team
:license: GPLv3

CONTEXT: Scanning bugs can cause:
- Missing tracks (some files not detected)
- Duplicate tracks (same file scanned twice)
- Incorrect metadata (wrong title, artist, album)
- Database corruption (orphaned entries)

These tests validate properties that MUST always hold for library scanning.

Test Philosophy:
- Test invariants (properties that must always hold)
- Test behavior, not implementation
- Focus on defect detection
- Real audio files, not mocks

See docs/development/TESTING_GUIDELINES.md for complete testing philosophy.
"""

import os

# Import the modules under test
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.io.saver import save as save_audio
from auralis.library.manager import LibraryManager
from auralis.library.scanner import LibraryScanner

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_audio_dir():
    """Create temporary directory with test audio files."""
    temp_dir = tempfile.mkdtemp()
    audio_dir = os.path.join(temp_dir, "music")
    os.makedirs(audio_dir)

    # Create 10 test WAV files
    for i in range(10):
        audio = np.random.randn(44100, 2)  # 1 second stereo
        filepath = os.path.join(audio_dir, f"track_{i:02d}.wav")
        save_audio(filepath, audio, 44100, subtype='PCM_16')

    yield audio_dir, temp_dir

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def library_manager():
    """Create temporary LibraryManager instance."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_library.db")
    manager = LibraryManager(database_path=db_path)

    yield manager

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def scanner(library_manager):
    """Create LibraryScanner instance."""
    return LibraryScanner(library_manager)


# ============================================================================
# Scan Completeness Invariants (P0 Priority)
# ============================================================================

@pytest.mark.integration
def test_scanner_finds_all_audio_files(test_audio_dir, scanner):
    """
    CRITICAL INVARIANT: Scanner must find all audio files in directory.

    Missing files during scan causes incomplete library.
    """
    audio_dir, _ = test_audio_dir

    # Scan directory
    found_files = scanner.scan_folder(audio_dir)

    # Count actual WAV files
    import glob
    actual_files = glob.glob(os.path.join(audio_dir, "*.wav"))

    assert len(found_files) == len(actual_files), (
        f"Scanner found {len(found_files)} files, but directory contains {len(actual_files)} files. "
        f"Missing: {len(actual_files) - len(found_files)} files"
    )


@pytest.mark.integration
def test_scanner_doesnt_duplicate_files(test_audio_dir, scanner):
    """
    INVARIANT: Scanner must not return duplicate files in single scan.
    """
    audio_dir, _ = test_audio_dir

    found_files = scanner.scan_folder(audio_dir)

    # Check for duplicates
    file_paths = [f['filepath'] for f in found_files]
    unique_paths = set(file_paths)

    assert len(file_paths) == len(unique_paths), (
        f"Scanner returned duplicates: {len(file_paths)} files, "
        f"{len(unique_paths)} unique. "
        f"Duplicates: {[p for p in file_paths if file_paths.count(p) > 1]}"
    )


@pytest.mark.integration
def test_rescan_produces_same_results(test_audio_dir, scanner):
    """
    INVARIANT: Scanning same directory twice should find same files.

    Determinism is essential for reliable library management.
    """
    audio_dir, _ = test_audio_dir

    # Scan twice
    first_scan = scanner.scan_folder(audio_dir)
    second_scan = scanner.scan_folder(audio_dir)

    first_paths = {f['filepath'] for f in first_scan}
    second_paths = {f['filepath'] for f in second_scan}

    assert first_paths == second_paths, (
        f"Rescan found different files. "
        f"First scan: {len(first_paths)} files, second scan: {len(second_paths)} files. "
        f"Missing in second: {first_paths - second_paths}, "
        f"Extra in second: {second_paths - first_paths}"
    )


# ============================================================================
# Metadata Extraction Invariants (P0 Priority)
# ============================================================================

@pytest.mark.integration
def test_scanner_extracts_duration(test_audio_dir, scanner):
    """
    INVARIANT: Scanner must extract duration for all audio files.
    """
    audio_dir, _ = test_audio_dir

    found_files = scanner.scan_folder(audio_dir)

    for file_info in found_files:
        assert 'duration' in file_info, (
            f"Missing duration for {file_info['filepath']}"
        )
        assert file_info['duration'] > 0, (
            f"Invalid duration {file_info['duration']} for {file_info['filepath']}"
        )


@pytest.mark.integration
def test_scanner_extracts_sample_rate(test_audio_dir, scanner):
    """
    INVARIANT: Scanner must extract sample rate for all audio files.
    """
    audio_dir, _ = test_audio_dir

    found_files = scanner.scan_folder(audio_dir)

    for file_info in found_files:
        assert 'sample_rate' in file_info, (
            f"Missing sample_rate for {file_info['filepath']}"
        )
        assert file_info['sample_rate'] > 0, (
            f"Invalid sample_rate {file_info['sample_rate']} for {file_info['filepath']}"
        )
        # Common sample rates
        assert file_info['sample_rate'] in [44100, 48000, 88200, 96000, 176400, 192000], (
            f"Unexpected sample_rate {file_info['sample_rate']} for {file_info['filepath']}"
        )


@pytest.mark.integration
def test_scanner_extracts_channels(test_audio_dir, scanner):
    """
    INVARIANT: Scanner must extract channel count for all audio files.
    """
    audio_dir, _ = test_audio_dir

    found_files = scanner.scan_folder(audio_dir)

    for file_info in found_files:
        assert 'channels' in file_info, (
            f"Missing channels for {file_info['filepath']}"
        )
        assert file_info['channels'] in [1, 2], (
            f"Unexpected channel count {file_info['channels']} for {file_info['filepath']} "
            f"(expected 1 or 2)"
        )


@pytest.mark.integration
def test_scanner_extracts_format(test_audio_dir, scanner):
    """
    INVARIANT: Scanner must extract audio format for all files.
    """
    audio_dir, _ = test_audio_dir

    found_files = scanner.scan_folder(audio_dir)

    for file_info in found_files:
        assert 'format' in file_info, (
            f"Missing format for {file_info['filepath']}"
        )
        assert file_info['format'] is not None, (
            f"Null format for {file_info['filepath']}"
        )


# ============================================================================
# File Path Invariants (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_scanner_returns_absolute_paths(test_audio_dir, scanner):
    """
    INVARIANT: Scanner must return absolute file paths, not relative.

    Relative paths cause issues when working directory changes.
    """
    audio_dir, _ = test_audio_dir

    found_files = scanner.scan_folder(audio_dir)

    for file_info in found_files:
        filepath = file_info['filepath']
        assert os.path.isabs(filepath), (
            f"Scanner returned relative path: {filepath}"
        )


@pytest.mark.integration
def test_scanner_returns_existing_files(test_audio_dir, scanner):
    """
    INVARIANT: Scanner must only return paths to files that exist.
    """
    audio_dir, _ = test_audio_dir

    found_files = scanner.scan_folder(audio_dir)

    for file_info in found_files:
        filepath = file_info['filepath']
        assert os.path.exists(filepath), (
            f"Scanner returned non-existent file: {filepath}"
        )
        assert os.path.isfile(filepath), (
            f"Scanner returned directory, not file: {filepath}"
        )


@pytest.mark.integration
def test_scanner_returns_readable_files(test_audio_dir, scanner):
    """
    INVARIANT: Scanner must only return files that are readable.
    """
    audio_dir, _ = test_audio_dir

    found_files = scanner.scan_folder(audio_dir)

    for file_info in found_files:
        filepath = file_info['filepath']
        assert os.access(filepath, os.R_OK), (
            f"Scanner returned unreadable file: {filepath}"
        )


# ============================================================================
# Recursive Scanning Invariants (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_scanner_finds_files_in_subdirectories(library_manager):
    """
    INVARIANT: Scanner should find files in subdirectories (recursive scan).
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Create nested directory structure
        # music/
        #   artist1/
        #     album1/
        #       track1.wav
        #   artist2/
        #     track2.wav
        artist1_dir = os.path.join(temp_dir, "artist1", "album1")
        artist2_dir = os.path.join(temp_dir, "artist2")
        os.makedirs(artist1_dir)
        os.makedirs(artist2_dir)

        # Create files in subdirectories
        audio = np.random.randn(44100, 2)

        file1 = os.path.join(artist1_dir, "track1.wav")
        save_audio(file1, audio, 44100, subtype='PCM_16')

        file2 = os.path.join(artist2_dir, "track2.wav")
        save_audio(file2, audio, 44100, subtype='PCM_16')

        # Scan root directory
        scanner = LibraryScanner(library_manager)
        found_files = scanner.scan_folder(temp_dir)

        # Should find both files
        found_paths = {f['filepath'] for f in found_files}
        assert file1 in found_paths, "Scanner didn't find file in nested subdirectory"
        assert file2 in found_paths, "Scanner didn't find file in subdirectory"

    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# Edge Cases (P2 Priority)
# ============================================================================

@pytest.mark.integration
def test_scanner_handles_empty_directory(library_manager):
    """
    INVARIANT: Scanner should handle empty directory (return empty list, not crash).
    """
    temp_dir = tempfile.mkdtemp()
    try:
        scanner = LibraryScanner(library_manager)
        found_files = scanner.scan_folder(temp_dir)

        assert found_files == [] or len(found_files) == 0, (
            f"Scanner should return empty list for empty directory, got {len(found_files)} files"
        )

    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.integration
def test_scanner_handles_nonexistent_directory(library_manager):
    """
    INVARIANT: Scanner should handle non-existent directory gracefully.
    """
    scanner = LibraryScanner(library_manager)
    nonexistent_dir = "/tmp/this_directory_does_not_exist_12345"

    # Should not crash, should return empty or raise appropriate exception
    try:
        found_files = scanner.scan_folder(nonexistent_dir)
        assert found_files == [] or len(found_files) == 0, (
            "Scanner should return empty list for non-existent directory"
        )
    except (FileNotFoundError, OSError):
        # Acceptable behavior: raise exception for non-existent directory
        pass


@pytest.mark.integration
def test_scanner_ignores_non_audio_files(library_manager):
    """
    INVARIANT: Scanner should ignore non-audio files (.txt, .jpg, etc.).
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Create audio and non-audio files
        audio = np.random.randn(44100, 2)
        audio_file = os.path.join(temp_dir, "track.wav")
        save_audio(audio_file, audio, 44100, subtype='PCM_16')

        # Create non-audio files
        text_file = os.path.join(temp_dir, "info.txt")
        with open(text_file, 'w') as f:
            f.write("Not an audio file")

        image_file = os.path.join(temp_dir, "cover.jpg")
        with open(image_file, 'wb') as f:
            f.write(b'\x00\x01\x02\x03')  # Fake image data

        # Scan directory
        scanner = LibraryScanner(library_manager)
        found_files = scanner.scan_folder(temp_dir)

        # Should only find audio file
        assert len(found_files) == 1, (
            f"Scanner should find 1 audio file, found {len(found_files)}"
        )
        assert found_files[0]['filepath'] == audio_file, (
            "Scanner should only return audio file"
        )

    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# Summary Statistics
# ============================================================================

def test_summary_stats():
    """
    Print summary of what these tests validate.
    """
    print("\n" + "=" * 80)
    print("LIBRARY SCANNING INVARIANT TEST SUMMARY")
    print("=" * 80)
    print(f"Scan Completeness: 3 tests")
    print(f"Metadata Extraction: 4 tests")
    print(f"File Path Invariants: 3 tests")
    print(f"Recursive Scanning: 1 test")
    print(f"Edge Cases: 3 tests")
    print("=" * 80)
    print(f"TOTAL: 14 scanning invariant tests")
    print("=" * 80)
    print("\nThese tests validate critical scanning properties:")
    print("1. Completeness (all audio files found)")
    print("2. No duplicates (each file found once)")
    print("3. Determinism (same results on rescan)")
    print("4. Metadata extraction (duration, SR, channels, format)")
    print("5. Path correctness (absolute, existing, readable)")
    print("=" * 80 + "\n")
