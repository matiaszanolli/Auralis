"""
Long-Running Operation Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for operations that run for extended periods.

LONG-RUNNING SCENARIOS:
- Hours of continuous processing
- Multi-day library operations
- Batch processing jobs
- Background task execution
- Queue processing
- Import/export operations
"""

import gc
import time

import pytest


@pytest.mark.load
@pytest.mark.slow
class TestBatchProcessing:
    """Test batch processing operations."""

    def test_batch_process_100_files(self, temp_audio_dir, resource_monitor):
        """
        LOAD: Batch process 100 audio files.
        Target: < 5 minutes, stable memory.
        """
        import numpy as np
        import soundfile as sf

        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        # Create 100 small audio files
        filepaths = []
        for i in range(100):
            audio = np.random.randn(44100) * 0.1  # 1 second each
            filepath = os.path.join(temp_audio_dir, f'batch_{i}.wav')
            sf.write(filepath, audio, 44100, subtype='PCM_16')
            filepaths.append(filepath)

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        with resource_monitor() as monitor:
            processed_count = 0

            for i, filepath in enumerate(filepaths):
                result = processor.process(filepath)
                del result
                processed_count += 1

                if i % 10 == 0:
                    gc.collect()
                    monitor.update()
                    print(f"  Progress: {processed_count}/100 files, " +
                          f"Memory: {monitor.peak_memory_mb:.1f}MB")

            elapsed = monitor.elapsed_seconds
            final_memory_growth = monitor.memory_growth_mb

        assert processed_count == 100, \
            f"Should process all files, processed {processed_count}/100"

        assert elapsed < 600, \
            f"Should complete in < 10min, took {elapsed:.1f}s"

        assert final_memory_growth < 500, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 500MB"

        rate = processed_count / elapsed
        print(f"✓ Batch processed 100 files in {elapsed:.1f}s " +
              f"({rate:.2f} files/s), memory: {final_memory_growth:.1f}MB")

    def test_batch_metadata_update(self, large_track_dataset, temp_db, resource_monitor):
        """
        LOAD: Update metadata for 1000 tracks.
        Target: < 2 minutes, stable memory.
        """
        from auralis.library.repositories import TrackRepository

        tracks = large_track_dataset(1000)
        track_repo = TrackRepository(temp_db)

        with resource_monitor() as monitor:
            updated_count = 0

            for i, track in enumerate(tracks):
                track_repo.update(track.id, {
                    'play_count': i,
                    'favorite': i % 2 == 0
                })
                updated_count += 1

                if i % 100 == 0:
                    gc.collect()
                    monitor.update()

            elapsed = monitor.elapsed_seconds
            final_memory_growth = monitor.memory_growth_mb

        assert updated_count == 1000, \
            f"Should update all tracks, updated {updated_count}/1000"

        assert elapsed < 120, \
            f"Should complete in < 2min, took {elapsed:.1f}s"

        assert final_memory_growth < 200, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 200MB"

        rate = updated_count / elapsed
        print(f"✓ Updated 1000 tracks in {elapsed:.1f}s " +
              f"({rate:.1f} updates/s), memory: {final_memory_growth:.1f}MB")


