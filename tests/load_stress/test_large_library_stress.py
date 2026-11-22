"""
Large Library Stress Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for handling large music libraries (10k-100k tracks).

STRESS SCENARIOS:
- 50k track library operations
- Full library scans
- Mass metadata updates
- Bulk playlist operations
- Search across massive datasets
- Pagination performance at scale
"""

import gc
import time

import pytest


@pytest.mark.load
@pytest.mark.slow
class TestLargeLibraryLoading:
    """Test loading and querying large libraries."""

    def test_load_1k_tracks(self, large_track_dataset, resource_monitor):
        """
        LOAD: Load 1,000 tracks into library.
        Target: < 5 seconds, < 100MB memory.
        """
        with resource_monitor() as monitor:
            tracks = large_track_dataset(1000)

            elapsed = monitor.elapsed_seconds
            memory_growth = monitor.memory_growth_mb

        assert len(tracks) == 1000, "Should create 1000 tracks"
        assert elapsed < 10, f"Should complete in < 10s, took {elapsed:.2f}s"
        assert memory_growth < 200, f"Memory growth {memory_growth:.1f}MB should be < 200MB"

        print(f"✓ Loaded 1k tracks in {elapsed:.2f}s, {memory_growth:.1f}MB")

    def test_load_10k_tracks(self, large_track_dataset, resource_monitor):
        """
        LOAD: 10,000 add() calls in < 100s (10ms per track), < 1GB growth.

        ~27s locally (2.7ms per track: a duplicate lookup, artist/album
        resolution, two flushes, a commit and two refreshes). CI runners are
        about twice as slow, which put the old 60s limit within noise of the
        expected time. Whether the cost per track stays flat as the library
        grows is test_add_cost_flat_up_to_50k_tracks's job.
        """
        with resource_monitor() as monitor:
            tracks = large_track_dataset(10000)

            elapsed = monitor.elapsed_seconds
            memory_growth = monitor.memory_growth_mb

        assert len(tracks) == 10000, "Should create 10k tracks"
        assert len({t.id for t in tracks}) == 10000
        assert elapsed < 100, f"Should complete in < 100s, took {elapsed:.2f}s"
        assert memory_growth < 1000, f"Memory growth {memory_growth:.1f}MB should be < 1000MB"

        print(f"✓ Loaded 10k tracks in {elapsed:.2f}s, {memory_growth:.1f}MB")

    def test_add_cost_flat_up_to_50k_tracks(self, large_track_dataset, temp_db, load_test_config):
        """
        STRESS: add() costs the same in a 50k-track library as in an empty one.

        add() starts with a filepath lookup that carries the standard eager
        loads. While Track.artists was joinedload-ed, that lookup scanned all
        of track_artist, which made building a library quadratic: 50k tracks
        hit the 300s per-test timeout on CI. Even at a linear 2.7ms per track,
        50k add() calls take ~5 min on CI, so the middle of the library is
        bulk-inserted and add() is timed at the empty end and the full end.
        """
        from sqlalchemy import insert, select

        from auralis.library.models import Artist, Track, track_artist
        from auralis.library.path_key import make_filepath_key
        from auralis.library.repositories import TrackRepository

        target = load_test_config['large_library']
        sample = 2000

        def seconds_per_add() -> float:
            start = time.perf_counter()
            batch = large_track_dataset(sample)
            elapsed = time.perf_counter() - start
            assert len({t.id for t in batch}) == sample
            return elapsed / sample

        empty_cost = seconds_per_add()

        session = temp_db()
        artist_ids = session.execute(select(Artist.id)).scalars().all()
        paths = [f'/tmp/seeded_track_{i}.flac' for i in range(target - 2 * sample)]
        track_ids = session.scalars(
            insert(Track).returning(Track.id),
            [{'title': f'Seeded Track {i}', 'filepath': path, 'filepath_key': make_filepath_key(path),
              'format': 'FLAC', 'sample_rate': 44100, 'channels': 2, 'duration': 180.0}
             for i, path in enumerate(paths)],
        ).all()
        session.execute(
            insert(track_artist),
            [{'track_id': track_id, 'artist_id': artist_ids[i % len(artist_ids)], 'position': 0}
             for i, track_id in enumerate(track_ids)],
        )
        session.commit()
        session.close()

        full_cost = seconds_per_add()

        assert TrackRepository(temp_db).get_all(limit=1)[1] == target
        assert full_cost < 2 * empty_cost, (
            f"add() took {full_cost * 1000:.2f}ms per track at {target} tracks vs "
            f"{empty_cost * 1000:.2f}ms on an empty library"
        )

        print(f"✓ add(): {empty_cost * 1000:.2f}ms/track empty, "
              f"{full_cost * 1000:.2f}ms/track at {target} tracks")


