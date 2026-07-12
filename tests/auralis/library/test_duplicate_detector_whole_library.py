"""
Regression tests for DuplicateDetector.find_duplicates(directories=None) (#4241).

Previously the "check entire library" branch was a `pass` no-op that always
returned an empty duplicates list. It now pages through the library via
LibraryManager and hashes each track's file on disk, or raises
NotImplementedError if constructed without a library_manager.
"""

from __future__ import annotations

import os

import pytest

from auralis.library.scanner.audio_analyzer import AudioAnalyzer
from auralis.library.scanner.duplicate_detector import DuplicateDetector
from auralis.library.scanner.file_discovery import FileDiscovery


@pytest.fixture
def _detector(library_manager):
    return DuplicateDetector(FileDiscovery(), AudioAnalyzer(), library_manager)


def _write_temp_file(tmp_path, name: str, content: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def test_finds_duplicates_across_entire_library(tmp_path, library_manager, _detector):
    dup_a = _write_temp_file(tmp_path, "a.wav", b"identical-content" * 1000)
    dup_b = _write_temp_file(tmp_path, "b.wav", b"identical-content" * 1000)
    unique = _write_temp_file(tmp_path, "c.wav", b"different-content" * 1000)

    for filepath in (dup_a, dup_b, unique):
        track = library_manager.add_track({'filepath': filepath, 'title': os.path.basename(filepath)})
        assert track is not None

    duplicates = _detector.find_duplicates(directories=None)

    assert len(duplicates) == 1
    assert set(duplicates[0]) == {dup_a, dup_b}


def test_no_duplicates_returns_empty_list(tmp_path, library_manager, _detector):
    only = _write_temp_file(tmp_path, "solo.wav", b"solo-content")
    track = library_manager.add_track({'filepath': only, 'title': 'solo'})
    assert track is not None

    assert _detector.find_duplicates(directories=None) == []


def test_missing_file_on_disk_is_skipped_not_fatal(tmp_path, library_manager, _detector):
    dup_a = _write_temp_file(tmp_path, "a.wav", b"identical-content" * 1000)
    dup_b = _write_temp_file(tmp_path, "b.wav", b"identical-content" * 1000)
    now_missing = _write_temp_file(tmp_path, "gone.wav", b"will be deleted")

    for filepath in (dup_a, dup_b, now_missing):
        track = library_manager.add_track({'filepath': filepath, 'title': os.path.basename(filepath)})
        assert track is not None

    # Simulate the file having moved/been deleted since it was added to the
    # library — add_track() itself requires the file to exist at insert time.
    os.remove(now_missing)

    duplicates = _detector.find_duplicates(directories=None)

    assert len(duplicates) == 1
    assert set(duplicates[0]) == {dup_a, dup_b}


def test_raises_without_library_manager():
    detector = DuplicateDetector(FileDiscovery(), AudioAnalyzer(), library_manager=None)

    with pytest.raises(NotImplementedError):
        detector.find_duplicates(directories=None)
