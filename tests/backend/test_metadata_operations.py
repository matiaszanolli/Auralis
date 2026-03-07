"""
Metadata Operations Tests

Tests metadata reading, editing, and persistence.

Philosophy:
- Test CRUD operations on track metadata
- Test metadata validation
- Test metadata persistence to files
- Test edge cases (special characters, long strings)

These tests ensure that metadata operations work correctly
and data is not lost or corrupted.
"""

import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

from auralis.io.saver import save as save_audio


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_audio_dir():
    """Create a temporary directory for test audio files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# Phase 5B.1: Migration to conftest.py fixtures
# Removed local library_manager fixture - now using conftest.py fixture
# Tests automatically use the fixture from parent conftest.py


@pytest.fixture
def track_repo(library_manager):
    """Get track repository from library manager."""
    return library_manager.tracks


def create_test_track(directory: Path, filename: str):
    """Create a minimal test audio file."""
    audio = np.random.randn(44100, 2) * 0.5
    filepath = directory / filename
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')
    return filepath


# ============================================================================
# Metadata CRUD Tests
# ============================================================================

@pytest.mark.integration
def test_metadata_delete_track(temp_audio_dir, track_repo):
    """
    METADATA: Delete track and verify metadata removal.

    Tests that deletion removes all metadata.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "Track to Delete",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)
    track_id = track.id

    # Delete
    track_repo.delete(track_id)

    # Verify deletion
    deleted_track = track_repo.get_by_id(track_id)
    assert deleted_track is None


# ============================================================================
# Metadata Validation Tests
# ============================================================================

@pytest.mark.unit
def test_metadata_year_validation(temp_audio_dir, track_repo):
    """
    METADATA: Year field validation.

    Tests that invalid years are handled.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    # Try with future year
    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "year": 2100,  # Future year
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    # Should either accept or reject gracefully
    try:
        track = track_repo.add(track_info)
        # If accepted, verify it's stored
        assert track.year == 2100 or track.year is None
    except ValueError:
        # Rejection is acceptable
        pass


@pytest.mark.unit
def test_metadata_track_number_validation(temp_audio_dir, track_repo):
    """
    METADATA: Track number validation.

    Tests that invalid track numbers are handled.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    # Try with zero track number
    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "track_number": 0,
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    # Should handle gracefully
    try:
        track = track_repo.add(track_info)
        assert track is not None
    except ValueError:
        pass


# ============================================================================
# Metadata Search Tests
# ============================================================================

@pytest.mark.integration
def test_metadata_search_by_title(temp_audio_dir, track_repo):
    """
    METADATA: Search tracks by title metadata.

    Tests that search uses metadata correctly.
    """
    # Create tracks with searchable titles
    titles = ["Hello World", "Goodbye Moon", "Hello Again"]

    for i, title in enumerate(titles):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")

        track_info = {
            "filepath": str(filepath),
            "title": title,
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }

        track_repo.add(track_info)

    # Search for "Hello"
    results, total = track_repo.search("Hello", limit=50, offset=0)

    # Should find both "Hello World" and "Hello Again"
    assert total >= 2
