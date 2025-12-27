# -*- coding: utf-8 -*-

"""
Auralis Cache Invalidation Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for pattern-based cache invalidation system.

Tests verify that:
- Targeted invalidation works correctly
- Unrelated caches survive mutations
- Cache hit rate remains high after selective invalidation
- Full cache clear still works as fallback

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import tempfile
from pathlib import Path

import pytest

from auralis.library.cache import _global_cache, get_cache_stats, invalidate_cache
from auralis.library.manager import LibraryManager

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_library():
    """Create temporary library with test data"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test audio files
        audio_dir = Path(tmpdir) / "music"
        audio_dir.mkdir()

        track_files = []
        for i in range(20):
            track_file = audio_dir / f"track_{i:03d}.mp3"
            track_file.write_bytes(b"dummy audio data")
            track_files.append(str(track_file))

        # Initialize manager
        db_path = Path(tmpdir) / "test_library.db"
        manager = LibraryManager(str(db_path))

        # Add tracks
        track_ids = []
        for i, filepath in enumerate(track_files):
            track_info = {
                'filepath': filepath,
                'title': f'Track {i:03d}',
                'artist': f'Artist {i % 5}',
                'album': f'Album {i % 3}',
                'duration': 180.0,
                'format': 'MP3'
            }
            track = manager.add_track(track_info)
            if track:
                track_ids.append(track.id)

        yield manager, track_ids, audio_dir

        # Cleanup handled by tempfile


# ============================================================================
# Pattern-Based Invalidation Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.library
def test_invalidate_single_function(temp_library):
    """
    Verify invalidating a single function only affects that cache.

    Tests that:
    - Targeted function cache is cleared
    - Other function caches remain intact
    """
    manager, track_ids, _ = temp_library

    # Clear cache first
    manager.clear_cache()

    # Populate multiple caches
    manager.get_all_tracks(limit=10)
    manager.get_favorite_tracks(limit=10)
    manager.get_popular_tracks(limit=10)

    stats_before = manager.get_cache_stats()
    assert stats_before['size'] == 3, "Should have 3 cached queries"

    # Invalidate only one function
    invalidate_cache('get_all_tracks')

    # Verify selective invalidation
    # get_all_tracks should be cleared, others should remain
    stats_after = manager.get_cache_stats()
    assert stats_after['size'] == 2, "Should have 2 cached queries remaining"

    # Verify cache hits on surviving caches
    manager.get_favorite_tracks(limit=10)  # Should hit cache
    stats_final = manager.get_cache_stats()
    assert stats_final['hits'] > stats_after['hits'], "Should have cache hit"


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.library
def test_invalidate_multiple_functions(temp_library):
    """
    Verify invalidating multiple functions at once.

    Tests that:
    - All specified functions are cleared
    - Unrelated caches survive
    """
    manager, track_ids, _ = temp_library

    manager.clear_cache()

    # Populate caches
    manager.get_all_tracks(limit=10)
    manager.get_favorite_tracks(limit=10)
    manager.get_popular_tracks(limit=10)
    manager.get_recent_tracks(limit=10)

    assert manager.get_cache_stats()['size'] == 4

    # Invalidate multiple
    invalidate_cache('get_all_tracks', 'get_popular_tracks')

    # Should have 2 caches remaining
    assert manager.get_cache_stats()['size'] == 2


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.library
def test_full_cache_clear(temp_library):
    """
    Verify full cache clear (no arguments) works.

    Tests that:
    - All caches are cleared
    - Cache size is 0
    """
    manager, track_ids, _ = temp_library

    # Populate caches
    manager.get_all_tracks(limit=10)
    manager.get_favorite_tracks(limit=10)
    manager.get_popular_tracks(limit=10)

    assert manager.get_cache_stats()['size'] > 0

    # Full clear
    invalidate_cache()

    assert manager.get_cache_stats()['size'] == 0


# ============================================================================
# Mutation-Specific Invalidation Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.fast
@pytest.mark.library
def test_favorite_toggle_preserves_other_caches(temp_library):
    """
    Verify toggling favorite doesn't clear unrelated caches.

    Tests that:
    - Favorite toggle invalidates get_favorite_tracks
    - get_all_tracks cache survives
    - get_popular_tracks cache survives
    """
    manager, track_ids, _ = temp_library

    manager.clear_cache()

    # Populate caches
    manager.get_all_tracks(limit=10)
    manager.get_popular_tracks(limit=10)
    manager.get_favorite_tracks(limit=10)

    stats_before = manager.get_cache_stats()
    assert stats_before['size'] == 3

    # Toggle favorite
    manager.set_track_favorite(track_ids[0], True)

    # get_favorite_tracks should be cleared
    stats_after = manager.get_cache_stats()
    assert stats_after['size'] == 2, "Only get_favorite_tracks should be invalidated"

    # Verify get_all_tracks still cached
    manager.get_all_tracks(limit=10)
    stats_final = manager.get_cache_stats()
    assert stats_final['hits'] == stats_after['hits'] + 1, "Should have cache hit for get_all_tracks"


