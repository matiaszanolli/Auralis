"""
Boundary Tests for Library Management

Tests edge cases and boundary conditions for library operations.

Philosophy:
- Test empty library (0 tracks)
- Test single item (1 track)
- Test exact page boundaries
- Test offset boundaries
- Test large collections (10k+ tracks)
- Test string input boundaries

These tests complement the pagination invariant tests by focusing on
boundary conditions where off-by-one errors commonly occur.

NOTE: These tests require refactoring to use the new TrackRepository API
that takes a session_factory parameter instead of db_path.
#4691: the whole module was skipped with "Tests use old TrackRepository API -
requires session_factory parameter". That was true of the *fixtures*, not the
tests: `TrackRepository(db_path=":memory:")` and `repo.close()` are both gone
from the repository API. Rebuilt the same way `test_string_input_boundaries.py`
already was (#5154) — a file-backed throwaway engine, since an in-memory
SQLite URL gives each new connection its own empty database and the repository
opens a short-lived session per call. All 15 tests pass unchanged.
"""

import pytest

# Mark all tests in this module as needing refactoring
import shutil
import tempfile
from pathlib import Path

import numpy as np

from auralis.io.saver import save as save_audio
from auralis.library.repositories.album_repository import AlbumRepository
from auralis.library.repositories.artist_repository import ArtistRepository
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


def _dispose(track_repo: TrackRepository) -> None:
    """Dispose a throwaway repository's engine.

    `TrackRepository` has no `close()` — the old API this module was written
    against did. Reaching through to the session factory's bind is the only
    way to release the SQLite file handle deterministically, which matters
    because these tests build one database per test.
    """
    bind = getattr(track_repo.session_factory, "kw", {}).get("bind")
    if bind is not None:
        bind.dispose()


