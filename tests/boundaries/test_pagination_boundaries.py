"""
Pagination Boundary Tests
~~~~~~~~~~~~~~~~~~~~~~~~

Tests edge cases and boundary conditions for pagination in library operations.

These tests verify critical invariants:
1. All items returned exactly once (no duplicates, no gaps)
2. Offset + limit never exceeds total count
3. Empty results when offset >= total
4. Correct total count regardless of pagination
5. Order consistency across pages

Test Categories:
- Empty collection (6 tests)
- Single item (6 tests)
- Exact page boundaries (6 tests)
- Large offsets (6 tests)
- Invalid parameters (6 tests)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import os
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add auralis to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'auralis'))

from auralis.library.models import Base, Track, Artist, Album
from auralis.library.repositories import TrackRepository, AlbumRepository, ArtistRepository


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(engine)
        SessionFactory = sessionmaker(bind=engine)
        yield SessionFactory
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
def track_repo(temp_db):
    """Create track repository"""
    return TrackRepository(temp_db)


@pytest.fixture
def album_repo(temp_db):
    """Create album repository"""
    return AlbumRepository(temp_db)


@pytest.fixture
def artist_repo(temp_db):
    """Create artist repository"""
    return ArtistRepository(temp_db)


def add_test_tracks(repo, count: int) -> list:
    """
    Helper to add test tracks to repository.

    Args:
        repo: TrackRepository instance
        count: Number of tracks to add

    Returns:
        List of created track IDs
    """
    track_ids = []
    for i in range(count):
        track_info = {
            'filepath': f'/tmp/test_track_{i:03d}.flac',
            'title': f'Test Track {i:03d}',
            'artists': [f'Artist {i % 10}'],  # 10 different artists
            'album': f'Album {i % 5}',  # 5 different albums
            'duration': 180.0 + (i * 10),  # Varying durations
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        }
        track = repo.add(track_info)
        if track:
            track_ids.append(track.id)
    return track_ids


# ============================================================================
# CATEGORY 1: EMPTY COLLECTION (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_empty_collection_first_page(track_repo):
    """
    BOUNDARY: Pagination on empty collection (offset=0).
    Should return empty list with total=0.
    """
    tracks, total = track_repo.get_all(limit=50, offset=0)

    assert tracks == [], "Empty collection should return empty list"
    assert total == 0, "Empty collection should have total count of 0"


@pytest.mark.boundary
def test_empty_collection_nonzero_offset(track_repo):
    """
    BOUNDARY: Pagination on empty collection (offset>0).
    Should return empty list with total=0.
    """
    tracks, total = track_repo.get_all(limit=50, offset=100)

    assert tracks == [], "Empty collection should return empty list regardless of offset"
    assert total == 0, "Empty collection should have total count of 0"


@pytest.mark.boundary
def test_empty_collection_zero_limit(track_repo):
    """
    BOUNDARY: Pagination with limit=0 on empty collection.
    Should return empty list with total=0.
    """
    tracks, total = track_repo.get_all(limit=0, offset=0)

    assert tracks == [], "Limit=0 should return empty list"
    assert total == 0, "Empty collection should have total count of 0"


@pytest.mark.boundary
def test_empty_collection_large_limit(track_repo):
    """
    BOUNDARY: Pagination with very large limit on empty collection.
    Should return empty list with total=0.
    """
    tracks, total = track_repo.get_all(limit=1_000_000, offset=0)

    assert tracks == [], "Empty collection should return empty list regardless of limit"
    assert total == 0, "Empty collection should have total count of 0"


@pytest.mark.boundary
def test_empty_albums(album_repo):
    """
    BOUNDARY: Album pagination on empty collection.
    Should return empty list with total=0.
    """
    albums, total = album_repo.get_all(limit=50, offset=0)

    assert albums == [], "Empty album collection should return empty list"
    assert total == 0, "Empty album collection should have total count of 0"


@pytest.mark.boundary
def test_empty_artists(artist_repo):
    """
    BOUNDARY: Artist pagination on empty collection.
    Should return empty list with total=0.
    """
    artists, total = artist_repo.get_all(limit=50, offset=0)

    assert artists == [], "Empty artist collection should return empty list"
    assert total == 0, "Empty artist collection should have total count of 0"


# ============================================================================
# CATEGORY 2: SINGLE ITEM (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_single_item_first_page(track_repo):
    """
    BOUNDARY: Pagination with exactly 1 item (offset=0).
    Should return 1 item with total=1.
    """
    add_test_tracks(track_repo, 1)

    tracks, total = track_repo.get_all(limit=50, offset=0)

    assert len(tracks) == 1, "Should return exactly 1 track"
    assert total == 1, "Total should be 1"
    assert tracks[0].title == 'Test Track 000'


@pytest.mark.boundary
def test_single_item_offset_one(track_repo):
    """
    BOUNDARY: Pagination with 1 item but offset=1.
    Should return empty list (beyond collection) but total=1.
    """
    add_test_tracks(track_repo, 1)

    tracks, total = track_repo.get_all(limit=50, offset=1)

    assert tracks == [], "Offset beyond collection should return empty list"
    assert total == 1, "Total should still be 1"


@pytest.mark.boundary
def test_single_item_limit_one(track_repo):
    """
    BOUNDARY: Pagination with 1 item and limit=1.
    Should return exactly 1 item.
    """
    add_test_tracks(track_repo, 1)

    tracks, total = track_repo.get_all(limit=1, offset=0)

    assert len(tracks) == 1, "Should return exactly 1 track with limit=1"
    assert total == 1, "Total should be 1"


@pytest.mark.boundary
def test_single_item_zero_limit(track_repo):
    """
    BOUNDARY: Pagination with 1 item but limit=0.
    Should return empty list but total=1.
    """
    add_test_tracks(track_repo, 1)

    tracks, total = track_repo.get_all(limit=0, offset=0)

    assert tracks == [], "Limit=0 should return empty list"
    assert total == 1, "Total should still be 1"


@pytest.mark.boundary
def test_single_album(album_repo, temp_db):
    """
    BOUNDARY: Album pagination with exactly 1 album.
    Should return 1 album with total=1.
    """
    # Create artist and album directly
    session = temp_db()
    artist = Artist(name='Test Artist')
    session.add(artist)
    session.commit()

    album = Album(title='Test Album', artist_id=artist.id, year=2024)
    session.add(album)
    session.commit()
    session.close()

    albums, total = album_repo.get_all(limit=50, offset=0)

    assert len(albums) == 1, "Should return exactly 1 album"
    assert total == 1, "Total should be 1"


@pytest.mark.boundary
def test_single_artist(artist_repo, temp_db):
    """
    BOUNDARY: Artist pagination with exactly 1 artist.
    Should return 1 artist with total=1.
    """
    session = temp_db()
    artist = Artist(name='Test Artist')
    session.add(artist)
    session.commit()
    session.close()

    artists, total = artist_repo.get_all(limit=50, offset=0)

    assert len(artists) == 1, "Should return exactly 1 artist"
    assert total == 1, "Total should be 1"


# ============================================================================
# CATEGORY 3: EXACT PAGE BOUNDARIES (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_exact_page_boundary_50(track_repo):
    """
    BOUNDARY: Collection size = limit exactly (50 items, limit=50).
    Should return all 50 items on first page.
    """
    add_test_tracks(track_repo, 50)

    tracks, total = track_repo.get_all(limit=50, offset=0)

    assert len(tracks) == 50, "Should return all 50 tracks"
    assert total == 50, "Total should be 50"


@pytest.mark.boundary
def test_exact_page_boundary_second_page_empty(track_repo):
    """
    BOUNDARY: Second page of exactly-sized collection (50 items, offset=50).
    Should return empty list.
    """
    add_test_tracks(track_repo, 50)

    tracks, total = track_repo.get_all(limit=50, offset=50)

    assert tracks == [], "Second page should be empty when collection = page size"
    assert total == 50, "Total should still be 50"


@pytest.mark.boundary
def test_exact_multiple_pages(track_repo):
    """
    BOUNDARY: Collection = exact multiple of limit (100 items, limit=50).
    Should have exactly 2 full pages.
    """
    add_test_tracks(track_repo, 100)

    # First page
    page1, total = track_repo.get_all(limit=50, offset=0)
    assert len(page1) == 50, "First page should have 50 items"

    # Second page
    page2, total = track_repo.get_all(limit=50, offset=50)
    assert len(page2) == 50, "Second page should have 50 items"

    # Third page (should be empty)
    page3, total = track_repo.get_all(limit=50, offset=100)
    assert page3 == [], "Third page should be empty"

    assert total == 100, "Total should be 100"


@pytest.mark.boundary
def test_partial_last_page(track_repo):
    """
    BOUNDARY: Last page has fewer items than limit (75 items, limit=50).
    Last page should have 25 items.
    """
    add_test_tracks(track_repo, 75)

    # Second page (last)
    tracks, total = track_repo.get_all(limit=50, offset=50)

    assert len(tracks) == 25, "Last page should have remaining 25 items"
    assert total == 75, "Total should be 75"


@pytest.mark.boundary
def test_no_duplicates_across_pages(track_repo):
    """
    INVARIANT: Pagination should return all items exactly once (no duplicates).
    Test with 150 items, 50 per page.
    """
    add_test_tracks(track_repo, 150)

    all_ids = set()
    for page_num in range(3):
        offset = page_num * 50
        tracks, total = track_repo.get_all(limit=50, offset=offset)

        # Extract IDs
        page_ids = {t.id for t in tracks}

        # Check for duplicates
        duplicates = all_ids & page_ids
        assert not duplicates, f"Found duplicates on page {page_num}: {duplicates}"

        all_ids.update(page_ids)

    assert len(all_ids) == 150, "Should have exactly 150 unique tracks across all pages"


@pytest.mark.boundary
def test_consistent_total_across_pages(track_repo):
    """
    INVARIANT: Total count should be consistent across all page requests.
    """
    add_test_tracks(track_repo, 75)

    totals = []
    for offset in [0, 25, 50, 75]:
        _, total = track_repo.get_all(limit=25, offset=offset)
        totals.append(total)

    assert len(set(totals)) == 1, "Total count should be consistent across all pages"
    assert totals[0] == 75, "Total should be 75"


# ============================================================================
# CATEGORY 4: LARGE OFFSETS (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_offset_equals_total(track_repo):
    """
    BOUNDARY: Offset exactly equals total count (offset=50, total=50).
    Should return empty list.
    """
    add_test_tracks(track_repo, 50)

    tracks, total = track_repo.get_all(limit=50, offset=50)

    assert tracks == [], "Offset = total should return empty list"
    assert total == 50, "Total should be 50"


@pytest.mark.boundary
def test_offset_just_before_total(track_repo):
    """
    BOUNDARY: Offset = total - 1 (offset=49, total=50).
    Should return exactly 1 item (the last item).
    """
    add_test_tracks(track_repo, 50)

    tracks, total = track_repo.get_all(limit=50, offset=49)

    assert len(tracks) == 1, "Should return exactly 1 track (the last one)"
    assert total == 50, "Total should be 50"


@pytest.mark.boundary
def test_offset_exceeds_total(track_repo):
    """
    BOUNDARY: Offset > total count (offset=100, total=50).
    Should return empty list.
    """
    add_test_tracks(track_repo, 50)

    tracks, total = track_repo.get_all(limit=50, offset=100)

    assert tracks == [], "Offset > total should return empty list"
    assert total == 50, "Total should be 50"


@pytest.mark.boundary
def test_very_large_offset(track_repo):
    """
    BOUNDARY: Extremely large offset (offset=1_000_000).
    Should return empty list without error.
    """
    add_test_tracks(track_repo, 10)

    tracks, total = track_repo.get_all(limit=50, offset=1_000_000)

    assert tracks == [], "Very large offset should return empty list"
    assert total == 10, "Total should be 10"


@pytest.mark.boundary
def test_offset_with_small_limit(track_repo):
    """
    BOUNDARY: Large offset with small limit (offset=45, limit=5, total=50).
    Should return exactly 5 items (items 45-49).
    """
    add_test_tracks(track_repo, 50)

    tracks, total = track_repo.get_all(limit=5, offset=45)

    assert len(tracks) == 5, "Should return exactly 5 tracks"
    assert total == 50, "Total should be 50"


@pytest.mark.boundary
def test_offset_near_end_partial_page(track_repo):
    """
    BOUNDARY: Offset near end with partial last page (offset=48, limit=5, total=50).
    Should return 2 items (items 48-49).
    """
    add_test_tracks(track_repo, 50)

    tracks, total = track_repo.get_all(limit=5, offset=48)

    assert len(tracks) == 2, "Should return exactly 2 tracks (remaining items)"
    assert total == 50, "Total should be 50"


# ============================================================================
# CATEGORY 5: INVALID PARAMETERS (6 tests)
# ============================================================================

@pytest.mark.boundary
def test_negative_offset(track_repo):
    """
    BOUNDARY: Negative offset (offset=-1).
    Should handle gracefully (likely treat as 0 or raise).
    """
    add_test_tracks(track_repo, 10)

    # SQLAlchemy treats negative offset as 0
    tracks, total = track_repo.get_all(limit=5, offset=-1)

    # Should either return items or empty list, but not crash
    assert isinstance(tracks, list), "Should return a list"
    assert total == 10, "Total should be 10"


@pytest.mark.boundary
def test_negative_limit(track_repo):
    """
    BOUNDARY: Negative limit (limit=-1).
    Should handle gracefully (likely return empty or all items).
    """
    add_test_tracks(track_repo, 10)

    # SQLAlchemy behavior with negative limit
    tracks, total = track_repo.get_all(limit=-1, offset=0)

    # Should not crash
    assert isinstance(tracks, list), "Should return a list"
    assert total == 10, "Total should be 10"


@pytest.mark.boundary
def test_zero_limit_nonzero_offset(track_repo):
    """
    BOUNDARY: Zero limit with non-zero offset (limit=0, offset=10).
    Should return empty list.
    """
    add_test_tracks(track_repo, 50)

    tracks, total = track_repo.get_all(limit=0, offset=10)

    assert tracks == [], "Limit=0 should always return empty list"
    assert total == 50, "Total should be 50"


@pytest.mark.boundary
def test_very_large_limit(track_repo):
    """
    BOUNDARY: Extremely large limit (limit=1_000_000).
    Should return all available items without error.
    """
    add_test_tracks(track_repo, 50)

    tracks, total = track_repo.get_all(limit=1_000_000, offset=0)

    assert len(tracks) == 50, "Should return all 50 tracks"
    assert total == 50, "Total should be 50"


@pytest.mark.boundary
def test_limit_one(track_repo):
    """
    BOUNDARY: Minimum useful limit (limit=1).
    Should return exactly 1 item per page.
    """
    add_test_tracks(track_repo, 10)

    # Get first 3 pages with limit=1
    page1, _ = track_repo.get_all(limit=1, offset=0)
    page2, _ = track_repo.get_all(limit=1, offset=1)
    page3, _ = track_repo.get_all(limit=1, offset=2)

    assert len(page1) == 1, "Page 1 should have 1 item"
    assert len(page2) == 1, "Page 2 should have 1 item"
    assert len(page3) == 1, "Page 3 should have 1 item"

    # Ensure they're different tracks
    ids = {page1[0].id, page2[0].id, page3[0].id}
    assert len(ids) == 3, "Each page should return a different track"


@pytest.mark.boundary
def test_order_consistency_across_pages(track_repo):
    """
    INVARIANT: Order should be consistent when paginating.
    Items should appear in same order regardless of page boundaries.
    """
    add_test_tracks(track_repo, 100)

    # Get all tracks in one query (sorted by title)
    all_tracks, _ = track_repo.get_all(limit=100, offset=0, order_by='title')
    all_ids = [t.id for t in all_tracks]

    # Get tracks in pages
    paginated_ids = []
    for page_num in range(4):  # 4 pages of 25
        tracks, _ = track_repo.get_all(limit=25, offset=page_num * 25, order_by='title')
        paginated_ids.extend([t.id for t in tracks])

    assert paginated_ids == all_ids, (
        "Order should be consistent between single query and paginated queries"
    )
