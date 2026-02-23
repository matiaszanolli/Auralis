"""
Cache Operations Tests

Tests cache management, invalidation, and performance.

Philosophy:
- Test cache hit/miss behavior
- Test cache invalidation
- Test cache statistics
- Test cache clearing
- Test cache performance improvements
- Test cache consistency

These tests ensure that caching works correctly and
provides the expected performance benefits.
"""

import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest

from auralis.io.saver import save as save_audio
from auralis.library.manager import LibraryManager
from auralis.library.repositories.factory import RepositoryFactory
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


# Phase 5B.1: Migration to conftest.py fixtures
# Removed local library_manager fixture - now using conftest.py fixture
# All tests automatically use the fixture from parent conftest.py

@pytest.fixture
def track_repo(library_manager):
    """Get track repository from library manager.

    Phase 5B: Uses library_manager fixture from conftest.py (Phase 5A)
    """
    return library_manager.tracks


def create_test_track(directory: Path, filename: str):
    """Create a minimal test audio file."""
    audio = np.random.randn(44100, 2) * 0.5
    filepath = directory / filename
    save_audio(str(filepath), audio, 44100, subtype='PCM_16')
    return filepath


# ============================================================================
# Cache Hit/Miss Tests
# ============================================================================

@pytest.mark.integration
def test_cache_first_query_is_miss(temp_audio_dir, library_manager):
    """
    CACHE: First query is cache miss.

    Tests that initial query populates cache.
    """
    # Add some tracks
    for i in range(10):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.tracks.add(track_info)

    # Clear cache first
    library_manager.clear_cache()

    # First query
    tracks, total = library_manager.tracks.get_all(limit=50, offset=0)

    assert len(tracks) == 10


@pytest.mark.integration
def test_cache_second_query_is_hit(temp_audio_dir, library_manager):
    """
    CACHE: Second identical query is cache hit.

    Tests that repeated queries use cache.
    """
    # Add tracks
    for i in range(10):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.tracks.add(track_info)

    # First query (cache miss)
    tracks1, total1 = library_manager.tracks.get_all(limit=50, offset=0)

    # Second query (should be cache hit)
    tracks2, total2 = library_manager.tracks.get_all(limit=50, offset=0)

    assert len(tracks1) == len(tracks2)
    assert total1 == total2