@pytest.mark.load
class TestLargeLibraryQueries:
    """Test querying large libraries."""

    def test_query_all_tracks_from_10k_library(self, large_track_dataset, temp_db):
        """
        LOAD: Query all tracks from 10k library with pagination.
        Target: < 5 seconds total, no duplicates.
        """
        from auralis.library.repositories import TrackRepository

        # Create 10k tracks
        large_track_dataset(10000)

        track_repo = TrackRepository(temp_db)

        start = time.time()
        all_track_ids = set()
        offset = 0
        limit = 100

        while True:
            result = track_repo.get_all(limit=limit, offset=offset)

            if isinstance(result, tuple):
                tracks, total = result
            else:
                tracks = result
                total = len(tracks)

            if not tracks:
                break

            # Check for duplicates
            track_ids = {t.id for t in tracks}
            assert not (all_track_ids & track_ids), \
                f"Duplicate tracks found at offset {offset}"

            all_track_ids.update(track_ids)
            offset += limit

            if offset >= total:
                break

        elapsed = time.time() - start

        assert len(all_track_ids) == 10000, "Should retrieve all 10k tracks"
        assert elapsed < 10, f"Should complete in < 10s, took {elapsed:.2f}s"

        print(f"✓ Queried 10k tracks in {elapsed:.2f}s, {len(all_track_ids)} unique")

    def test_search_across_10k_tracks(self, large_track_dataset, temp_db):
        """
        LOAD: Search across 10k track library.
        Target: < 1 second per search.
        """
        from auralis.library.repositories import TrackRepository

        large_track_dataset(10000)
        track_repo = TrackRepository(temp_db)

        search_queries = [
            'Track 1',      # High results
            'Track 100',    # Medium results
            'Track 9999',   # Low results
            'Album 50',     # Album search
            'Artist 25',    # Artist search
        ]

        for query in search_queries:
            start = time.time()

            result = track_repo.search(query, limit=100, offset=0)

            if isinstance(result, tuple):
                results, total = result
            else:
                results = result

            elapsed = time.time() - start

            assert elapsed < 2.0, \
                f"Search '{query}' took {elapsed:.2f}s, expected < 2s"

            print(f"  ✓ Search '{query}': {len(results)} results in {elapsed*1000:.1f}ms")

    def test_get_recent_tracks_from_large_library(self, large_track_dataset, temp_db):
        """
        LOAD: Get recent tracks from 10k library.
        Target: < 100ms (should use created_at index).
        """
        from auralis.library.repositories import TrackRepository

        large_track_dataset(10000)
        track_repo = TrackRepository(temp_db)

        start = time.time()

        result = track_repo.get_all(limit=50, offset=0, order_by='created_at', order='desc')

        if isinstance(result, tuple):
            recent_tracks, total = result
        else:
            recent_tracks = result

        elapsed = time.time() - start

        assert len(recent_tracks) <= 50, "Should return at most 50 tracks"
        assert elapsed < 0.5, f"Should complete in < 500ms, took {elapsed*1000:.1f}ms"

        print(f"✓ Recent tracks query: {elapsed*1000:.1f}ms")


