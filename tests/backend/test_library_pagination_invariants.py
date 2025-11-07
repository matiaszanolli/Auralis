#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Library Pagination Invariant Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Critical invariant tests for library pagination that validate completeness,
correctness, and consistency of paginated queries.

:copyright: (C) 2024 Auralis Team
:license: GPLv3

CONTEXT: Pagination bugs can cause:
- Missing items (gaps in results)
- Duplicate items (same item appears in multiple pages)
- Incorrect counts (total != actual number of items)
- Order inconsistencies (items appear in different order on refresh)

These tests validate properties that MUST always hold for pagination to be correct.

Test Philosophy:
- Test invariants (properties that must always hold)
- Test behavior, not implementation
- Focus on defect detection
- Integration tests > unit tests for configuration bugs

See docs/development/TESTING_GUIDELINES.md for complete testing philosophy.
"""

import pytest
import tempfile
from pathlib import Path
from typing import List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the modules under test
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from auralis.library.models import Base, Track, Artist, Album
from auralis.library.repositories import TrackRepository, AlbumRepository, ArtistRepository


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session


@pytest.fixture
def track_repo(test_db):
    """Create TrackRepository instance."""
    return TrackRepository(test_db)


@pytest.fixture
def album_repo(test_db):
    """Create AlbumRepository instance."""
    return AlbumRepository(test_db)


@pytest.fixture
def artist_repo(test_db):
    """Create ArtistRepository instance."""
    return ArtistRepository(test_db)


@pytest.fixture
def populated_db(track_repo):
    """Create a database populated with 100 test tracks."""
    import tempfile
    from auralis.io.saver import save as save_audio
    import numpy as np

    # Create temporary directory for test audio files
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Create 100 test tracks
        for i in range(100):
            # Create minimal audio file
            audio = np.random.randn(44100, 2)  # 1 second stereo
            filepath = temp_dir / f"track_{i:03d}.wav"
            save_audio(str(filepath), audio, 44100, subtype='PCM_16')

            # Add to database
            track_info = {
                'filepath': str(filepath),
                'title': f'Track {i:03d}',
                'artists': [f'Artist {i % 10}'],  # 10 artists total
                'album': f'Album {i % 20}',  # 20 albums total
                'duration': 1.0,
                'sample_rate': 44100,
                'channels': 2,
                'format': 'WAV',
                'track_number': (i % 20) + 1,
                'year': 2020 + (i % 5),
            }
            track_repo.add(track_info)

        yield track_repo

    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# Core Pagination Invariant Tests (P0 Priority)
# ============================================================================

@pytest.mark.integration
def test_pagination_returns_all_items_exactly_once(populated_db):
    """
    CRITICAL INVARIANT: Paginating through all items returns each item exactly once.

    This is the fundamental invariant of pagination:
    - No items missing (completeness)
    - No items duplicated (uniqueness)

    This test would catch:
    - Off-by-one errors in offset calculation
    - Incorrect limit handling
    - Race conditions in ordering
    """
    track_repo = populated_db

    # Get total count
    _, total = track_repo.get_all(limit=1, offset=0)

    # Paginate through all tracks
    all_track_ids = set()
    page_size = 10
    offset = 0

    while offset < total:
        tracks, _ = track_repo.get_all(limit=page_size, offset=offset)

        # Check for duplicates
        track_ids_this_page = {t.id for t in tracks}
        duplicates = all_track_ids & track_ids_this_page

        assert not duplicates, (
            f"Duplicate items found in pagination at offset {offset}: {duplicates}. "
            f"Items should appear exactly once across all pages."
        )

        all_track_ids.update(track_ids_this_page)
        offset += page_size

    # Verify we got all items
    assert len(all_track_ids) == total, (
        f"Pagination returned {len(all_track_ids)} unique items, "
        f"but total count is {total}. Missing items: {total - len(all_track_ids)}"
    )


@pytest.mark.integration
def test_pagination_total_count_matches_actual_items(populated_db):
    """
    INVARIANT: Total count returned by pagination must match actual number of items.

    COUNT(*) must equal the number of items you can actually retrieve.
    """
    track_repo = populated_db

    # Get total count from first page
    _, total_count = track_repo.get_all(limit=10, offset=0)

    # Retrieve ALL items in one query (no pagination)
    all_tracks, _ = track_repo.get_all(limit=10000, offset=0)

    assert len(all_tracks) == total_count, (
        f"Total count mismatch: returned {total_count}, "
        f"but actually retrieved {len(all_tracks)} items"
    )


@pytest.mark.integration
def test_pagination_empty_result_when_offset_exceeds_total(populated_db):
    """
    INVARIANT: Offset beyond total count returns empty result, not error.

    Requesting page 100 when there are only 10 items should return empty list,
    not crash or return incorrect data.
    """
    track_repo = populated_db

    # Get total count
    _, total = track_repo.get_all(limit=1, offset=0)

    # Request page far beyond total
    tracks, returned_total = track_repo.get_all(limit=10, offset=total + 1000)

    assert len(tracks) == 0, (
        f"Offset beyond total should return empty result, got {len(tracks)} items"
    )
    assert returned_total == total, (
        f"Total count should remain {total} even with large offset, got {returned_total}"
    )


@pytest.mark.integration
def test_pagination_limit_zero_returns_empty(populated_db):
    """
    INVARIANT: limit=0 should return empty result with correct total count.
    """
    track_repo = populated_db

    tracks, total = track_repo.get_all(limit=0, offset=0)

    assert len(tracks) == 0, f"limit=0 should return empty list, got {len(tracks)} items"
    assert total > 0, f"Total count should still be reported, got {total}"


@pytest.mark.integration
def test_pagination_offset_zero_returns_first_page(populated_db):
    """
    INVARIANT: offset=0 must return the first page (items 1-N).
    """
    track_repo = populated_db

    # Get first page with offset=0
    page1, _ = track_repo.get_all(limit=10, offset=0, order_by='id')

    # Get all items ordered by ID
    all_tracks, _ = track_repo.get_all(limit=100, offset=0, order_by='id')

    # First page should match first 10 items from all_tracks
    assert len(page1) == min(10, len(all_tracks)), "First page should have correct size"

    for i, track in enumerate(page1):
        assert track.id == all_tracks[i].id, (
            f"Item {i} mismatch: page1 has ID {track.id}, all_tracks has ID {all_tracks[i].id}"
        )


# ============================================================================
# Ordering Invariant Tests (P0 Priority)
# ============================================================================

@pytest.mark.integration
def test_pagination_preserves_order_across_pages(populated_db):
    """
    INVARIANT: Items must appear in consistent order across pagination.

    If ordering by title, the concatenation of all pages must be sorted by title.
    """
    track_repo = populated_db

    # Paginate through all tracks ordered by title
    page_size = 10
    offset = 0
    _, total = track_repo.get_all(limit=1, offset=0)

    all_titles = []

    while offset < total:
        tracks, _ = track_repo.get_all(limit=page_size, offset=offset, order_by='title')
        all_titles.extend([t.title for t in tracks])
        offset += page_size

    # Verify titles are in sorted order
    sorted_titles = sorted(all_titles)

    assert all_titles == sorted_titles, (
        f"Pagination order inconsistent: items not sorted by title across pages. "
        f"First mismatch at index {next(i for i, (a, b) in enumerate(zip(all_titles, sorted_titles)) if a != b)}"
    )


@pytest.mark.integration
def test_pagination_different_orderings_return_same_items(populated_db):
    """
    INVARIANT: Changing sort order should return same items (different order).

    Sorting by title vs. ID should return same set of items, just ordered differently.
    """
    track_repo = populated_db

    # Get all tracks ordered by title
    tracks_by_title, total1 = track_repo.get_all(limit=1000, offset=0, order_by='title')
    ids_by_title = {t.id for t in tracks_by_title}

    # Get all tracks ordered by ID
    tracks_by_id, total2 = track_repo.get_all(limit=1000, offset=0, order_by='id')
    ids_by_id = {t.id for t in tracks_by_id}

    # Should have same total count
    assert total1 == total2, f"Total count differs: {total1} vs {total2}"

    # Should have same items
    assert ids_by_title == ids_by_id, (
        f"Different sort orders returned different items. "
        f"Missing in title sort: {ids_by_id - ids_by_title}, "
        f"Extra in title sort: {ids_by_title - ids_by_id}"
    )


# ============================================================================
# Boundary Tests (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_pagination_last_page_partial_results(populated_db):
    """
    INVARIANT: Last page can have fewer items than page_size (partial page).
    """
    track_repo = populated_db

    _, total = track_repo.get_all(limit=1, offset=0)

    # Request a page size that doesn't divide evenly into total
    page_size = 7
    last_page_offset = (total // page_size) * page_size

    last_page, _ = track_repo.get_all(limit=page_size, offset=last_page_offset)

    expected_last_page_size = total % page_size
    if expected_last_page_size == 0:
        expected_last_page_size = page_size  # Exact division

    assert len(last_page) == expected_last_page_size, (
        f"Last page should have {expected_last_page_size} items, got {len(last_page)}"
    )


@pytest.mark.integration
def test_pagination_single_item_pages(populated_db):
    """
    INVARIANT: limit=1 should work correctly (one item per page).
    """
    track_repo = populated_db

    _, total = track_repo.get_all(limit=1, offset=0)

    # Get first 10 items with limit=1
    all_ids = []
    for offset in range(min(10, total)):
        tracks, _ = track_repo.get_all(limit=1, offset=offset)
        assert len(tracks) == 1, f"limit=1 should return 1 item at offset {offset}"
        all_ids.append(tracks[0].id)

    # Should be 10 unique items
    assert len(all_ids) == len(set(all_ids)), "Each single-item page should be unique"


@pytest.mark.integration
def test_pagination_large_limit_returns_all_items(populated_db):
    """
    INVARIANT: limit > total should return all items (no truncation).
    """
    track_repo = populated_db

    _, total = track_repo.get_all(limit=1, offset=0)

    # Request with limit far exceeding total
    tracks, returned_total = track_repo.get_all(limit=10000, offset=0)

    assert len(tracks) == total, (
        f"Large limit should return all {total} items, got {len(tracks)}"
    )
    assert returned_total == total


# ============================================================================
# Album Pagination Invariants (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_album_pagination_completeness(album_repo):
    """
    INVARIANT: Album pagination must return all albums exactly once.

    Same invariant as tracks, but for albums.
    """
    # Get total count
    _, total = album_repo.get_all(limit=1, offset=0)

    if total == 0:
        pytest.skip("No albums in test database")

    # Paginate through all albums
    all_album_ids = set()
    page_size = 5
    offset = 0

    while offset < total:
        albums, _ = album_repo.get_all(limit=page_size, offset=offset)

        album_ids_this_page = {a.id for a in albums}
        duplicates = all_album_ids & album_ids_this_page

        assert not duplicates, f"Duplicate albums at offset {offset}: {duplicates}"

        all_album_ids.update(album_ids_this_page)
        offset += page_size

    assert len(all_album_ids) == total, (
        f"Album pagination returned {len(all_album_ids)} unique albums, expected {total}"
    )


@pytest.mark.integration
def test_album_pagination_ordering(album_repo):
    """
    INVARIANT: Albums must be ordered consistently across pages.
    """
    _, total = album_repo.get_all(limit=1, offset=0)

    if total == 0:
        pytest.skip("No albums in test database")

    # Paginate through all albums ordered by title
    page_size = 5
    offset = 0
    all_titles = []

    while offset < total:
        albums, _ = album_repo.get_all(limit=page_size, offset=offset, order_by='title')
        all_titles.extend([a.title for a in albums])
        offset += page_size

    # Verify ordering
    sorted_titles = sorted(all_titles)
    assert all_titles == sorted_titles, "Album pagination order inconsistent"


# ============================================================================
# Artist Pagination Invariants (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_artist_pagination_completeness(artist_repo):
    """
    INVARIANT: Artist pagination must return all artists exactly once.
    """
    # Get total count
    _, total = artist_repo.get_all(limit=1, offset=0)

    if total == 0:
        pytest.skip("No artists in test database")

    # Paginate through all artists
    all_artist_ids = set()
    page_size = 5
    offset = 0

    while offset < total:
        artists, _ = artist_repo.get_all(limit=page_size, offset=offset)

        artist_ids_this_page = {a.id for a in artists}
        duplicates = all_artist_ids & artist_ids_this_page

        assert not duplicates, f"Duplicate artists at offset {offset}: {duplicates}"

        all_artist_ids.update(artist_ids_this_page)
        offset += page_size

    assert len(all_artist_ids) == total, (
        f"Artist pagination returned {len(all_artist_ids)} unique artists, expected {total}"
    )


# ============================================================================
# Search Pagination Invariants (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_search_pagination_completeness(populated_db):
    """
    INVARIANT: Search with pagination must return matching items exactly once.
    """
    track_repo = populated_db

    # Search for tracks containing "Track 0" (should match Track 000-009, 010-019, etc.)
    query = "Track 0"

    # First get all results in one query to know expected count
    all_results, total = track_repo.search(query, limit=1000, offset=0)

    if total == 0:
        pytest.skip("No search results to test")

    # Now paginate through results
    all_ids = set()
    page_size = 5
    offset = 0

    while offset < total:
        results, _ = track_repo.search(query, limit=page_size, offset=offset)

        ids_this_page = {t.id for t in results}
        duplicates = all_ids & ids_this_page

        assert not duplicates, f"Duplicate search results at offset {offset}"

        all_ids.update(ids_this_page)
        offset += page_size

    assert len(all_ids) == total, (
        f"Search pagination returned {len(all_ids)} unique items, expected {total}"
    )


@pytest.mark.integration
def test_search_pagination_returns_relevant_items_only(populated_db):
    """
    INVARIANT: Search pagination should only return items matching the query.
    """
    track_repo = populated_db

    query = "Track 01"  # Should match "Track 010", "Track 011", ..., "Track 019"

    # Paginate through search results
    page_size = 5
    offset = 0
    _, total = track_repo.search(query, limit=1, offset=0)

    while offset < total:
        results, _ = track_repo.search(query, limit=page_size, offset=offset)

        for track in results:
            assert query in track.title, (
                f"Non-matching item in search results: '{track.title}' doesn't contain '{query}'"
            )

        offset += page_size


# ============================================================================
# Filtered List Invariants (P1 Priority)
# ============================================================================

@pytest.mark.integration
def test_favorites_pagination_completeness(populated_db):
    """
    INVARIANT: Favorites pagination must return all favorites exactly once.
    """
    track_repo = populated_db

    # Mark every 5th track as favorite
    for i in range(0, 100, 5):
        tracks, _ = track_repo.get_all(limit=1, offset=i, order_by='id')
        if tracks:
            track_repo.set_favorite(tracks[0].id, True)

    # Get total favorites count
    _, total = track_repo.get_favorites(limit=1, offset=0)

    if total == 0:
        pytest.skip("No favorites to test")

    # Paginate through favorites
    all_fav_ids = set()
    page_size = 5
    offset = 0

    while offset < total:
        favorites, _ = track_repo.get_favorites(limit=page_size, offset=offset)

        fav_ids_this_page = {t.id for t in favorites}
        duplicates = all_fav_ids & fav_ids_this_page

        assert not duplicates, f"Duplicate favorites at offset {offset}"

        all_fav_ids.update(fav_ids_this_page)
        offset += page_size

    assert len(all_fav_ids) == total, (
        f"Favorites pagination returned {len(all_fav_ids)} unique items, expected {total}"
    )


@pytest.mark.integration
def test_recent_tracks_pagination_completeness(populated_db):
    """
    INVARIANT: Recent tracks pagination must return items exactly once.
    """
    track_repo = populated_db

    # Record some plays
    for i in range(min(20, 100)):
        tracks, _ = track_repo.get_all(limit=1, offset=i, order_by='id')
        if tracks:
            track_repo.record_play(tracks[0].id)

    # Get total recent count
    _, total = track_repo.get_recent(limit=1, offset=0)

    if total == 0:
        pytest.skip("No recent tracks to test")

    # Paginate through recent tracks
    all_recent_ids = set()
    page_size = 5
    offset = 0

    while offset < total:
        recent, _ = track_repo.get_recent(limit=page_size, offset=offset)

        recent_ids_this_page = {t.id for t in recent}
        duplicates = all_recent_ids & recent_ids_this_page

        assert not duplicates, f"Duplicate recent tracks at offset {offset}"

        all_recent_ids.update(recent_ids_this_page)
        offset += page_size

    assert len(all_recent_ids) == total, (
        f"Recent tracks pagination returned {len(all_recent_ids)} unique items, expected {total}"
    )


# ============================================================================
# Edge Cases (P2 Priority)
# ============================================================================

@pytest.mark.integration
def test_pagination_with_empty_database(test_db):
    """
    INVARIANT: Pagination on empty database should return empty result with total=0.
    """
    track_repo = TrackRepository(test_db)

    tracks, total = track_repo.get_all(limit=10, offset=0)

    assert len(tracks) == 0, "Empty database should return empty list"
    assert total == 0, "Empty database should report total=0"


@pytest.mark.integration
def test_pagination_with_single_item(test_db):
    """
    INVARIANT: Pagination with single item should work correctly.
    """
    import tempfile
    import numpy as np
    from auralis.io.saver import save as save_audio

    track_repo = TrackRepository(test_db)

    # Create single test track
    temp_dir = Path(tempfile.mkdtemp())
    try:
        audio = np.random.randn(44100, 2)
        filepath = temp_dir / "track.wav"
        save_audio(str(filepath), audio, 44100, subtype='PCM_16')

        track_info = {
            'filepath': str(filepath),
            'title': 'Single Track',
            'artists': ['Test Artist'],
        }
        track_repo.add(track_info)

        # Test pagination
        tracks, total = track_repo.get_all(limit=10, offset=0)

        assert len(tracks) == 1, "Should return 1 track"
        assert total == 1, "Total should be 1"
        assert tracks[0].title == 'Single Track'

        # Second page should be empty
        tracks_page2, total_page2 = track_repo.get_all(limit=10, offset=10)
        assert len(tracks_page2) == 0, "Second page should be empty"
        assert total_page2 == 1, "Total should still be 1"

    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.integration
def test_pagination_consistency_with_concurrent_modifications():
    """
    INVARIANT: Pagination should be consistent even if items are added during iteration.

    NOTE: This is a known limitation - adding items during pagination can cause
    duplicates or missing items. This test documents the expected behavior.

    In production, use cursor-based pagination or snapshot isolation for true consistency.
    """
    # This test is intentionally marked as expected to have issues
    # Just documenting the limitation of offset-based pagination
    pytest.skip("Known limitation: offset-based pagination not consistent with concurrent writes")


# ============================================================================
# Summary Statistics
# ============================================================================

def test_summary_stats():
    """
    Print summary of what these tests validate.
    """
    print("\n" + "=" * 80)
    print("LIBRARY PAGINATION INVARIANT TEST SUMMARY")
    print("=" * 80)
    print(f"Core Pagination Invariants: 5 tests")
    print(f"Ordering Invariants: 2 tests")
    print(f"Boundary Tests: 3 tests")
    print(f"Album Pagination: 2 tests")
    print(f"Artist Pagination: 1 test")
    print(f"Search Pagination: 2 tests")
    print(f"Filtered List Pagination: 2 tests")
    print(f"Edge Cases: 3 tests")
    print("=" * 80)
    print(f"TOTAL: 20 pagination invariant tests")
    print("=" * 80)
    print("\nThese tests validate the fundamental pagination invariants:")
    print("1. Completeness: All items returned exactly once")
    print("2. Consistency: Same items regardless of page size")
    print("3. Ordering: Items maintain sort order across pages")
    print("4. Boundary handling: Edge cases handled correctly")
    print("=" * 80 + "\n")