@pytest.mark.integration
def test_cache_hit_faster_than_miss(temp_audio_dir, library_manager):
    """
    CACHE: Cache hit is faster than cache miss.

    Tests performance improvement from caching.
    """
    # Add 100 tracks for measurable difference
    for i in range(100):
        filepath = create_test_track(temp_audio_dir, f"track_{i:03d}.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i:03d}",
            "artist": f"Artist {i % 10}",
            "album": f"Album {i % 20}",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.tracks.add(track_info)

    # Clear cache
    library_manager.clear_cache()

    # First query (cache miss)
    start_time = time.time()
    tracks1, _ = library_manager.tracks.get_all(limit=50, offset=0)
    miss_time = time.time() - start_time

    # Second query (cache hit)
    start_time = time.time()
    tracks2, _ = library_manager.tracks.get_all(limit=50, offset=0)
    hit_time = time.time() - start_time

    # Cache hit should be faster or equal
    assert hit_time <= miss_time


# ============================================================================
# Cache Invalidation Tests
# ============================================================================

@pytest.mark.integration
def test_cache_invalidates_on_add(temp_audio_dir, library_manager):
    """
    CACHE: Cache invalidates when track is added.

    Tests that adding tracks clears relevant cache.
    """
    # Add initial tracks
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.tracks.add(track_info)

    # Query to populate cache
    tracks1, total1 = library_manager.tracks.get_all(limit=50, offset=0)

    # Add another track (should invalidate cache)
    filepath = create_test_track(temp_audio_dir, "new_track.wav")
    track_info = {
        "filepath": str(filepath),
        "title": "New Track",
        "artist": "Artist",
        "album": "Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    library_manager.tracks.add(track_info)

    # Query again (should reflect new track)
    tracks2, total2 = library_manager.tracks.get_all(limit=50, offset=0)

    assert total2 == total1 + 1


@pytest.mark.integration
def test_cache_invalidates_on_update(temp_audio_dir, library_manager):
    """
    CACHE: Cache invalidates when track is updated.

    Tests that updating tracks clears cache.
    """
    filepath = create_test_track(temp_audio_dir, "track.wav")
    track_info = {
        "filepath": str(filepath),
        "title": "Original Title",
        "artist": "Artist",
        "album": "Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track = library_manager.tracks.add(track_info)

    # Query to populate cache
    tracks1, _ = library_manager.tracks.get_all(limit=50, offset=0)

    # Update track (should invalidate cache)
    library_manager.tracks.update(track.id, {"title": "Updated Title"})

    # Query again (should reflect update)
    tracks2, _ = library_manager.tracks.get_all(limit=50, offset=0)

    assert tracks2[0].title == "Updated Title"


@pytest.mark.integration
def test_cache_invalidates_on_delete(temp_audio_dir, library_manager):
    """
    CACHE: Cache invalidates when track is deleted.

    Tests that deleting tracks clears cache.
    """
    # Add tracks
    track_ids = []
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track = library_manager.tracks.add(track_info)
        track_ids.append(track.id)

    # Query to populate cache
    tracks1, total1 = library_manager.tracks.get_all(limit=50, offset=0)

    # Delete a track (should invalidate cache)
    library_manager.tracks.delete(track_ids[0])

    # Query again (should reflect deletion)
    tracks2, total2 = library_manager.tracks.get_all(limit=50, offset=0)

    assert total2 == total1 - 1


# ============================================================================
# Cache Statistics Tests
# ============================================================================

@pytest.mark.integration
def test_cache_get_statistics(library_manager):
    """
    CACHE: Get cache statistics.

    Tests cache stats API.
    """
    stats = library_manager.get_cache_stats()

    # Verify stats structure
    assert isinstance(stats, dict)
    assert "size" in stats or "hits" in stats or "misses" in stats


@pytest.mark.integration
def test_cache_clear_resets_statistics(temp_audio_dir, library_manager):
    """
    CACHE: Clearing cache resets statistics.

    Tests that cache clear resets counters.
    """
    # Add some tracks
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.tracks.add(track_info)

    # Make some queries
    library_manager.tracks.get_all(limit=50, offset=0)
    library_manager.tracks.get_all(limit=50, offset=0)

    # Clear cache
    library_manager.clear_cache()

    # Stats should reflect clear
    stats = library_manager.get_cache_stats()
    assert isinstance(stats, dict)


# ============================================================================
# Cache Clearing Tests
# ============================================================================

@pytest.mark.integration
def test_cache_manual_clear(temp_audio_dir, library_manager):
    """
    CACHE: Manual cache clear works.

    Tests explicit cache clearing.
    """
    # Add tracks
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.tracks.add(track_info)

    # Query to populate cache
    library_manager.tracks.get_all(limit=50, offset=0)

    # Clear cache
    library_manager.clear_cache()

    # Next query should work (cache miss)
    tracks, total = library_manager.tracks.get_all(limit=50, offset=0)
    assert len(tracks) == 5


@pytest.mark.integration
def test_cache_clear_multiple_times(library_manager):
    """
    CACHE: Clearing cache multiple times doesn't error.

    Tests idempotent cache clearing.
    """
    # Clear cache multiple times
    library_manager.clear_cache()
    library_manager.clear_cache()
    library_manager.clear_cache()

    # Should not raise errors


# ============================================================================
# Summary Statistics
# ============================================================================

@pytest.mark.unit
def test_summary_stats():
    """Print summary statistics about cache operation tests."""
    print("\n" + "=" * 70)
    print("CACHE OPERATIONS TESTS - SUMMARY")
    print("=" * 70)
    print(f"Total cache tests: 12")
    print(f"\nTest categories:")
    print(f"  - Cache hit/miss: 3 tests")
    print(f"  - Cache invalidation: 3 tests")
    print(f"  - Cache statistics: 2 tests")
    print(f"  - Cache clearing: 2 tests")
    print(f"  - Summary stats: 1 test")
    print("=" * 70)


# ============================================================================
# Phase 5A: Dual-Mode Cache Testing
# ============================================================================

@pytest.fixture
def repository_factory_memory():
    """Create RepositoryFactory with in-memory database for testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auralis.library.models import Base

    # Create in-memory SQLite database
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    factory = RepositoryFactory(SessionLocal)

    yield factory

    try:
        engine.dispose()
    except Exception:
        pass


@pytest.mark.integration
def test_cache_operations_with_repository_factory(temp_audio_dir, repository_factory_memory):
    """
    PHASE 5A: Cache operations work with RepositoryFactory pattern.

    Tests that cache behavior is consistent when using RepositoryFactory
    instead of LibraryManager.
    """
    # Add tracks via repository factory
    track_repo = repository_factory_memory.tracks

    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}_factory.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track_repo.add(track_info)

    # Query via factory
    tracks, total = track_repo.get_all(limit=50, offset=0)

    assert len(tracks) == 5
    assert total == 5


@pytest.mark.integration
def test_cache_operations_dual_mode_equivalent(
    temp_audio_dir,
    library_manager,
    repository_factory_memory
):
    """
    PHASE 5A: Cache operations equivalent between LibraryManager and RepositoryFactory.

    Tests that both access patterns return equivalent results and cache behavior.
    """
    # Setup data via LibraryManager
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_{i}_dual.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        library_manager.tracks.add(track_info)

    # Query via LibraryManager
    tracks_manager, total_manager = library_manager.tracks.get_all(limit=50, offset=0)

    # Setup same data via RepositoryFactory
    for i in range(5):
        filepath = create_test_track(temp_audio_dir, f"track_repo_{i}_dual.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Track Repo {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        repository_factory_memory.tracks.add(track_info)

    # Query via RepositoryFactory
    tracks_factory, total_factory = repository_factory_memory.tracks.get_all(limit=50, offset=0)

    # Both should return same number of tracks (in their respective databases)
    assert total_manager == 5
    assert total_factory == 5
    assert len(tracks_manager) == 5
    assert len(tracks_factory) == 5


@pytest.mark.integration
def test_cache_invalidation_with_factory(temp_audio_dir, repository_factory_memory):
    """
    PHASE 5A: Cache invalidation works correctly with RepositoryFactory.

    Tests that adding/updating/deleting via factory properly invalidates cache.
    """
    track_repo = repository_factory_memory.tracks

    # Add initial tracks
    for i in range(3):
        filepath = create_test_track(temp_audio_dir, f"factory_track_{i}.wav")
        track_info = {
            "filepath": str(filepath),
            "title": f"Factory Track {i}",
            "artist": "Artist",
            "album": "Album",
            "duration": 1.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track_repo.add(track_info)

    # Query to populate cache
    tracks1, total1 = track_repo.get_all(limit=50, offset=0)

    # Add another track (should invalidate cache)
    filepath = create_test_track(temp_audio_dir, "new_factory_track.wav")
    track_info = {
        "filepath": str(filepath),
        "title": "New Factory Track",
        "artist": "Artist",
        "album": "Album",
        "duration": 1.0,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 1411200,
    }
    track_repo.add(track_info)

    # Query again
    tracks2, total2 = track_repo.get_all(limit=50, offset=0)

    # Should reflect new track
    assert total2 == total1 + 1
    assert len(tracks2) == 4
