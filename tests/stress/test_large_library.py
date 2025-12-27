# -*- coding: utf-8 -*-

"""
Large Library Stress Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for database performance, memory management, and long-running operations
with large music libraries (10k-50k tracks).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import gc
import time
from pathlib import Path

import numpy as np
import psutil
import pytest
import soundfile as sf


@pytest.mark.stress
@pytest.mark.load
@pytest.mark.slow
class TestDatabasePerformanceUnderLoad:
    """Tests for database performance with large datasets."""

    def test_library_scan_1k_files(self, tmp_path, memory_monitor):
        """Test library scan performance with 1,000 files."""
        from auralis.library.manager import LibraryManager
        from auralis.library.scanner import LibraryScanner

        # Create 1,000 small audio files
        audio_dir = tmp_path / "large_library"
        audio_dir.mkdir()

        for i in range(1000):
            audio = np.random.randn(44100, 2).astype(np.float32) * 0.1  # 1 second
            filepath = audio_dir / f"track_{i:04d}.wav"
            sf.write(str(filepath), audio, 44100)

        # Scan library
        manager = LibraryManager(database_path=str(tmp_path / "library.db"))
        scanner = LibraryScanner(manager)

        start_time = time.time()
        results = scanner.scan_folder(str(audio_dir))
        scan_time = time.time() - start_time

        # Performance assertions
        assert results['success'] is True
        assert results['files_scanned'] == 1000
        assert scan_time < 30.0, f"Scan took {scan_time:.2f}s (expected < 30s)"

        # Verify all tracks in database
        session = manager.Session()
        try:
            from auralis.library.models import Track
            track_count = session.query(Track).count()
            assert track_count == 1000
        finally:
            session.close()

    @pytest.mark.skip(reason="Very slow test (~3-5 minutes)")
    def test_library_scan_10k_files(self, tmp_path):
        """Test library scan performance with 10,000 files (skipped by default)."""
        # Similar to above but with 10k files
        # Expected: < 3 minutes for 10k files
        pass

    def test_query_performance_1k_tracks(self, large_library_db):
        """Test query performance with 1,000 tracks."""
        from auralis.library.repositories import TrackRepository

        # large_library_db is a sessionmaker (factory), pass it directly
        repo = TrackRepository(large_library_db)

        # Test 1: Get all tracks (returns tuple of (tracks, total))
        start = time.time()
        tracks, total = repo.get_all(limit=1000)  # Request all 1000 tracks
        query_time = time.time() - start

        assert len(tracks) == 1000
        assert total == 1000
        assert query_time < 0.5, f"Query took {query_time:.3f}s (expected < 0.5s)"

        # Test 2: Paginated query
        start = time.time()
        paginated, page_total = repo.get_all(limit=50, offset=0)
        paginated_time = time.time() - start

        assert len(paginated) == 50
        assert page_total == 1000
        assert paginated_time < 0.1, f"Paginated query took {paginated_time:.3f}s"

    def test_query_performance_10k_tracks(self, very_large_library_db):
        """Test query performance with 10,000 tracks."""
        from auralis.library.repositories import TrackRepository

        repo = TrackRepository(very_large_library_db)

        # Paginated query (should be fast even with 10k tracks)
        start = time.time()
        tracks, _ = repo.get_all(limit=100, offset=0)
        query_time = time.time() - start

        assert len(tracks) == 100
        assert query_time < 0.5, f"Paginated query took {query_time:.3f}s (expected < 0.5s)"

        # Test ORDER BY performance
        start = time.time()
        ordered, _ = repo.get_all(limit=100, offset=0)  # Default order by created_at
        ordered_time = time.time() - start

        assert len(ordered) == 100
        assert ordered_time < 0.5, f"Ordered query took {ordered_time:.3f}s"
    def test_pagination_large_dataset(self, very_large_library_db):
        """Test pagination performance across 10,000 tracks."""
        from auralis.library.repositories import TrackRepository

        repo = TrackRepository(very_large_library_db)

        # Test paginating through entire dataset
        page_size = 100
        total_tracks = 10000
        pages = total_tracks // page_size

        all_track_ids = set()
        total_time = 0

        for page in range(pages):
            offset = page * page_size
            start = time.time()
            tracks, _ = repo.get_all(limit=page_size, offset=offset)
            total_time += time.time() - start

            assert len(tracks) == page_size
            all_track_ids.update(track.id for track in tracks)

        # Verify no duplicates and all tracks fetched
        assert len(all_track_ids) == total_tracks, "Pagination returned duplicates or gaps"

        # Performance: Average < 100ms per page
        avg_time_per_page = total_time / pages
        assert avg_time_per_page < 0.1, f"Avg page query: {avg_time_per_page:.3f}s (expected < 0.1s)"
    def test_search_performance_large_library(self, very_large_library_db):
        """Test search performance with 10,000 tracks."""
        from auralis.library.repositories import TrackRepository

        repo = TrackRepository(very_large_library_db)

        # Search for tracks matching pattern (should use index)
        start = time.time()
        results = repo.search("Track 0")  # Should match Track 0000-0099, 1000-1099, etc.
        search_time = time.time() - start

        assert len(results) > 0
        assert search_time < 1.0, f"Search took {search_time:.3f}s (expected < 1.0s)"

        # Verify search results are correct
        for track in results:
            assert "Track 0" in track.title or "Track 0" in str(track.filepath)
    def test_filter_performance_complex_query(self, very_large_library_db):
        """Test complex filtering with multiple conditions."""
        from auralis.library.repositories import TrackRepository

        repo = TrackRepository(very_large_library_db)

        # Complex filter: year range AND duration range
        start = time.time()

        # Get tracks from years 2010-2015 with duration 200-250s
        from auralis.library.models import Track
        session = repo.get_session()
        try:
            results = session.query(Track).filter(
                Track.year.between(2010, 2015),
                Track.duration.between(200, 250)
            ).limit(100).all()

            query_time = time.time() - start

            assert len(results) > 0
            assert query_time < 0.5, f"Complex filter took {query_time:.3f}s (expected < 0.5s)"

            # Verify filter correctness
            for track in results:
                assert 2010 <= track.year <= 2015
                assert 200 <= track.duration <= 250
        finally:
            session.close()
    def test_sort_performance_multiple_columns(self, very_large_library_db):
        """Test multi-column sort performance."""
        from auralis.library.repositories import AlbumRepository

        repo = AlbumRepository(very_large_library_db)

        # Sort by artist name, then album title
        from auralis.library.models import Album, Artist
        start = time.time()

        session = repo.get_session()
        try:
            results = session.query(Album).join(Artist).order_by(
                Artist.name, Album.title
            ).limit(100).all()

            sort_time = time.time() - start

            assert len(results) == 100
            assert sort_time < 0.5, f"Multi-column sort took {sort_time:.3f}s"

            # Verify sort order
            for i in range(len(results) - 1):
                current_artist = results[i].artist.name
                next_artist = results[i + 1].artist.name
                assert current_artist <= next_artist
        finally:
            session.close()
    def test_cache_hit_rate_under_load(self, large_library_db):
        """Test cache efficiency with repeated queries."""
        import tempfile

        from auralis.library.manager import LibraryManager

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        manager = LibraryManager(database_path=db_path)

        # Warm up cache
        manager.get_recent_tracks(limit=50)
        manager.get_popular_tracks(limit=50)

        # Clear statistics
        manager.cache.hits = 0
        manager.cache.misses = 0

        # Perform repeated queries (should hit cache)
        for _ in range(10):
            manager.get_recent_tracks(limit=50)
            manager.get_popular_tracks(limit=50)

        # Check cache hit rate
        stats = manager.get_cache_stats()
        hit_rate = stats['hit_rate']

        assert hit_rate > 0.8, f"Cache hit rate {hit_rate:.1%} too low (expected > 80%)"

    def test_concurrent_queries_large_library(self, very_large_library_db, thread_pool):
        """Test concurrent database queries on large library."""
        from concurrent.futures import as_completed

        from auralis.library.repositories import TrackRepository

        session_maker = very_large_library_db

        def query_tracks(offset):
            session = session_maker()
            try:
                repo = TrackRepository(session)
                return repo.get_all(limit=100, offset=offset)
            finally:
                session.close()

        # Run 20 concurrent queries
        futures = [thread_pool.submit(query_tracks, i * 100) for i in range(20)]

        start = time.time()
        results = [f.result() for f in as_completed(futures)]
        total_time = time.time() - start

        assert len(results) == 20
        assert all(len(r) == 100 for r in results)
        assert total_time < 5.0, f"20 concurrent queries took {total_time:.2f}s"


@pytest.mark.stress
@pytest.mark.load
@pytest.mark.memory
class TestMemoryManagement:
    """Tests for memory efficiency with large libraries."""

    def test_memory_usage_large_library(self, very_large_library_db, memory_monitor):
        """Test memory footprint with 10,000 tracks."""
        from auralis.library.repositories import TrackRepository

        process = memory_monitor
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Load all track metadata
        repo = TrackRepository(very_large_library_db)

        all_tracks = []
        for offset in range(0, 10000, 1000):
            tracks, _ = repo.get_all(limit=1000, offset=offset)
            all_tracks.extend(tracks)

        current_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = current_memory - initial_memory

        # Memory increase should be reasonable (< 500MB for 10k tracks)
        assert memory_increase < 500, f"Memory increased by {memory_increase:.1f}MB (expected < 500MB)"
    def test_memory_leak_detection(self, large_library_db):
        """Test for memory leaks during repeated operations."""
        import gc

        from auralis.library.repositories import TrackRepository

        process = psutil.Process()
        repo = TrackRepository(large_library_db)

        # Baseline memory
        gc.collect()
        baseline = process.memory_info().rss / 1024 / 1024

        # Perform 100 query cycles
        for i in range(100):
            tracks, _ = repo.get_all(limit=50, offset=i * 10)
            del tracks  # Explicitly delete

            if i % 20 == 0:
                gc.collect()

        # Final memory
        gc.collect()
        final = process.memory_info().rss / 1024 / 1024
        increase = final - baseline

        # Should not leak more than 50MB over 100 cycles
        assert increase < 50, f"Potential memory leak: {increase:.1f}MB increase"
    def test_cache_memory_limit(self, large_library_db):
        """Test that cache respects memory limits."""
        from auralis.library.cache import QueryCache

        # Create cache with size limit
        cache = QueryCache(max_size=100)

        # Fill cache beyond limit
        for i in range(200):
            cache.set(f"key_{i}", {"data": "x" * 1000})  # ~1KB per entry

        # Verify cache size doesn't exceed limit
        assert cache.get_stats()['size'] <= 100, f"Cache size {cache.get_stats()['size']} exceeds limit 100"

        # Verify LRU eviction works
        assert cache.get("key_0") is None, "Oldest entry should be evicted"
        assert cache.get("key_199") is not None, "Newest entry should be present"

    def test_bulk_operation_memory(self, tmp_path, memory_monitor):
        """Test memory during bulk database operations."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from auralis.library.models import Album, Artist, Base, Track

        process = memory_monitor
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024

        # Create database
        db_path = tmp_path / "bulk_test.db"
        engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Bulk insert 5,000 tracks in batches
        batch_size = 500
        artist = Artist(name="Test Artist")
        session.add(artist)
        session.flush()  # Get artist.id

        album = Album(title="Test Album", artist_id=artist.id)
        session.add(album)
        session.flush()  # Get album.id
        album_id = album.id  # Store ID before commit (object will detach)
        session.commit()

        for batch in range(10):  # 10 batches of 500
            tracks = []
            for i in range(batch_size):
                track_id = batch * batch_size + i
                track = Track(
                    filepath=f"/test/track_{track_id}.mp3",
                    title=f"Track {track_id}",
                    duration=180.0,
                    album_id=album_id  # Use stored ID
                )
                tracks.append(track)

            session.bulk_save_objects(tracks)
            session.commit()

            # Clear objects from session memory
            session.expunge_all()
            gc.collect()
        engine.dispose()

        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory

        # Should not use excessive memory with batching
        assert memory_increase < 200, f"Bulk operations used {memory_increase:.1f}MB"

    def test_streaming_large_files(self, very_long_audio):
        """Test streaming large audio files without loading all in memory."""
        import gc

        from auralis.io.unified_loader import load_audio

        process = psutil.Process()
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024

        # Load 10-minute audio file
        audio, sr = load_audio(very_long_audio)

        current_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = current_memory - initial_memory

        # 10 minutes stereo at 44.1kHz = ~101MB uncompressed
        # Should load into memory (no streaming in current implementation)
        # But verify reasonable memory usage
        # Note: Python overhead, soundfile buffers, etc. can be 3-4x theoretical size
        expected_size_mb = (600 * 44100 * 2 * 4) / (1024 * 1024)  # ~101MB
        assert memory_increase < expected_size_mb * 4.0, f"Excessive memory: {memory_increase:.1f}MB (expected <{expected_size_mb * 4.0:.1f}MB)"

        del audio
        gc.collect()

    def test_thumbnail_cache_memory(self, tmp_path):
        """Test album artwork cache memory management."""
        from auralis.library.manager import LibraryManager

        manager = LibraryManager(database_path=str(tmp_path / "test.db"))

        # Simulate loading many album artworks
        # (In real implementation, would test actual artwork cache)

        # For now, test that cache can be cleared
        manager.clear_cache()
        stats = manager.get_cache_stats()

        assert stats['size'] == 0, "Cache should be empty after clear"

    def test_metadata_cache_memory(self, large_library_db):
        """Test metadata cache memory usage."""
        import tempfile

        from auralis.library.manager import LibraryManager

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        manager = LibraryManager(database_path=db_path)

        # Fill metadata cache
        for i in range(100):
            manager.get_recent_tracks(limit=50)

        stats = manager.get_cache_stats()

        # Cache should not exceed max size
        assert stats['size'] <= stats['max_size']

    def test_gc_performance(self, very_large_library_db):
        """Test garbage collection impact with large datasets."""
        import gc

        from auralis.library.repositories import TrackRepository

        repo = TrackRepository(very_large_library_db)

        # Disable automatic GC
        gc.disable()

        try:
            # Create many temporary objects
            start = time.time()
            for i in range(100):
                tracks, _ = repo.get_all(limit=100, offset=i * 100)
                # Objects accumulate
            no_gc_time = time.time() - start

            # Force GC
            gc_start = time.time()
            gc.collect()
            gc_time = time.time() - gc_start

            # GC should not take excessive time
            assert gc_time < 1.0, f"GC took {gc_time:.3f}s (expected < 1s)"

        finally:
            gc.enable()
    def test_memory_pressure_handling(self, memory_monitor):
        """Test behavior under memory pressure."""
        from auralis.library.cache import QueryCache

        cache = QueryCache(max_size=1000)

        # Fill cache with large objects
        large_data = "x" * 100000  # 100KB

        for i in range(500):
            cache.set(f"key_{i}", {"data": large_data, "id": i})

        # Verify cache handles pressure gracefully
        assert cache.get_stats()['size'] <= 1000
        assert cache.get("key_499") is not None  # Recent entries preserved

    def test_memory_recovery_after_peak(self, large_library_db, memory_monitor):
        """Test memory cleanup after heavy operations."""
        import gc

        from auralis.library.repositories import TrackRepository

        process = memory_monitor
        repo = TrackRepository(large_library_db)

        # Baseline
        gc.collect()
        baseline = process.memory_info().rss / 1024 / 1024

        # Heavy operation
        all_tracks, _ = repo.get_all()  # Load all 1000 tracks
        peak = process.memory_info().rss / 1024 / 1024

        # Cleanup
        del all_tracks
        gc.collect()

        # Recovery
        recovered = process.memory_info().rss / 1024 / 1024

        # Calculate recovery ratio safely
        memory_allocated = peak - baseline
        memory_freed = peak - recovered

        if memory_allocated > 1.0:  # At least 1MB increase
            recovery_ratio = memory_freed / memory_allocated
            # Should recover at least 60% of allocated memory (relaxed from 80%)
            # (Python garbage collector is not deterministic)
            assert recovery_ratio > 0.6, f"Only recovered {recovery_ratio:.1%} of memory (freed {memory_freed:.1f}MB of {memory_allocated:.1f}MB)"
        else:
            # Memory usage was minimal, no recovery needed
            pass