@pytest.mark.load
class TestLargeLibraryUpdates:
    """Test bulk update operations on large libraries."""

    def test_mass_favorite_toggle(self, large_track_dataset, temp_db):
        """
        LOAD: Toggle favorite on 1000 tracks.
        Target: < 10 seconds.
        """
        from auralis.library.repositories import TrackRepository

        tracks = large_track_dataset(1000)
        track_repo = TrackRepository(temp_db)

        start = time.time()

        # Toggle favorite on all tracks. set_favorite() is the production
        # write path (routers/tracks.py); update() deliberately refuses
        # 'favorite' (not in its field allowlist), so the old
        # update(id, {'favorite': True}) loop silently no-opped (#5486).
        for track in tracks:
            track_repo.set_favorite(track.id, True)

        elapsed = time.time() - start

        assert elapsed < 30, f"Should complete in < 30s, took {elapsed:.2f}s"

        # Verify updates
        favorites = track_repo.get_favorites(limit=1000, offset=0)

        if isinstance(favorites, tuple):
            fav_tracks, total = favorites
        else:
            fav_tracks = favorites

        assert len(fav_tracks) == 1000, "All tracks should be favorited"

        print(f"✓ Mass favorite toggle: {elapsed:.2f}s")

    def test_bulk_play_count_increment(self, large_track_dataset, temp_db):
        """
        LOAD: Increment play count on 1000 tracks.
        Target: < 10 seconds.
        """
        from auralis.library.repositories import TrackRepository

        tracks = large_track_dataset(1000)
        track_repo = TrackRepository(temp_db)

        start = time.time()

        # Increment play count
        for track in tracks:
            current_count = track.play_count or 0
            track_repo.update(track.id, {'play_count': current_count + 1})

        elapsed = time.time() - start

        assert elapsed < 30, f"Should complete in < 30s, took {elapsed:.2f}s"

        print(f"✓ Bulk play count increment: {elapsed:.2f}s")


@pytest.mark.load
@pytest.mark.slow
class TestLargePlaylistOperations:
    """Test playlist operations with large track sets."""

    def test_create_playlist_with_1k_tracks(self, large_track_dataset, temp_db):
        """
        LOAD: Create playlist with 1000 tracks.
        Target: < 5 seconds.
        """
        from auralis.library.repositories import PlaylistRepository

        tracks = large_track_dataset(1000)
        playlist_repo = PlaylistRepository(temp_db)

        start = time.time()

        # Create playlist
        playlist = playlist_repo.create('Large Playlist')

        # Add all tracks
        for track in tracks:
            playlist_repo.add_track(playlist.id, track.id)

        elapsed = time.time() - start

        assert elapsed < 15, f"Should complete in < 15s, took {elapsed:.2f}s"

        print(f"✓ Created 1k-track playlist in {elapsed:.2f}s")

    def test_retrieve_large_playlist(self, large_track_dataset, temp_db):
        """
        LOAD: Retrieve playlist with 1000 tracks.
        Target: < 2 seconds.
        """
        from auralis.library.repositories import PlaylistRepository

        tracks = large_track_dataset(1000)
        playlist_repo = PlaylistRepository(temp_db)

        # Create playlist with tracks
        playlist = playlist_repo.create('Test Playlist')
        for track in tracks:
            playlist_repo.add_track(playlist.id, track.id)

        start = time.time()

        # Retrieve playlist
        retrieved = playlist_repo.get_by_id(playlist.id)

        elapsed = time.time() - start

        assert retrieved is not None
        assert elapsed < 2.0, f"Should complete in < 2s, took {elapsed:.2f}s"

        print(f"✓ Retrieved 1k-track playlist in {elapsed*1000:.1f}ms")


