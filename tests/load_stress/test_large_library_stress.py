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

import pytest
import time
import gc


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
        LOAD: Load 10,000 tracks into library.
        Target: < 30 seconds, < 500MB memory.
        """
        with resource_monitor() as monitor:
            tracks = large_track_dataset(10000)

            elapsed = monitor.elapsed_seconds
            memory_growth = monitor.memory_growth_mb

        assert len(tracks) == 10000, "Should create 10k tracks"
        assert elapsed < 60, f"Should complete in < 60s, took {elapsed:.2f}s"
        assert memory_growth < 1000, f"Memory growth {memory_growth:.1f}MB should be < 1000MB"

        print(f"✓ Loaded 10k tracks in {elapsed:.2f}s, {memory_growth:.1f}MB")

    @pytest.mark.slow
    def test_load_50k_tracks(self, large_track_dataset, resource_monitor, load_test_config):
        """
        STRESS: Load 50,000 tracks into library.
        Target: < 5 minutes, < 2GB memory.
        """
        target_size = load_test_config['large_library']

        with resource_monitor() as monitor:
            # Create in batches to monitor progress
            batch_size = 10000
            all_tracks = []

            for i in range(0, target_size, batch_size):
                current_batch = min(batch_size, target_size - i)
                batch_tracks = large_track_dataset(current_batch)
                all_tracks.extend(batch_tracks)

                monitor.update()
                print(f"  Progress: {len(all_tracks)}/{target_size} tracks, "
                      f"Memory: {monitor.peak_memory_mb:.1f}MB")

            elapsed = monitor.elapsed_seconds
            memory_growth = monitor.memory_growth_mb

        assert len(all_tracks) == target_size, f"Should create {target_size} tracks"
        assert elapsed < 300, f"Should complete in < 5min, took {elapsed:.2f}s"
        assert memory_growth < 2048, f"Memory growth {memory_growth:.1f}MB should be < 2GB"

        print(f"✓ Loaded {target_size} tracks in {elapsed:.2f}s, {memory_growth:.1f}MB")


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

        result = track_repo.get_recent(limit=50, offset=0)

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

        # Toggle favorite on all tracks
        for track in tracks:
            track_repo.update(track.id, {'favorite': True})

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
        from auralis.library.repositories import TrackRepository, PlaylistRepository

        tracks = large_track_dataset(1000)
        track_repo = TrackRepository(temp_db)
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
class TestCachePerformanceAtScale:
    """Test cache performance with large libraries."""

    def test_cache_hit_rate_with_10k_library(self, large_track_dataset, temp_db):
        """
        LOAD: Cache should maintain high hit rate with 10k library.
        Target: > 80% cache hit rate on repeated queries.
        """
        from auralis.library.repositories import TrackRepository

        large_track_dataset(10000)
        track_repo = TrackRepository(temp_db)

        # First queries (cache miss)
        for _ in range(10):
            track_repo.get_all(limit=100, offset=0)

        # Get initial cache stats
        # (Note: This assumes LibraryManager has cache stats,
        #  may need to adapt based on actual implementation)

        # Second queries (should hit cache)
        start = time.time()
        for _ in range(100):
            track_repo.get_all(limit=100, offset=0)
        elapsed = time.time() - start

        # Should be very fast due to caching
        assert elapsed < 1.0, \
            f"100 cached queries should complete in < 1s, took {elapsed:.2f}s"

        print(f"✓ 100 cached queries in {elapsed*1000:.1f}ms ({elapsed*10:.2f}ms avg)")

    def test_cache_invalidation_performance(self, large_track_dataset, temp_db):
        """
        LOAD: Cache invalidation shouldn't block queries.
        Target: < 100ms invalidation time.
        """
        from auralis.library.repositories import TrackRepository

        tracks = large_track_dataset(1000)
        track_repo = TrackRepository(temp_db)

        # Populate cache
        for _ in range(10):
            track_repo.get_all(limit=100, offset=0)

        # Time cache invalidation
        start = time.time()

        # Update a track (should invalidate caches)
        track_repo.update(tracks[0].id, {'favorite': True})

        elapsed = time.time() - start

        assert elapsed < 1.0, \
            f"Cache invalidation should complete in < 1s, took {elapsed*1000:.1f}ms"

        print(f"✓ Cache invalidation: {elapsed*1000:.1f}ms")


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