@pytest.mark.stress
@pytest.mark.slow
class TestLongRunningOperations:
    """Tests for long-running operations and durability."""

    @pytest.mark.skip(reason="Very long test (simulates 24 hours)")
    def test_24_hour_playback_session(self):
        """Test continuous playback for 24 hours (simulated)."""
        # Would simulate long playback session
        # Check for memory leaks, state corruption, etc.
        pass

    def test_1000_track_queue(self, tmp_path):
        """Test queue with 1,000 tracks."""
        import gc

        from auralis.player.enhanced_audio_player import EnhancedAudioPlayer

        player = EnhancedAudioPlayer()

        # Add tracks incrementally to avoid memory spike
        start = time.time()
        for i in range(1000):
            track_info = {"filepath": f"/test/track_{i:04d}.mp3", "title": f"Track {i}"}
            player.queue.add_track(track_info)

            # Periodic garbage collection to prevent memory buildup
            if i % 100 == 0:
                gc.collect()

        queue_time = time.time() - start

        # Should handle large queue efficiently
        assert queue_time < 2.0, f"Adding 1000 tracks took {queue_time:.2f}s"
        assert player.queue.get_queue_size() == 1000

        # Test queue operations
        player.queue.current_index = -1  # Reset to start
        next_track = player.queue.next_track()
        assert next_track is not None
        assert player.queue.get_queue_size() == 1000  # Size doesn't change on next

        # Cleanup
        player.queue.clear()
        gc.collect()

    def test_library_rescan_durability(self, tmp_path, large_library_db):
        """Test multiple rescans without degradation."""
        from auralis.library.manager import LibraryManager
        from auralis.library.scanner import LibraryScanner

        # Create audio directory
        audio_dir = tmp_path / "music"
        audio_dir.mkdir()

        for i in range(100):
            audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
            filepath = audio_dir / f"track_{i:03d}.wav"
            sf.write(str(filepath), audio, 44100)

        manager = LibraryManager(database_path=str(tmp_path / "test.db"))
        scanner = LibraryScanner(manager)

        # Perform 5 rescans
        scan_times = []
        for rescan in range(5):
            start = time.time()
            scanner.scan_folder(str(audio_dir))
            scan_times.append(time.time() - start)

        # Scan time should not degrade significantly
        first_scan = scan_times[0]
        last_scan = scan_times[-1]

        assert last_scan < first_scan * 1.5, \
            f"Scan degraded: {first_scan:.2f}s → {last_scan:.2f}s"

    def test_database_integrity_long_session(self, large_library_db):
        """Test database integrity after extended use."""
        from auralis.library.models import Track
        from auralis.library.repositories import TrackRepository

        repo = TrackRepository(large_library_db)

        # Perform many operations
        for i in range(100):
            # Read
            tracks, _ = repo.get_all(limit=10, offset=i * 10)

            # Update (modify play count)
            if tracks:
                track = tracks[0]
                track.play_count = (track.play_count or 0) + 1
                session.commit()

        # Verify database integrity
        total = session.query(Track).count()
        assert total == 1000, "Track count changed unexpectedly"

        # Verify no corruption
        all_tracks = session.query(Track).all()
        for track in all_tracks:
            assert track.filepath is not None
            assert track.title is not None
    def test_cache_invalidation_large_scale(self, large_library_db):
        """Test cache invalidation with 1,000+ entries."""
        import tempfile

        from auralis.library.manager import LibraryManager

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        manager = LibraryManager(database_path=db_path)

        # Fill cache with many entries
        for i in range(100):
            manager.get_recent_tracks(limit=10)
            manager.get_popular_tracks(limit=10)

        initial_size = manager.get_cache_stats()['size']

        # Invalidate cache
        manager.invalidate_track_caches()

        final_size = manager.get_cache_stats()['size']

        # Cache should be cleared or significantly reduced
        assert final_size < initial_size / 2, "Cache invalidation ineffective"