@pytest.mark.load
class TestRepeatedQueriesAtScale:
    """Repeated reads and a write between them on a large library.

    These were TestCachePerformanceAtScale, but the repositories have no
    query cache: every get_all() goes to SQLite. What they measure is
    uncached page latency, so they are named and budgeted for that.
    """

    def test_repeated_page_queries_with_10k_library(self, large_track_dataset, temp_db):
        """
        LOAD: 100 x get_all(limit=100) on a 10k library in < 1s.

        Each call is a COUNT(*) plus the page and its selectin loads,
        ~3.7ms locally. While Track.artists was joinedload-ed, the page
        query materialized all of track_artist per call (~18ms on CI).
        """
        from auralis.library.repositories import TrackRepository

        large_track_dataset(10000)
        track_repo = TrackRepository(temp_db)
        first_page, total = track_repo.get_all(limit=100, offset=0)
        assert total == 10000
        assert len(first_page) == 100

        start = time.time()
        for _ in range(100):
            page, _ = track_repo.get_all(limit=100, offset=0)
        elapsed = time.time() - start

        assert [t.id for t in page] == [t.id for t in first_page]
        assert elapsed < 1.0, \
            f"100 page queries should complete in < 1s, took {elapsed:.2f}s"

        print(f"✓ 100 page queries in {elapsed*1000:.1f}ms ({elapsed*10:.2f}ms avg)")

    def test_update_between_page_reads(self, large_track_dataset, temp_db):
        """
        LOAD: An update after repeated reads takes < 1s and the next read sees it.
        """
        from auralis.library.repositories import TrackRepository

        tracks = large_track_dataset(1000)
        track_repo = TrackRepository(temp_db)

        for _ in range(10):
            track_repo.get_all(limit=100, offset=0)

        # update() writes metadata (title, year, artists, ...); favorites go
        # through set_favorite(), so {'favorite': True} here was a no-op that
        # nothing checked.
        start = time.time()
        updated = track_repo.update(tracks[0].id, {'title': 'Renamed Track'})
        elapsed = time.time() - start

        assert updated is not None and updated.title == 'Renamed Track'
        assert track_repo.get_by_id(tracks[0].id).title == 'Renamed Track'
        assert elapsed < 1.0, \
            f"Update should complete in < 1s, took {elapsed*1000:.1f}ms"

        print(f"✓ Update between reads: {elapsed*1000:.1f}ms")


@pytest.mark.load
class TestMemoryEfficiencyAtScale:
    """Test memory efficiency with large libraries."""

    def test_memory_stable_with_repeated_queries(self, large_track_dataset, temp_db, resource_monitor):
        """
        LOAD: Memory should remain stable with repeated queries.
        Target: < 50MB growth over 1000 queries.
        """
        from auralis.library.repositories import TrackRepository

        large_track_dataset(1000)
        track_repo = TrackRepository(temp_db)

        with resource_monitor() as monitor:
            # Run 1000 queries
            for i in range(1000):
                track_repo.get_all(limit=50, offset=(i * 50) % 1000)

                if i % 100 == 0:
                    gc.collect()  # Force garbage collection
                    monitor.update()

            final_memory_growth = monitor.memory_growth_mb

        assert final_memory_growth < 100, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 100MB"

        print(f"✓ 1000 queries, memory growth: {final_memory_growth:.1f}MB")

    def test_no_memory_leak_in_track_iteration(self, large_track_dataset, temp_db, resource_monitor):
        """
        LOAD: Iterating through all tracks shouldn't leak memory.
        Target: < 100MB growth after full iteration.
        """
        from auralis.library.repositories import TrackRepository

        large_track_dataset(10000)
        track_repo = TrackRepository(temp_db)

        with resource_monitor() as monitor:
            offset = 0
            limit = 100

            while True:
                result = track_repo.get_all(limit=limit, offset=offset)

                if isinstance(result, tuple):
                    tracks, total = result
                else:
                    tracks = result
                    total = len(tracks) if tracks else 0

                if not tracks:
                    break

                # Process tracks (simulate work)
                for track in tracks:
                    _ = track.title  # Access attribute

                offset += limit

                if offset % 1000 == 0:
                    gc.collect()
                    monitor.update()

                if offset >= total:
                    break

            final_memory_growth = monitor.memory_growth_mb

        assert final_memory_growth < 200, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 200MB"

        print(f"✓ Full iteration, memory growth: {final_memory_growth:.1f}MB")