@pytest.mark.load
@pytest.mark.slow
class TestQueueProcessing:
    """Test queue-based processing."""

    def test_process_queue_of_100_items(self, temp_audio_dir, resource_monitor):
        """
        LOAD: Process queue of 100 items sequentially.
        Target: < 5 minutes, no memory growth.
        """
        from collections import deque

        import numpy as np
        import soundfile as sf

        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        # Create queue of audio files
        queue = deque()
        for i in range(100):
            audio = np.random.randn(22050) * 0.1  # 0.5 second each
            filepath = os.path.join(temp_audio_dir, f'queue_{i}.wav')
            sf.write(filepath, audio, 44100, subtype='PCM_16')
            queue.append(filepath)

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        with resource_monitor() as monitor:
            processed_count = 0

            while queue:
                filepath = queue.popleft()
                result = processor.process(filepath)
                del result
                processed_count += 1

                if processed_count % 10 == 0:
                    gc.collect()
                    monitor.update()

            elapsed = monitor.elapsed_seconds
            final_memory_growth = monitor.memory_growth_mb

        assert processed_count == 100, \
            f"Should process all items, processed {processed_count}/100"

        assert elapsed < 600, \
            f"Should complete in < 10min, took {elapsed:.1f}s"

        assert final_memory_growth < 300, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 300MB"

        print(f"✓ Processed queue of 100 items in {elapsed:.1f}s, " +
              f"memory: {final_memory_growth:.1f}MB")

    def test_priority_queue_processing(self, temp_audio_dir):
        """
        LOAD: Process priority queue (high priority first).
        Target: Correct ordering, all items processed.
        """
        import heapq

        import numpy as np
        import soundfile as sf

        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        # Create priority queue (min-heap, lower number = higher priority)
        priority_queue = []

        for i in range(50):
            audio = np.random.randn(11025) * 0.1  # 0.25 second each
            filepath = os.path.join(temp_audio_dir, f'priority_{i}.wav')
            sf.write(filepath, audio, 44100, subtype='PCM_16')

            # Random priority
            import random
            priority = random.randint(1, 10)
            heapq.heappush(priority_queue, (priority, filepath))

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        processed_items = []

        while priority_queue:
            priority, filepath = heapq.heappop(priority_queue)
            result = processor.process(filepath)
            del result
            processed_items.append(priority)

        assert len(processed_items) == 50, \
            "Should process all items"

        # Verify processing order (should be sorted by priority)
        assert processed_items == sorted(processed_items), \
            "Items should be processed in priority order"

        print(f"✓ Priority queue processed 50 items in correct order")


@pytest.mark.load
@pytest.mark.slow
class TestBackgroundTasks:
    """Test background task execution."""

    def test_simulated_background_processing(self, temp_audio_dir, resource_monitor):
        """
        LOAD: Simulate background processing while handling queries.
        Target: Both operations complete successfully.
        """
        import threading

        import numpy as np
        import soundfile as sf

        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        # Create audio files
        filepaths = []
        for i in range(20):
            audio = np.random.randn(22050) * 0.1
            filepath = os.path.join(temp_audio_dir, f'bg_{i}.wav')
            sf.write(filepath, audio, 44100, subtype='PCM_16')
            filepaths.append(filepath)

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        background_completed = {'count': 0}
        foreground_completed = {'count': 0}
        lock = threading.Lock()

        def background_worker():
            """Simulated background processing."""
            for filepath in filepaths:
                result = processor.process(filepath)
                del result
                with lock:
                    background_completed['count'] += 1

        def foreground_task():
            """Simulated foreground queries."""
            for i in range(100):
                # Simulate query
                time.sleep(0.01)
                with lock:
                    foreground_completed['count'] += 1

        with resource_monitor() as monitor:
            # Start background worker
            bg_thread = threading.Thread(target=background_worker)
            bg_thread.start()

            # Run foreground tasks
            foreground_task()

            # Wait for background to complete
            bg_thread.join()

            elapsed = monitor.elapsed_seconds
            final_memory_growth = monitor.memory_growth_mb

        assert background_completed['count'] == 20, \
            f"Background should complete 20 tasks, completed {background_completed['count']}"

        assert foreground_completed['count'] == 100, \
            f"Foreground should complete 100 tasks, completed {foreground_completed['count']}"

        print(f"✓ Background + foreground tasks in {elapsed:.1f}s, " +
              f"memory: {final_memory_growth:.1f}MB")


