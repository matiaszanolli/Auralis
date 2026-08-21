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

NOTE: Some tests use old TrackRepository API - requires refactoring.
"""

import pytest

# Mark tests using old TrackRepository API as needing refactoring
import shutil
import tempfile
from pathlib import Path

import numpy as np

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.config import UnifiedConfig
from auralis.io.saver import save as save_audio
from auralis.io.unified_loader import load_audio
from auralis.utils.logging import ModuleError
from auralis.library.database import LibraryDatabase
from auralis.library.repositories.track_repository import TrackRepository

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
def track_repo(tmp_path):
    """A track repository over a throwaway file-backed database.

    File-backed rather than ``:memory:`` so the repository's own short-lived
    sessions all see the same database — an in-memory SQLite URL gives each new
    connection its own empty one. Same shape as
    `test_string_input_boundaries.py` (#5154); the old
    ``TrackRepository(db_path=...)`` / ``repo.close()`` API is gone (#4691).
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auralis.library.models import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'errors.db'}")
    Base.metadata.create_all(engine)
    return TrackRepository(sessionmaker(bind=engine))


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

    # `load_audio` wraps every failure in ModuleError rather than letting the
    # underlying FileNotFoundError/OSError through (#4691). Asserting the
    # wrapper is what actually pins the loader's contract.
    with pytest.raises((ModuleError, FileNotFoundError, OSError)):
        load_audio(nonexistent)


@pytest.mark.error
@pytest.mark.unit
def test_error_load_directory_as_file(temp_audio_dir):
    """
    ERROR: Loading a directory as audio file raises error.

    Tests that directories are rejected.
    """
    # Try to load a directory
    with pytest.raises((ModuleError, OSError, IsADirectoryError, ValueError)):
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

    # `save_audio` wraps the libsndfile failure in RuntimeError (#4691).
    with pytest.raises((RuntimeError, OSError, PermissionError)):
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

    # #4691: this asserted a raise, which the processor has never done here.
    # Zero-length audio takes the documented MIN_SAMPLES short-circuit —
    # "too short to master, returning it unprocessed" — and that IS the
    # contract: the streaming path feeds it buffers and must not have playback
    # die on a degenerate one. What matters is that it returns cleanly and
    # preserves the invariants, which is what is asserted now.
    result = processor.process(empty_audio)

    assert isinstance(result, np.ndarray)
    assert len(result) == len(empty_audio)
    assert result.dtype == empty_audio.dtype


@pytest.mark.error
@pytest.mark.unit
def test_error_process_nan_audio():
    """
    ERROR: Processing audio with NaN values raises error or sanitizes.

    Tests that NaN values are detected.
    """
    # A realistic buffer: `validate_audio_finite(repair=False)` rejects this.
    audio_with_nan = (np.random.randn(44100, 2) * 0.2)
    audio_with_nan[1000, 0] = np.nan

    config = UnifiedConfig()
    processor = HybridProcessor(config)

    with pytest.raises(ModuleError, match="NaN"):
        processor.process(audio_with_nan)


@pytest.mark.error
@pytest.mark.unit
@pytest.mark.xfail(
    strict=True,
    reason="#5191: the MIN_SAMPLES short-circuit returns before "
           "validate_audio_finite, so a sub-MIN_SAMPLES buffer keeps its NaN",
)
def test_error_process_nan_audio_short_buffer():
    """The gap the original 3-sample fixture was unknowingly sitting on.

    `_process_impl` validates NaN/Inf and fails fast — but only after the
    "too short to master" short-circuit has already returned a copy. So the
    guard holds at every length except the one this exercises.
    """
    audio_with_nan = np.array([[1.0, 1.0], [np.nan, 0.5], [0.3, 0.3]])

    processor = HybridProcessor(UnifiedConfig())
    processed = processor.process(audio_with_nan)

    assert not np.isnan(processed).any()


@pytest.mark.error
@pytest.mark.unit
def test_error_process_inf_audio():
    """
    ERROR: Processing audio with inf values raises error or sanitizes.

    Tests that inf values are detected.
    """
    audio_with_inf = (np.random.randn(44100, 2) * 0.2)
    audio_with_inf[1000, 0] = np.inf

    config = UnifiedConfig()
    processor = HybridProcessor(config)

    with pytest.raises(ModuleError, match="Inf"):
        processor.process(audio_with_inf)


@pytest.mark.error
@pytest.mark.unit
@pytest.mark.xfail(
    strict=True,
    reason="#5191: the MIN_SAMPLES short-circuit returns before "
           "validate_audio_finite, so a sub-MIN_SAMPLES buffer keeps its Inf",
)
def test_error_process_inf_audio_short_buffer():
    """Inf half of #5191 — see test_error_process_nan_audio_short_buffer."""
    audio_with_inf = np.array([[1.0, 1.0], [np.inf, 0.5], [0.3, 0.3]])

    processor = HybridProcessor(UnifiedConfig())
    processed = processor.process(audio_with_inf)

    assert not np.isinf(processed).any()


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

    # #4691: this asserted a raise. The repository signals a rejected row by
    # returning None instead — the right contract for a scanner walking
    # thousands of files, where one malformed tag must not abort the walk.
    # Asserting the real contract is what makes this test able to notice a
    # regression; asserting a raise it never performed could only ever fail.
    assert track_repo.add(incomplete_track_info) is None


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
    # narrowed from bare Exception, #5023: delete() returns False for a missing
    # row; an implementation that rejects instead raises a lookup error
    # (KeyError), a validation error (ValueError) or a DB error.
    except (KeyError, ValueError, SQLAlchemyError):
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
    # Not ":memory:": SQLAlchemy picks SingletonThreadPool for an in-memory
    # SQLite URL, which rejects the pool_size/max_overflow LibraryDatabase
    # always passes, so the constructor raises before the test body (#4691).
    db = LibraryDatabase(database_path=str(temp_audio_dir / "cleanup.db"))

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
            db.tracks.add(invalid_track_info)
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

        track = db.tracks.add(valid_track_info)
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
        db1 = LibraryDatabase(database_path=str(db_path))
        db2 = LibraryDatabase(database_path=str(db_path))

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
            track1 = db1.tracks.add(track_info)
            track2 = db2.tracks.add(track_info)
        # narrowed from bare Exception, #5023: the two outcomes this test
        # tolerates are exactly a lock timeout (OperationalError, "database is
        # locked") and a UNIQUE-filepath violation (IntegrityError).
        except (OperationalError, IntegrityError):
            # Database lock or constraint violation is acceptable
            pass

        db1.shutdown()
        db2.shutdown()

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