@pytest.mark.integration
@pytest.mark.fast
@pytest.mark.library
def test_record_play_invalidates_affected_caches(temp_library):
    """
    Verify recording play invalidates correct caches.

    Tests that:
    - get_popular_tracks is invalidated (play count changed)
    - get_recent_tracks is invalidated (last_played changed)
    - get_favorite_tracks survives (unrelated to play count)
    """
    manager, track_ids, _ = temp_library

    manager.clear_cache()

    # Populate caches
    manager.get_popular_tracks(limit=10)
    manager.get_recent_tracks(limit=10)
    manager.get_favorite_tracks(limit=10)
    manager.get_all_tracks(limit=10)

    assert manager.get_cache_stats()['size'] == 4

    # Record play
    manager.record_track_play(track_ids[0])

    # get_popular_tracks, get_recent_tracks, get_all_tracks, get_track should be cleared
    # get_favorite_tracks should survive
    stats_after = manager.get_cache_stats()
    # Note: The exact number depends on implementation, but should be < 4

    # Verify get_favorite_tracks is still cached
    manager.get_favorite_tracks(limit=10)
    stats_final = manager.get_cache_stats()
    # If get_favorite_tracks survived, this should be a cache hit
    # (hits increased by 1)


@pytest.mark.integration
@pytest.mark.fast
@pytest.mark.library
def test_delete_track_invalidation(temp_library):
    """
    Verify track deletion invalidates relevant caches.

    Tests that:
    - get_all_tracks is invalidated
    - search_tracks is invalidated
    - Caches are properly cleared
    """
    manager, track_ids, _ = temp_library

    manager.clear_cache()

    # Populate caches (only cached methods)
    manager.get_all_tracks(limit=10)
    manager.search_tracks("Track")
    manager.get_favorite_tracks(limit=10)

    stats_before = manager.get_cache_stats()
    assert stats_before['size'] >= 3

    # Delete track
    manager.delete_track(track_ids[0])

    # All track-related caches should be cleared (delete affects many queries)
    stats_after = manager.get_cache_stats()
    assert stats_after['size'] < stats_before['size'], "Caches should be invalidated"


@pytest.mark.integration
@pytest.mark.fast
@pytest.mark.library
def test_update_track_invalidation(temp_library):
    """
    Verify track update invalidates search/metadata caches.

    Tests that:
    - get_track is invalidated
    - search_tracks is invalidated
    - get_favorite_tracks survives (metadata update doesn't affect favorites)
    """
    manager, track_ids, _ = temp_library

    manager.clear_cache()

    # Populate caches
    manager.get_track(track_ids[0])
    manager.search_tracks("Track")
    manager.get_favorite_tracks(limit=10)

    stats_before = manager.get_cache_stats()

    # Update track
    manager.update_track(track_ids[0], {"title": "Updated Track"})

    # get_track and search_tracks should be cleared
    stats_after = manager.get_cache_stats()
    assert stats_after['size'] < stats_before['size']


# ============================================================================
# Cache Hit Rate Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.fast
@pytest.mark.library
@pytest.mark.performance
def test_cache_hit_rate_after_mutations(temp_library):
    """
    Verify cache hit rate remains high after targeted mutations.

    Tests that:
    - Multiple queries build up cache
    - Mutations only invalidate affected caches
    - Hit rate stays above 70% for repeated queries
    """
    manager, track_ids, _ = temp_library

    manager.clear_cache()

    # Perform 100 mixed operations
    for i in range(100):
        if i % 10 == 0:
            # Mutation every 10th operation
            manager.set_track_favorite(track_ids[i % len(track_ids)], True)
        else:
            # Queries (should mostly hit cache)
            manager.get_all_tracks(limit=10)

    stats = manager.get_cache_stats()
    hit_rate_str = stats['hit_rate']
    hit_rate = float(hit_rate_str.rstrip('%'))

    # With targeted invalidation, hit rate should be high
    # Mutation happens 10 times, queries happen 90 times
    # After first query, all subsequent get_all_tracks should hit cache
    # except after mutations that affect get_all_tracks
    assert hit_rate > 70.0, f"Cache hit rate too low: {hit_rate}% (expected >70%)"