def _make_track_repo(db_path: Path | None = None) -> TrackRepository:
    """Build a repository the way every other test in this suite does.

    File-backed rather than ``:memory:`` so the repository's own short-lived
    sessions all see the same database — an in-memory SQLite URL gives each new
    connection its own empty one. Same fixture shape as
    `test_string_input_boundaries.py`, which had this identical breakage fixed
    first (#5154).
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auralis.library.models import Base

    if db_path is None:
        db_path = Path(tempfile.mkdtemp()) / "boundaries.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return TrackRepository(sessionmaker(bind=engine))


@pytest.fixture
def empty_library(tmp_path):
    """A library with no tracks."""
    return _make_track_repo(tmp_path / "boundaries_empty.db")


@pytest.fixture
def single_track_library(temp_audio_dir, tmp_path):
    """Create a library with exactly 1 track."""
    track_repo = _make_track_repo(tmp_path / "boundaries_single.db")

    # Create minimal audio file
    audio = np.random.randn(44100, 2)  # 1 second stereo
    filepath = temp_audio_dir / "track_001.wav"
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')

    # Add to database
    track_info = {
        "filepath": str(filepath),
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track_repo.add(track_info)

    return track_repo


def populate_library(track_repo, num_tracks: int, temp_dir: Path):
    """Helper to populate library with specified number of tracks."""
    for i in range(num_tracks):
        # Create minimal audio file
        audio = np.random.randn(44100, 2)  # 1 second stereo
        filepath = temp_dir / f"track_{i:05d}.wav"
        save_audio(str(filepath), audio, 44100, subtype='PCM_16')

        # Add to database
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i:05d}",
            "artist": f"Artist {i % 10}",  # 10 different artists
            "album": f"Album {i % 5}",     # 5 different albums
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track_repo.add(track_info)


# ============================================================================
# Boundary Tests - Empty Library
# ============================================================================

@pytest.mark.boundary
@pytest.mark.integration
def test_empty_library_get_all_returns_zero_tracks(empty_library):
    """
    BOUNDARY: Empty library (0 tracks).

    Tests that querying an empty library returns zero results correctly.
    """
    tracks, total = empty_library.get_all(limit=50, offset=0)

    assert len(tracks) == 0, "Empty library should return 0 tracks"
    assert total == 0, "Empty library should report total=0"


@pytest.mark.boundary
@pytest.mark.integration
def test_empty_library_pagination_with_offset_returns_empty(empty_library):
    """
    BOUNDARY: Pagination with offset on empty library.

    Tests that offset values on empty library don't cause errors.
    """
    # Try various offsets on empty library
    for offset in [0, 10, 100, 1000]:
        tracks, total = empty_library.get_all(limit=50, offset=offset)

        assert len(tracks) == 0, f"Empty library should return 0 tracks at offset {offset}"
        assert total == 0, "Empty library should report total=0"


@pytest.mark.boundary
@pytest.mark.integration
def test_empty_library_search_returns_no_results(empty_library):
    """
    BOUNDARY: Search on empty library.

    Tests that search queries on empty library return empty results.
    """
    results, total = empty_library.search("any query", limit=50, offset=0)

    assert len(results) == 0
    assert total == 0


# ============================================================================
# Boundary Tests - Single Item
# ============================================================================

@pytest.mark.boundary
@pytest.mark.integration
def test_single_track_library_returns_one_track(single_track_library):
    """
    BOUNDARY: Library with exactly 1 track.

    Tests that a library with one item returns it correctly.
    """
    tracks, total = single_track_library.get_all(limit=50, offset=0)

    assert len(tracks) == 1, "Single-track library should return 1 track"
    assert total == 1, "Single-track library should report total=1"


@pytest.mark.boundary
@pytest.mark.integration
def test_single_track_library_offset_one_returns_empty(single_track_library):
    """
    BOUNDARY: Offset=1 on single-item library (beyond bounds).

    Tests that offset beyond the only item returns empty results.
    """
    tracks, total = single_track_library.get_all(limit=50, offset=1)

    assert len(tracks) == 0, "Offset beyond single item should return 0 tracks"
    assert total == 1, "Total count should still be 1"


@pytest.mark.boundary
@pytest.mark.integration
def test_single_track_library_limit_one_returns_one(single_track_library):
    """
    BOUNDARY: limit=1 on single-item library.

    Tests that limit=1 returns the single item.
    """
    tracks, total = single_track_library.get_all(limit=1, offset=0)

    assert len(tracks) == 1
    assert total == 1


# ============================================================================
# Boundary Tests - Exact Page Boundaries
# ============================================================================

@pytest.mark.boundary
@pytest.mark.integration
def test_pagination_exact_page_size_50_tracks(temp_audio_dir):
    """
    BOUNDARY: Exactly 50 tracks with limit=50.

    Tests when total tracks exactly matches page size (no second page).
    """
    track_repo = _make_track_repo()
    try:
        populate_library(track_repo, num_tracks=50, temp_dir=temp_audio_dir)

        # First page should return all 50
        tracks_page1, total = track_repo.get_all(limit=50, offset=0)

        assert len(tracks_page1) == 50
        assert total == 50

        # Second page should be empty
        tracks_page2, _ = track_repo.get_all(limit=50, offset=50)

        assert len(tracks_page2) == 0
    finally:
        # The repository API has no close(); its sessions are short-lived and
        # the throwaway engine goes away with the temp directory (#4691).
        _dispose(track_repo)


@pytest.mark.boundary
@pytest.mark.integration
def test_pagination_exact_two_pages_100_tracks(temp_audio_dir):
    """
    BOUNDARY: Exactly 100 tracks with limit=50 (exactly 2 pages).

    Tests when total tracks is exactly 2x page size.
    """
    track_repo = _make_track_repo()
    try:
        populate_library(track_repo, num_tracks=100, temp_dir=temp_audio_dir)

        # First page
        tracks_page1, total = track_repo.get_all(limit=50, offset=0)
        assert len(tracks_page1) == 50
        assert total == 100

        # Second page (should be exactly full)
        tracks_page2, _ = track_repo.get_all(limit=50, offset=50)
        assert len(tracks_page2) == 50

        # Third page (should be empty)
        tracks_page3, _ = track_repo.get_all(limit=50, offset=100)
        assert len(tracks_page3) == 0
    finally:
        # The repository API has no close(); its sessions are short-lived and
        # the throwaway engine goes away with the temp directory (#4691).
        _dispose(track_repo)


@pytest.mark.boundary
@pytest.mark.integration
def test_pagination_one_track_over_page_boundary(temp_audio_dir):
    """
    BOUNDARY: 51 tracks with limit=50 (one track over).

    Tests minimal overflow past page boundary.
    """
    track_repo = _make_track_repo()
    try:
        populate_library(track_repo, num_tracks=51, temp_dir=temp_audio_dir)

        # First page: full (50 tracks)
        tracks_page1, total = track_repo.get_all(limit=50, offset=0)
        assert len(tracks_page1) == 50
        assert total == 51

        # Second page: partial (1 track)
        tracks_page2, _ = track_repo.get_all(limit=50, offset=50)
        assert len(tracks_page2) == 1
    finally:
        # The repository API has no close(); its sessions are short-lived and
        # the throwaway engine goes away with the temp directory (#4691).
        _dispose(track_repo)


# ============================================================================
# Boundary Tests - Offset Boundaries
# ============================================================================

@pytest.mark.boundary
@pytest.mark.integration
def test_offset_exactly_at_total_count_returns_empty(temp_audio_dir):
    """
    BOUNDARY: offset=total (exactly at the boundary).

    Tests that offset equal to total count returns empty results.
    """
    track_repo = _make_track_repo()
    try:
        populate_library(track_repo, num_tracks=100, temp_dir=temp_audio_dir)

        # offset=100 when total=100 should return empty
        tracks, total = track_repo.get_all(limit=50, offset=100)

        assert len(tracks) == 0
        assert total == 100
    finally:
        # The repository API has no close(); its sessions are short-lived and
        # the throwaway engine goes away with the temp directory (#4691).
        _dispose(track_repo)


@pytest.mark.boundary
@pytest.mark.integration
def test_offset_beyond_total_count_returns_empty(temp_audio_dir):
    """
    BOUNDARY: offset > total (beyond the boundary).

    Tests that offset beyond total count returns empty results.
    """
    track_repo = _make_track_repo()
    try:
        populate_library(track_repo, num_tracks=100, temp_dir=temp_audio_dir)

        # offset=200 when total=100
        tracks, total = track_repo.get_all(limit=50, offset=200)

        assert len(tracks) == 0
        assert total == 100
    finally:
        # The repository API has no close(); its sessions are short-lived and
        # the throwaway engine goes away with the temp directory (#4691).
        _dispose(track_repo)


@pytest.mark.boundary
@pytest.mark.integration
def test_offset_one_before_last_item(temp_audio_dir):
    """
    BOUNDARY: offset=total-1 (last valid offset).

    Tests accessing the very last item via offset.
    """
    track_repo = _make_track_repo()
    try:
        populate_library(track_repo, num_tracks=100, temp_dir=temp_audio_dir)

        # offset=99 when total=100 (last item)
        tracks, total = track_repo.get_all(limit=50, offset=99)

        assert len(tracks) == 1, "Should return the last item"
        assert total == 100
    finally:
        # The repository API has no close(); its sessions are short-lived and
        # the throwaway engine goes away with the temp directory (#4691).
        _dispose(track_repo)


# ============================================================================
# Boundary Tests - Limit Values
# ============================================================================

@pytest.mark.boundary
@pytest.mark.integration
def test_limit_zero_returns_empty(temp_audio_dir):
    """
    BOUNDARY: limit=0.

    Tests that limit=0 returns no results (but still reports total).
    """
    track_repo = _make_track_repo()
    try:
        populate_library(track_repo, num_tracks=100, temp_dir=temp_audio_dir)

        tracks, total = track_repo.get_all(limit=0, offset=0)

        assert len(tracks) == 0, "limit=0 should return 0 tracks"
        assert total == 100, "Total count should still be reported correctly"
    finally:
        # The repository API has no close(); its sessions are short-lived and
        # the throwaway engine goes away with the temp directory (#4691).
        _dispose(track_repo)


@pytest.mark.boundary
@pytest.mark.integration
def test_limit_one_returns_single_track(temp_audio_dir):
    """
    BOUNDARY: limit=1.

    Tests minimum non-zero limit.
    """
    track_repo = _make_track_repo()
    try:
        populate_library(track_repo, num_tracks=100, temp_dir=temp_audio_dir)

        tracks, total = track_repo.get_all(limit=1, offset=0)

        assert len(tracks) == 1
        assert total == 100
    finally:
        # The repository API has no close(); its sessions are short-lived and
        # the throwaway engine goes away with the temp directory (#4691).
        _dispose(track_repo)


@pytest.mark.boundary
@pytest.mark.integration
def test_limit_larger_than_total_returns_all(temp_audio_dir):
    """
    BOUNDARY: limit > total count.

    Tests that large limit values don't cause errors.
    """
    track_repo = _make_track_repo()
    try:
        populate_library(track_repo, num_tracks=50, temp_dir=temp_audio_dir)

        # Request 1000 tracks when only 50 exist
        tracks, total = track_repo.get_all(limit=1000, offset=0)

        assert len(tracks) == 50, "Should return all 50 tracks"
        assert total == 50
    finally:
        # The repository API has no close(); its sessions are short-lived and
        # the throwaway engine goes away with the temp directory (#4691).
        _dispose(track_repo)
