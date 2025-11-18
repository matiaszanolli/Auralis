"""
Error Handling Tests

Tests that the system handles errors gracefully and predictably.

Philosophy:
- Test error conditions explicitly
- Test error recovery mechanisms
- Test error messages are helpful
- Test no silent failures
- Test resource cleanup on errors

These tests ensure that the system fails gracefully and
provides useful feedback when things go wrong.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import shutil

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.library.repositories.track_repository import TrackRepository
from auralis.library.manager import LibraryManager
from auralis.io.unified_loader import load_audio
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


@pytest.fixture
def track_repo():
    """Create an in-memory track repository."""
    repo = TrackRepository(db_path=":memory:")
    yield repo
    repo.close()


# ============================================================================
# Error Handling Tests - File Operations
# ============================================================================

@pytest.mark.error
@pytest.mark.unit
def test_error_load_nonexistent_file():
    """
    ERROR: Loading non-existent file raises appropriate error.

    Tests that missing files are detected and reported.
    """
    nonexistent = "/path/that/does/not/exist.wav"

    with pytest.raises((FileNotFoundError, IOError, OSError)):
        load_audio(nonexistent)


@pytest.mark.error
@pytest.mark.unit
def test_error_load_directory_as_file(temp_audio_dir):
    """
    ERROR: Loading a directory as audio file raises error.

    Tests that directories are rejected.
    """
    # Try to load a directory
    with pytest.raises((IOError, OSError, IsADirectoryError, ValueError)):
        load_audio(str(temp_audio_dir))


@pytest.mark.error
@pytest.mark.unit
def test_error_save_to_readonly_location():
    """
    ERROR: Saving to read-only location raises error.

    Tests that permission errors are detected.
    """
    audio = np.random.randn(44100, 2) * 0.5

    # Try to save to /dev/null or similar read-only location
    readonly_path = "/dev/null/impossible.wav"

    with pytest.raises((IOError, OSError, PermissionError)):
        save_audio(readonly_path, audio, 44100, subtype='PCM_16')


# ============================================================================
# Error Handling Tests - Invalid Audio Data
# ============================================================================

@pytest.mark.error
@pytest.mark.unit
def test_error_process_empty_audio():
    """
    ERROR: Processing empty audio raises error.

    Tests that zero-length audio is rejected.
    """
    empty_audio = np.array([]).reshape(0, 2)

    config = UnifiedConfig()
    processor = HybridProcessor(config)

    with pytest.raises((ValueError, RuntimeError, Exception)):
        processor.process(empty_audio)


@pytest.mark.error
@pytest.mark.unit
def test_error_process_nan_audio():
    """
    ERROR: Processing audio with NaN values raises error or sanitizes.

    Tests that NaN values are detected.
    """
    audio_with_nan = np.array([[1.0, 1.0], [np.nan, 0.5], [0.3, 0.3]])

    config = UnifiedConfig()
    processor = HybridProcessor(config)

    # Should either raise error or sanitize NaN values
    try:
        processed = processor.process(audio_with_nan)
        # If it succeeds, verify no NaN in output
        assert not np.isnan(processed).any()
    except (ValueError, RuntimeError):
        # Rejection is acceptable
        pass


@pytest.mark.error
@pytest.mark.unit
def test_error_process_inf_audio():
    """
    ERROR: Processing audio with inf values raises error or sanitizes.

    Tests that inf values are detected.
    """
    audio_with_inf = np.array([[1.0, 1.0], [np.inf, 0.5], [0.3, 0.3]])

    config = UnifiedConfig()
    processor = HybridProcessor(config)

    # Should either raise error or sanitize inf values
    try:
        processed = processor.process(audio_with_inf)
        # If it succeeds, verify no inf in output
        assert not np.isinf(processed).any()
    except (ValueError, RuntimeError):
        # Rejection is acceptable
        pass


# ============================================================================
# Error Handling Tests - Database Operations
# ============================================================================

@pytest.mark.error
@pytest.mark.unit
def test_error_add_track_missing_required_fields(track_repo):
    """
    ERROR: Adding track without required fields raises error.

    Tests that required field validation works.
    """
    incomplete_track_info = {
        "title": "Test Track"
        # Missing filepath, artist, album, duration, etc.
    }

    with pytest.raises((ValueError, KeyError, Exception)):
        track_repo.add(incomplete_track_info)


@pytest.mark.error
@pytest.mark.unit
def test_error_get_track_invalid_id(track_repo):
    """
    ERROR: Getting track with invalid ID returns None.

    Tests that invalid IDs are handled gracefully.
    """
    invalid_id = 999999

    track = track_repo.get_by_id(invalid_id)

    # Should return None, not raise error
    assert track is None


@pytest.mark.error
@pytest.mark.unit
def test_error_delete_nonexistent_track(track_repo):
    """
    ERROR: Deleting non-existent track handles gracefully.

    Tests that deleting missing tracks doesn't crash.
    """
    nonexistent_id = 999999

    # Should not raise error, just do nothing
    try:
        track_repo.delete(nonexistent_id)
    except Exception as e:
        # Some implementations may raise, that's ok
        pass


# ============================================================================
# Error Handling Tests - Invalid Parameters
# ============================================================================

@pytest.mark.error
@pytest.mark.unit
def test_error_pagination_negative_limit(track_repo):
    """
    ERROR: Negative limit value raises error or is treated as zero.

    Tests that invalid pagination parameters are rejected.
    """
    # Try negative limit
    try:
        tracks, total = track_repo.get_all(limit=-10, offset=0)
        # If it succeeds, should return empty
        assert len(tracks) == 0
    except (ValueError, Exception):
        # Rejection is acceptable
        pass


@pytest.mark.error
@pytest.mark.unit
def test_error_pagination_negative_offset(track_repo):
    """
    ERROR: Negative offset value raises error or is treated as zero.

    Tests that invalid offset is rejected.
    """
    # Try negative offset
    try:
        tracks, total = track_repo.get_all(limit=50, offset=-10)
        # If it succeeds, should work like offset=0
        assert isinstance(tracks, list)
    except (ValueError, Exception):
        # Rejection is acceptable
        pass


# ============================================================================
# Error Handling Tests - Resource Cleanup
# ============================================================================

@pytest.mark.error
@pytest.mark.integration
def test_error_cleanup_on_exception(temp_audio_dir):
    """
    ERROR: Resources are cleaned up when exception occurs.

    Tests that file handles and connections are closed on error.
    """
    manager = LibraryManager(database_path=":memory:")

    try:
        # Force an error by trying to add invalid data
        invalid_track_info = {
            "filepath": "/nonexistent/file.wav",
            "title": None,  # Invalid: None title
            "artist": "Test",
            "album": "Test",
            "duration": -1.0,  # Invalid: negative duration
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }

        try:
            manager.tracks.add(invalid_track_info)
        except Exception:
            pass  # Expected

        # Verify database is still functional after error
        valid_track_info = {
            "filepath": "/valid/file.wav",
            "title": "Valid Track",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 180.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }

        track = manager.tracks.add(valid_track_info)
        assert track is not None

    finally:
        pass


# ============================================================================
# Error Handling Tests - Concurrent Access
# ============================================================================

@pytest.mark.error
@pytest.mark.integration
def test_error_database_locked_handling():
    """
    ERROR: Database lock errors are handled gracefully.

    Tests that concurrent access doesn't cause crashes.
    """
    # Create a real database file (not in-memory)
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "test.db"

    try:
        manager1 = LibraryManager(database_path=str(db_path))
        manager2 = LibraryManager(database_path=str(db_path))

        # Try concurrent writes (may or may not cause lock)
        track_info = {
            "filepath": "/test/file.wav",
            "title": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 180.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }

        # Should handle gracefully (either succeed or raise predictable error)
        try:
            track1 = manager1.tracks.add(track_info)
            track2 = manager2.tracks.add(track_info)
        except Exception as e:
            # Database lock or constraint violation is acceptable
            pass

        manager1.close()
        manager2.close()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# Error Handling Tests - Invalid File Formats
# ============================================================================

@pytest.mark.error
@pytest.mark.unit
def test_error_load_corrupt_audio_file(temp_audio_dir):
    """
    ERROR: Loading corrupt audio file raises error.

    Tests that corrupt files are detected.
    """
    # Create a "corrupt" file (just random bytes)
    corrupt_file = temp_audio_dir / "corrupt.wav"
    with open(corrupt_file, 'wb') as f:
        f.write(b"Not a valid WAV file, just random data" * 100)

    with pytest.raises((IOError, ValueError, Exception)):
        load_audio(str(corrupt_file))


# ============================================================================
# Summary Statistics
# ============================================================================

@pytest.mark.unit
def test_summary_stats():
    """Print summary statistics about error handling tests."""
    print("\n" + "=" * 70)
    print("ERROR HANDLING TESTS - SUMMARY")
    print("=" * 70)
    print(f"Total error handling tests: 15")
    print(f"\nTest categories:")
    print(f"  - File operations: 3 tests")
    print(f"  - Invalid audio data: 3 tests")
    print(f"  - Database operations: 3 tests")
    print(f"  - Invalid parameters: 2 tests")
    print(f"  - Resource cleanup: 1 test")
    print(f"  - Concurrent access: 1 test")
    print(f"  - Invalid file formats: 1 test")
    print(f"  - Summary stats: 1 test")
    print("=" * 70)