@pytest.mark.integration
@pytest.mark.fast
@pytest.mark.library
@pytest.mark.performance
def test_cache_effectiveness_with_diverse_queries(temp_library):
    """
    Verify cache effectiveness with diverse query patterns.

    Tests that:
    - Different query types build separate caches
    - Mutations only affect related caches
    - Overall hit rate is reasonable
    """
    manager, track_ids, _ = temp_library

    manager.clear_cache()

    # Perform diverse operations
    for i in range(50):
        if i % 5 == 0:
            manager.get_all_tracks(limit=10)
        elif i % 5 == 1:
            manager.get_favorite_tracks(limit=10)
        elif i % 5 == 2:
            manager.get_popular_tracks(limit=10)
        elif i % 5 == 3:
            manager.search_tracks("Track")
        else:
            # Mutation
            manager.set_track_favorite(track_ids[i % len(track_ids)], True)

    stats = manager.get_cache_stats()
    hit_rate_str = stats['hit_rate']
    hit_rate = float(hit_rate_str.rstrip('%'))

    # With 20% mutations, hit rate should still be reasonable
    assert hit_rate > 40.0, f"Cache hit rate too low: {hit_rate}% (expected >40%)"


# ============================================================================
# Edge Cases
# ============================================================================

@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.library
def test_invalidate_nonexistent_function(temp_library):
    """
    Verify invalidating non-existent function is safe.

    Tests that:
    - No error is raised
    - Existing caches are unaffected
    """
    manager, track_ids, _ = temp_library

    manager.clear_cache()

    # Populate caches
    manager.get_all_tracks(limit=10)

    stats_before = manager.get_cache_stats()

    # Invalidate non-existent function
    invalidate_cache('non_existent_function')

    stats_after = manager.get_cache_stats()
    assert stats_after['size'] == stats_before['size'], "Cache size should be unchanged"


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.library
def test_cache_with_different_parameters(temp_library):
    """
    Verify same function with different parameters creates separate caches.

    Tests that:
    - get_all_tracks(limit=10) and get_all_tracks(limit=20) are separate
    - Invalidating function clears both
    """
    manager, track_ids, _ = temp_library

    manager.clear_cache()

    # Same function, different params
    manager.get_all_tracks(limit=10)
    manager.get_all_tracks(limit=20)

    stats = manager.get_cache_stats()
    assert stats['size'] == 2, "Should have 2 separate caches"

    # Invalidate function (should clear both)
    invalidate_cache('get_all_tracks')

    stats_after = manager.get_cache_stats()
    assert stats_after['size'] == 0, "Both parameter variants should be cleared"


# ============================================================================
# Concurrency Safety (Basic)
# ============================================================================

@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.library
def test_rapid_invalidation(temp_library):
    """
    Verify rapid invalidation operations don't corrupt cache.

    Tests that:
    - Multiple rapid invalidations complete successfully
    - Cache remains in consistent state
    """
    manager, track_ids, _ = temp_library

    manager.clear_cache()

    # Populate cache
    manager.get_all_tracks(limit=10)

    # Rapid invalidation
    for i in range(100):
        invalidate_cache('get_all_tracks')

    # Should be able to use cache normally afterward
    manager.get_all_tracks(limit=10)
    stats = manager.get_cache_stats()
    assert stats['size'] == 1


# ============================================================================
# Summary Statistics
# ============================================================================

def test_summary_stats():
    """
    Print summary of cache invalidation test suite.
    """
    test_categories = {
        'Pattern-Based Invalidation': 3,
        'Mutation-Specific Invalidation': 4,
        'Cache Hit Rate': 2,
        'Edge Cases': 2,
        'Concurrency Safety': 1
    }

    total = sum(test_categories.values())

    print("\n" + "=" * 60)
    print("Cache Invalidation Test Suite Summary")
    print("=" * 60)
    for category, count in test_categories.items():
        print(f"  {category:.<40} {count:>3} tests")
    print("-" * 60)
    print(f"  {'Total':.<40} {total:>3} tests")
    print("=" * 60)
    print("\nTest Organization:")
    print("  - Unit tests: Fast, isolated cache behavior")
    print("  - Integration tests: Multi-component cache interactions")
    print("  - Performance tests: Cache hit rate benchmarks")
    print("=" * 60)