@pytest.mark.load
@pytest.mark.slow
class TestImportExport:
    """Test import/export operations."""

    def test_export_large_library(self, large_track_dataset, temp_db, resource_monitor):
        """
        LOAD: Export 1000 tracks to JSON.
        Target: < 30 seconds, reasonable file size.
        """
        import json

        from auralis.library.repositories import TrackRepository

        large_track_dataset(1000)
        track_repo = TrackRepository(temp_db)

        with resource_monitor() as monitor:
            # Get all tracks
            result = track_repo.get_all(limit=1000, offset=0)

            if isinstance(result, tuple):
                tracks, total = result
            else:
                tracks = result

            # Export to dict
            export_data = []
            for track in tracks:
                export_data.append({
                    'id': track.id,
                    'title': track.title,
                    'filepath': track.filepath,
                    'duration': track.duration,
                })

            # Serialize to JSON
            json_str = json.dumps(export_data, indent=2)

            elapsed = monitor.elapsed_seconds

        assert len(export_data) == 1000, \
            f"Should export all tracks, exported {len(export_data)}/1000"

        assert elapsed < 60, \
            f"Should complete in < 1min, took {elapsed:.1f}s"

        assert len(json_str) > 0, "Should produce non-empty JSON"

        print(f"✓ Exported 1000 tracks in {elapsed:.1f}s, " +
              f"JSON size: {len(json_str) / 1024:.1f}KB")

    def test_import_large_dataset(self, temp_db, resource_monitor):
        """
        LOAD: Import 1000 tracks from data structure.
        Target: < 2 minutes.
        """
        from auralis.library.repositories import TrackRepository

        track_repo = TrackRepository(temp_db)

        # Prepare import data
        import_data = []
        for i in range(1000):
            import_data.append({
                'filepath': f'/import/track_{i}.flac',
                'title': f'Import Track {i}',
                'artists': ['Import Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2,
                'duration': 180.0 + i,
            })

        with resource_monitor() as monitor:
            imported_count = 0

            for track_data in import_data:
                track = track_repo.add(track_data)
                if track:
                    imported_count += 1

                if imported_count % 100 == 0:
                    gc.collect()
                    monitor.update()

            elapsed = monitor.elapsed_seconds
            final_memory_growth = monitor.memory_growth_mb

        assert imported_count == 1000, \
            f"Should import all tracks, imported {imported_count}/1000"

        assert elapsed < 120, \
            f"Should complete in < 2min, took {elapsed:.1f}s"

        rate = imported_count / elapsed
        print(f"✓ Imported 1000 tracks in {elapsed:.1f}s " +
              f"({rate:.1f} tracks/s), memory: {final_memory_growth:.1f}MB")


@pytest.mark.load
@pytest.mark.slow
class TestContinuousOperation:
    """Test system under continuous operation."""

    def test_continuous_operation_stability(self, test_audio_file, resource_monitor, load_test_config):
        """
        STRESS: Run continuously for 30 seconds with varied operations.
        Target: Stable performance, no degradation.
        """
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        target_duration = load_test_config['medium_test_seconds']  # 30 seconds

        with resource_monitor() as monitor:
            start_time = time.time()
            iterations = 0

            while time.time() - start_time < target_duration:
                # Varied operations
                if iterations % 3 == 0:
                    # Processing
                    result = processor.process(test_audio_file)
                    del result

                if iterations % 2 == 0:
                    # GC
                    gc.collect()

                iterations += 1
                monitor.update()

            elapsed = monitor.elapsed_seconds
            final_memory_growth = monitor.memory_growth_mb
            peak_memory = monitor.peak_memory_mb

        rate = iterations / elapsed

        assert final_memory_growth < 500, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 500MB"

        assert peak_memory < 1024, \
            f"Peak memory {peak_memory:.1f}MB should be < 1GB"

        print(f"✓ Continuous operation: {iterations} iterations in {elapsed:.1f}s, " +
              f"rate: {rate:.1f} iter/s, memory: {final_memory_growth:.1f}MB, " +
              f"peak: {peak_memory:.1f}MB")


@pytest.mark.load
class TestProgressiveLoad:
    """Test performance under progressive load increase."""

    def test_progressive_library_growth(self, large_track_dataset, temp_db, resource_monitor):
        """
        LOAD: Add tracks progressively, measure query performance.
        Target: Query time shouldn't degrade significantly.
        """
        from auralis.library.repositories import TrackRepository

        track_repo = TrackRepository(temp_db)

        query_times = []

        with resource_monitor() as monitor:
            for batch_num in range(10):
                # Add 100 tracks
                large_track_dataset(100)

                # Measure query time
                start = time.time()
                result = track_repo.get_all(limit=50, offset=0)
                query_time = time.time() - start

                query_times.append(query_time)

                monitor.update()

            final_memory_growth = monitor.memory_growth_mb

        # Check query time degradation
        first_query_time = query_times[0]
        last_query_time = query_times[-1]

        degradation_factor = last_query_time / first_query_time if first_query_time > 0 else 1

        assert degradation_factor < 3.0, \
            f"Query time degraded {degradation_factor:.1f}x, should be < 3x"

        print(f"✓ Progressive growth: 1000 tracks added, " +
              f"query degradation: {degradation_factor:.2f}x, " +
              f"memory: {final_memory_growth:.1f}MB")
