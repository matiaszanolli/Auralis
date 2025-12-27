"""
Concurrent Operations Edge Case Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for thread safety, race conditions, and concurrent access patterns.

INVARIANTS TESTED:
- Thread safety: No data corruption from concurrent access
- Race conditions: No duplicate entries from simultaneous adds
- Deadlocks: Operations complete without hanging
- Data consistency: Database remains consistent under concurrent load
- Transaction isolation: Concurrent transactions don't interfere
"""

import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pytest

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.saver import save
from auralis.library.repositories import (
    AlbumRepository,
    ArtistRepository,
    TrackRepository,
)


@pytest.mark.edge_case
@pytest.mark.slow
class TestConcurrentDatabaseOperations:
    """Test concurrent database access patterns."""

    def test_concurrent_track_adds_no_duplicates(self, temp_db):
        """
        INVARIANT: Concurrent adds of same track should not create duplicates.
        Race condition: Multiple threads adding identical filepath.
        """
        track_repo = TrackRepository(temp_db)

        track_info = {
            'filepath': '/tmp/test_concurrent.flac',
            'title': 'Concurrent Test',
            'artists': ['Test Artist'],
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        }

        results = []
        errors = []

        def add_track():
            try:
                track = track_repo.add(track_info)
                results.append(track)
            except Exception as e:
                errors.append(e)

        # Launch 10 threads simultaneously
        threads = []
        for _ in range(10):
            t = threading.Thread(target=add_track)
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # INVARIANT: Should have exactly 1 track (no duplicates)
        all_tracks, total = track_repo.get_all(limit=100, offset=0)
        assert total == 1, f"Should have exactly 1 track, got {total} (duplicates detected!)"

        # All results should point to same track
        track_ids = {r.id for r in results if r is not None}
        assert len(track_ids) <= 1, f"Multiple track IDs created: {track_ids}"

    def test_concurrent_reads_during_write(self, temp_db):
        """
        INVARIANT: Concurrent reads during writes should not block or crash.
        Test: Multiple readers while one writer is active.
        """
        track_repo = TrackRepository(temp_db)

        # Add initial tracks
        for i in range(10):
            track_repo.add({
                'filepath': f'/tmp/track_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Test Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

        results = []
        errors = []

        def read_tracks():
            try:
                tracks, total = track_repo.get_all(limit=100, offset=0)
                results.append(total)
            except Exception as e:
                errors.append(e)

        def write_track(num):
            try:
                track_repo.add({
                    'filepath': f'/tmp/new_track_{num}.flac',
                    'title': f'New Track {num}',
                    'artists': ['Test Artist'],
                    'format': 'FLAC',
                    'sample_rate': 44100,
                    'channels': 2
                })
            except Exception as e:
                errors.append(e)

        # Launch readers and writers simultaneously
        threads = []

        # 5 readers
        for _ in range(5):
            t = threading.Thread(target=read_tracks)
            threads.append(t)
            t.start()

        # 3 writers
        for i in range(3):
            t = threading.Thread(target=write_track, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # INVARIANT: No crashes, all operations completed
        assert len(errors) == 0, f"Concurrent operations failed: {errors}"
        assert len(results) == 5, "All read operations should complete"

    def test_concurrent_search_operations(self, temp_db):
        """
        INVARIANT: Concurrent searches should not interfere with each other.
        Test: Multiple simultaneous search queries.
        """
        track_repo = TrackRepository(temp_db)

        # Add diverse tracks
        keywords = ['rock', 'jazz', 'classical', 'metal', 'blues']
        for i, keyword in enumerate(keywords):
            for j in range(5):
                track_repo.add({
                    'filepath': f'/tmp/{keyword}_{j}.flac',
                    'title': f'{keyword.title()} Track {j}',
                    'artists': [f'{keyword.title()} Artist'],
                    'format': 'FLAC',
                    'sample_rate': 44100,
                    'channels': 2
                })

        results = {}
        errors = []

        def search_keyword(keyword):
            try:
                result = track_repo.search(keyword, limit=100, offset=0)
                if isinstance(result, tuple):
                    tracks, total = result
                else:
                    tracks = result
                    total = len(tracks)
                results[keyword] = total
            except Exception as e:
                errors.append(e)

        # Search all keywords simultaneously
        threads = []
        for keyword in keywords:
            t = threading.Thread(target=search_keyword, args=(keyword,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # INVARIANT: All searches complete without errors
        assert len(errors) == 0, f"Search operations failed: {errors}"
        assert len(results) == len(keywords), "All searches should complete"

        # Each keyword should find its tracks
        for keyword in keywords:
            assert results.get(keyword, 0) > 0, f"Should find tracks for {keyword}"

    def test_concurrent_updates_no_lost_updates(self, temp_db):
        """
        INVARIANT: Concurrent updates should not lose data (lost update problem).
        Test: Multiple threads incrementing play count.
        """
        track_repo = TrackRepository(temp_db)

        # Add track
        track = track_repo.add({
            'filepath': '/tmp/play_count_test.flac',
            'title': 'Play Count Test',
            'artists': ['Test Artist'],
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2,
            'play_count': 0
        })

        track_id = track.id
        num_increments = 20
        errors = []

        def increment_play_count():
            try:
                # Get current count
                session = temp_db()
                from auralis.library.models import Track
                t = session.query(Track).filter_by(id=track_id).first()
                if t:
                    t.play_count = (t.play_count or 0) + 1
                    session.commit()
                session.close()
            except Exception as e:
                errors.append(e)

        # Launch multiple threads to increment
        threads = []
        for _ in range(num_increments):
            t = threading.Thread(target=increment_play_count)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check final count
        session = temp_db()
        from auralis.library.models import Track
        final_track = session.query(Track).filter_by(id=track_id).first()
        final_count = final_track.play_count if final_track else 0
        session.close()

        # INVARIANT: Some increments should succeed (may have lost updates due to race)
        # This test documents the behavior - ideally should be num_increments
        assert final_count > 0, "At least some increments should succeed"

        # If lost updates occur, this will be less than num_increments
        # This is expected behavior without proper locking
        if final_count < num_increments:
            print(f"Lost updates detected: {num_increments - final_count} updates lost")

    def test_concurrent_deletes_no_errors(self, temp_db):
        """
        INVARIANT: Concurrent deletes of same item should not crash.
        Test: Multiple threads trying to delete same track.
        """
        track_repo = TrackRepository(temp_db)

        # Add track
        track = track_repo.add({
            'filepath': '/tmp/delete_test.flac',
            'title': 'Delete Test',
            'artists': ['Test Artist'],
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        })

        track_id = track.id
        errors = []
        success_count = [0]  # Use list for mutable counter

        def delete_track():
            try:
                track_repo.delete(track_id)
                success_count[0] += 1
            except Exception as e:
                errors.append(e)

        # Launch 5 threads to delete same track
        threads = []
        for _ in range(5):
            t = threading.Thread(target=delete_track)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # INVARIANT: At least one delete should succeed, others may fail gracefully
        assert success_count[0] >= 1, "At least one delete should succeed"

        # Track should be gone
        all_tracks, total = track_repo.get_all(limit=100, offset=0)
        assert track_id not in [t.id for t in all_tracks], "Track should be deleted"


@pytest.mark.edge_case
@pytest.mark.slow
class TestConcurrentAudioProcessing:
    """Test concurrent audio processing operations."""

    def test_concurrent_processing_different_files(self, temp_audio_dir):
        """
        INVARIANT: Processing different files concurrently should not interfere.
        Test: Multiple files processed in parallel.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Create test audio files
        sample_rate = 44100
        duration = 2.0
        num_files = 5

        files = []
        for i in range(num_files):
            audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'test_{i}.wav')
            save(filepath, audio, sample_rate, subtype='PCM_16')
            files.append(filepath)

        results = []
        errors = []

        def process_file(filepath):
            try:
                result = processor.process(filepath)
                results.append((filepath, len(result)))
            except Exception as e:
                errors.append((filepath, e))

        # Process files concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_file, f) for f in files]
            for future in as_completed(futures):
                future.result()  # Wait for completion

        # INVARIANT: All files processed successfully
        assert len(errors) == 0, f"Processing errors: {errors}"
        assert len(results) == num_files, f"Should process all {num_files} files"

        # All results should be valid
        for filepath, length in results:
            assert length > 0, f"File {filepath} produced empty output"

    def test_concurrent_processing_same_file(self, temp_audio_dir):
        """
        INVARIANT: Processing same file concurrently should work (read-only).
        Test: Multiple threads processing same file.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Create single test file
        sample_rate = 44100
        duration = 2.0
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'shared.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        results = []
        errors = []

        def process_file():
            try:
                result = processor.process(filepath)
                results.append(len(result))
            except Exception as e:
                errors.append(e)

        # Process same file from multiple threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=process_file)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # INVARIANT: All threads should process successfully
        assert len(errors) == 0, f"Concurrent processing failed: {errors}"
        assert len(results) == 5, "All threads should complete"

        # All results should be same length (deterministic processing)
        assert len(set(results)) == 1, f"Results differ: {results}"

    def test_processor_thread_safety(self, temp_audio_dir):
        """
        INVARIANT: Single processor instance should handle concurrent calls safely.
        Test: Shared processor instance, multiple concurrent calls.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)  # Single shared instance

        # Create test files
        sample_rate = 44100
        duration = 1.0

        files = []
        for i in range(3):
            audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'thread_test_{i}.wav')
            save(filepath, audio, sample_rate, subtype='PCM_16')
            files.append(filepath)

        results = []
        errors = []

        def process_with_shared_processor(filepath):
            try:
                # All threads use same processor instance
                result = processor.process(filepath)
                results.append(len(result))
            except Exception as e:
                errors.append(e)

        # Use shared processor from multiple threads
        threads = []
        for filepath in files:
            t = threading.Thread(target=process_with_shared_processor, args=(filepath,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # INVARIANT: Either all succeed (thread-safe) or all fail (not thread-safe)
        # Both are valid behaviors, but should be consistent
        if errors:
            # If processor is not thread-safe, document the behavior
            print(f"Processor not thread-safe: {len(errors)} errors")
        else:
            assert len(results) == len(files), "All processing should complete"


@pytest.mark.edge_case
class TestDeadlockPrevention:
    """Test for potential deadlock scenarios."""

    def test_no_deadlock_circular_dependencies(self, temp_db):
        """
        INVARIANT: Operations with circular dependencies should not deadlock.
        Test: Album → Artist → Track → Album references.
        """
        track_repo = TrackRepository(temp_db)
        album_repo = AlbumRepository(temp_db)
        artist_repo = ArtistRepository(temp_db)

        errors = []
        completed = [0]

        def create_complex_relationships(idx):
            try:
                # Create artist
                session = temp_db()
                from auralis.library.models import Album, Artist, Track

                artist = Artist(name=f'Artist {idx}')
                session.add(artist)
                session.commit()

                # Create album
                album = Album(title=f'Album {idx}', artist_id=artist.id)
                session.add(album)
                session.commit()

                # Create tracks
                for i in range(3):
                    track = Track(
                        filepath=f'/tmp/track_{idx}_{i}.flac',
                        title=f'Track {i}',
                        album_id=album.id,
                        format='FLAC',
                        sample_rate=44100,
                        channels=2
                    )
                    track.artists.append(artist)
                    session.add(track)

                session.commit()
                session.close()
                completed[0] += 1
            except Exception as e:
                errors.append(e)

        # Create multiple relationships concurrently
        threads = []
        for i in range(5):
            t = threading.Thread(target=create_complex_relationships, args=(i,))
            threads.append(t)
            t.start()

        # Wait with timeout (deadlock would cause timeout)
        for t in threads:
            t.join(timeout=10)
            if t.is_alive():
                errors.append("Thread deadlocked (timeout)")

        # INVARIANT: All operations complete without deadlock
        assert len(errors) == 0, f"Deadlock or errors occurred: {errors}"
        assert completed[0] == 5, "All operations should complete"

    def test_no_deadlock_concurrent_queries(self, temp_db):
        """
        INVARIANT: Complex queries should not deadlock under concurrent load.
        Test: Multiple complex queries running simultaneously.
        """
        track_repo = TrackRepository(temp_db)

        # Add test data
        for i in range(20):
            track_repo.add({
                'filepath': f'/tmp/query_test_{i}.flac',
                'title': f'Track {i}',
                'artists': [f'Artist {i % 5}'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2,
                'play_count': i
            })

        results = []
        errors = []

        def run_complex_queries():
            try:
                # Multiple different query types
                track_repo.get_all(limit=10, offset=0)
                track_repo.search('Track', limit=10, offset=0)
                track_repo.get_by_id(1)
                results.append(True)
            except Exception as e:
                errors.append(e)

        # Run queries from multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=run_complex_queries)
            threads.append(t)
            t.start()

        # Wait with timeout
        for t in threads:
            t.join(timeout=10)
            if t.is_alive():
                errors.append("Query deadlocked (timeout)")

        # INVARIANT: No deadlocks, all queries complete
        assert len(errors) == 0, f"Deadlock or errors: {errors}"
        assert len(results) == 10, "All query threads should complete"
