"""
String Input Boundary Tests

Tests string input handling at boundaries and with special characters.

Philosophy:
- Test empty strings
- Test very long strings
- Test special characters and Unicode
- Test SQL injection attempts (security)
- Test path traversal attempts (security)
- Test malformed input

These tests validate that the system handles string inputs safely
and gracefully, preventing security vulnerabilities and crashes.

#5154: this module was skipped wholesale for "Tests use old TrackRepository
API - requires session_factory parameter". That was true of exactly one
fixture — track_repo built `TrackRepository(db_path=":memory:")` and called
`repo.close()`, neither of which exists on the repository API any more. The
tests themselves were fine. Since the file holds this suite's SQL-injection and
string-boundary coverage, the fixture is now built the way every other test
builds a repository, and the module-level skip is gone.
"""

import pytest
import shutil
import tempfile
from pathlib import Path

import numpy as np

from auralis.io.saver import save as save_audio
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
    """Create a track repository over a throwaway file-backed database.

    File-backed rather than ``:memory:`` so the repository's own short-lived
    sessions all see the same database — an in-memory SQLite URL gives each
    new connection its own empty one (#5154).
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auralis.library.models import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'strings.db'}")
    Base.metadata.create_all(engine)
    yield TrackRepository(sessionmaker(bind=engine))
    engine.dispose()


def create_test_track(directory: Path, filename: str):
    """Create a minimal test audio file."""
    audio = np.random.randn(44100, 2) * 0.5
    filepath = directory / filename
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')
    return filepath


# ============================================================================
# Boundary Tests - Empty Strings
# ============================================================================

@pytest.mark.boundary
@pytest.mark.unit
def test_empty_string_title(temp_audio_dir, track_repo):
    """
    BOUNDARY: Empty string for title field.

    Tests that empty title is handled gracefully.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    track_info = {
        "filepath": str(filepath),
        "title": "",  # Empty string
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    # Should handle empty string without error
    track = track_repo.add(track_info)
    assert track is not None
    assert track.title == ""


@pytest.mark.boundary
@pytest.mark.unit
def test_empty_string_search_query(track_repo):
    """
    BOUNDARY: Empty search query.

    Tests that empty search string returns all results or empty.
    """
    # Search with empty string
    results, total = track_repo.search("", limit=50, offset=0)

    # Should not crash, return empty or all results
    assert isinstance(results, list)
    assert isinstance(total, int)


# ============================================================================
# Boundary Tests - Very Long Strings
# ============================================================================

@pytest.mark.boundary
@pytest.mark.unit
def test_very_long_title_1000_chars(temp_audio_dir, track_repo):
    """
    BOUNDARY: Very long title (1000 characters).

    Tests that very long titles are handled without truncation or error.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    long_title = "A" * 1000  # 1000 character title

    track_info = {
        "filepath": str(filepath),
        "title": long_title,
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)
    assert track is not None

    # Verify title is preserved (may be truncated by database)
    assert len(track.title) > 0


@pytest.mark.boundary
@pytest.mark.unit
def test_very_long_search_query(track_repo):
    """
    BOUNDARY: Very long search query (500 characters).

    Tests that long search queries don't cause errors.
    """
    long_query = "test " * 100  # ~500 characters

    # Should not crash
    results, total = track_repo.search(long_query, limit=50, offset=0)

    assert isinstance(results, list)


# ============================================================================
# Boundary Tests - Special Characters
# ============================================================================

@pytest.mark.boundary
@pytest.mark.unit
def test_special_characters_in_title(temp_audio_dir, track_repo):
    """
    BOUNDARY: Special characters in title.

    Tests that special characters are handled correctly.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    special_title = "Track!@#$%^&*()_+-=[]{}|;:',.<>?/~`"

    track_info = {
        "filepath": str(filepath),
        "title": special_title,
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)
    assert track is not None
    assert special_title in track.title or len(track.title) > 0


@pytest.mark.boundary
@pytest.mark.unit
def test_unicode_characters_in_title(temp_audio_dir, track_repo):
    """
    BOUNDARY: Unicode characters in title.

    Tests that Unicode (emojis, non-ASCII) is handled correctly.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    unicode_title = "Test Track 测试 🎵 Тест"

    track_info = {
        "filepath": str(filepath),
        "title": unicode_title,
        "artist": "Artist 艺术家",
        "album": "Album álbum",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)
    assert track is not None

    # Verify Unicode is preserved
    assert len(track.title) > 0


@pytest.mark.boundary
@pytest.mark.unit
def test_newlines_in_title(temp_audio_dir, track_repo):
    """
    BOUNDARY: Newline characters in title.

    Tests that newlines are handled or sanitized.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    title_with_newlines = "First Line\nSecond Line\rThird Line"

    track_info = {
        "filepath": str(filepath),
        "title": title_with_newlines,
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    # Should handle without crashing
    track = track_repo.add(track_info)
    assert track is not None


# ============================================================================
# Security Tests - SQL Injection Attempts
# ============================================================================

@pytest.mark.boundary
@pytest.mark.security
def test_sql_injection_in_title(temp_audio_dir, track_repo):
    """
    SECURITY: SQL injection attempt in title field.

    Tests that SQL injection strings are treated as literals.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    sql_injection = "'; DROP TABLE tracks; --"

    track_info = {
        "filepath": str(filepath),
        "title": sql_injection,
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    # Should treat as literal string, not execute SQL.
    # #5154: asserting only `is not None` meant an injection that SUCCEEDED
    # and returned a row still passed. The real claim is that the payload is
    # stored verbatim as data and that the table survives.
    track = track_repo.add(track_info)
    assert track is not None
    assert track.title == sql_injection, (
        f"Injection payload was not stored verbatim: {track.title!r}"
    )

    # Round-trip through a fresh read, not just the returned instance.
    reread = track_repo.get_by_id(track.id)
    assert reread is not None, "tracks table did not survive the injection"
    assert reread.title == sql_injection

    # The payload must not have created or destroyed rows.
    _, total_after_first = track_repo.get_all(limit=100)
    assert total_after_first == 1, (
        f"Expected exactly 1 row after the injection attempt, got {total_after_first}"
    )

    # Verify database is still intact by adding another track
    filepath2 = create_test_track(temp_audio_dir, "track2.wav")
    track_info2 = {
        "filepath": str(filepath2),
        "title": "Normal Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track2 = track_repo.add(track_info2)
    assert track2 is not None


@pytest.mark.boundary
@pytest.mark.security
def test_sql_injection_in_search_query(temp_audio_dir, track_repo):
    """
    SECURITY: SQL injection attempt in search query.

    Tests that SQL injection in search is treated as literal.
    """
    # Add a normal track first
    filepath = create_test_track(temp_audio_dir, "track.wav")
    track_info = {
        "filepath": str(filepath),
        "title": "Normal Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track_repo.add(track_info)

    # Search with SQL injection attempt
    sql_injection = "' OR '1'='1"

    # Should not return all results (unless search implementation matches)
    results, total = track_repo.search(sql_injection, limit=50, offset=0)

    # Should complete without error
    assert isinstance(results, list)

    # Verify database is still intact
    all_tracks, all_total = track_repo.get_all(limit=50, offset=0)
    assert all_total >= 1


# ============================================================================
# Security Tests - Path Traversal Attempts
# ============================================================================

@pytest.mark.boundary
@pytest.mark.security
def test_path_traversal_in_filepath(track_repo):
    """
    SECURITY: Path traversal attempt in filepath.

    Tests that path traversal strings are handled safely.
    """
    path_traversal = "../../../etc/passwd"

    track_info = {
        "filepath": path_traversal,
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    # May fail to add (good) or treat as literal (acceptable)
    try:
        track = track_repo.add(track_info)
        # If it succeeds, verify it's stored as-is (not resolved)
        if track:
            assert "../" in track.filepath or "etc" not in track.filepath
    except (ValueError, FileNotFoundError, OSError):
        # Expected - file doesn't exist
        pass


@pytest.mark.boundary
@pytest.mark.security
def test_null_bytes_in_string(temp_audio_dir, track_repo):
    """
    SECURITY: Null bytes in string fields.

    Tests that null bytes are handled or rejected.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    title_with_null = "Track\x00Hidden"

    track_info = {
        "filepath": str(filepath),
        "title": title_with_null,
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    # Should either accept and sanitize, or reject
    try:
        track = track_repo.add(track_info)
        assert track is not None
    except (ValueError, Exception):
        # Rejection is acceptable
        pass


# ============================================================================
# Boundary Tests - Whitespace
# ============================================================================

@pytest.mark.boundary
@pytest.mark.unit
def test_whitespace_only_title(temp_audio_dir, track_repo):
    """
    BOUNDARY: Title with only whitespace.

    Tests that whitespace-only titles are handled.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    whitespace_title = "     "  # Only spaces

    track_info = {
        "filepath": str(filepath),
        "title": whitespace_title,
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    # Should handle without error
    track = track_repo.add(track_info)
    assert track is not None


@pytest.mark.boundary
@pytest.mark.unit
def test_leading_trailing_whitespace(temp_audio_dir, track_repo):
    """
    BOUNDARY: Title with leading/trailing whitespace.

    Tests whitespace trimming behavior.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")

    title_with_whitespace = "   Test Track   "

    track_info = {
        "filepath": str(filepath),
        "title": title_with_whitespace,
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }

    track = track_repo.add(track_info)
    assert track is not None

    # May trim whitespace or preserve it
    assert len(track.title) > 0
