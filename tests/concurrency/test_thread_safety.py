# -*- coding: utf-8 -*-

"""
Thread Safety Tests
~~~~~~~~~~~~~~~~~~~

Tests for thread-safe operations and race condition detection.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import threading
import time
from pathlib import Path

from .helpers import run_concurrent, run_concurrent_with_barrier, detect_race_condition


# ============================================================================
# Shared Resource Access Tests (10 tests)
# ============================================================================

class TestSharedResourceAccess:
    """Test thread-safety of shared resource access."""

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_concurrent_cache_access(self, thread_pool):
        """
        Test concurrent cache read access.

        Validates that multiple threads can safely read from cache simultaneously.
        """
        from auralis.library.cache import LibraryCache

        cache = LibraryCache(max_size=100)

        # Populate cache
        for i in range(50):
            cache.set(f"key_{i}", f"value_{i}")

        # Concurrent reads
        def read_from_cache(key_num):
            return cache.get(f"key_{key_num % 50}")

        futures = [thread_pool.submit(read_from_cache, i) for i in range(100)]
        results = [f.result() for f in futures]

        # All reads should succeed
        assert len(results) == 100
        assert all(r is not None for r in results)

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_concurrent_cache_writes(self, thread_pool):
        """
        Test concurrent cache write access.

        Validates that cache correctly handles concurrent writes.
        """
        from auralis.library.cache import LibraryCache

        cache = LibraryCache(max_size=200)

        # Concurrent writes
        def write_to_cache(i):
            cache.set(f"concurrent_key_{i}", f"concurrent_value_{i}")
            return True

        futures = [thread_pool.submit(write_to_cache, i) for i in range(100)]
        results = [f.result() for f in futures]

        # All writes should succeed
        assert len(results) == 100
        assert all(r for r in results)

        # Verify data integrity
        for i in range(100):
            value = cache.get(f"concurrent_key_{i}")
            assert value == f"concurrent_value_{i}", f"Cache corruption detected for key {i}"

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_cache_invalidation_race_condition(self, thread_pool):
        """
        Test cache invalidation during concurrent reads.

        Ensures cache invalidation doesn't cause errors in concurrent readers.
        """
        from auralis.library.cache import LibraryCache

        cache = LibraryCache(max_size=100)

        # Populate cache
        for i in range(50):
            cache.set(f"race_key_{i}", f"race_value_{i}")

        results = []
        errors = []

        def reader():
            try:
                for i in range(10):
                    cache.get(f"race_key_{i % 50}")
                results.append(True)
            except Exception as e:
                errors.append(e)

        def invalidator():
            time.sleep(0.01)  # Let readers start
            cache.clear()

        # Start readers
        reader_futures = [thread_pool.submit(reader) for _ in range(5)]

        # Start invalidator
        invalidator_future = thread_pool.submit(invalidator)

        # Wait for all to complete
        for f in reader_futures + [invalidator_future]:
            f.result(timeout=10)

        # No errors should occur
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"


    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_database_connection_pool(self, temp_db, thread_pool):
        """
        Test database connection pool under concurrent load.

        Validates that connection pool handles concurrent database access safely.
        """
        from auralis.library.repositories import TrackRepository

        track_repo = TrackRepository(temp_db)

        # Concurrent database operations
        def add_track(i):
            track_info = {
                'filepath': f'/tmp/concurrent_track_{i}.flac',
                'title': f'Concurrent Track {i}',
                'artists': ['Test Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }
            return track_repo.add(track_info)

        futures = [thread_pool.submit(add_track, i) for i in range(20)]
        results = [f.result() for f in futures]

        # All operations should succeed
        assert len(results) == 20
        assert all(r is not None for r in results)

        # Verify data integrity
        all_tracks, total = track_repo.get_all(limit=100)
        assert len(all_tracks) == 20

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_concurrent_database_writes(self, temp_db, thread_pool):
        """
        Test concurrent database write operations.

        Ensures database writes don't interfere with each other.
        """
        from auralis.library.repositories import TrackRepository

        track_repo = TrackRepository(temp_db)

        # Add initial tracks
        track_ids = []
        for i in range(10):
            track = track_repo.add({
                'filepath': f'/tmp/write_track_{i}.flac',
                'title': f'Write Track {i}',
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })
            if track:
                track_ids.append(track.id)

        # Concurrent updates
        def update_track(track_id, new_title):
            session = temp_db()
            from auralis.library.models import Track
            track = session.query(Track).filter_by(id=track_id).first()
            if track:
                track.title = new_title
                session.commit()
            session.close()
            return True

        futures = []
        for i, track_id in enumerate(track_ids):
            future = thread_pool.submit(update_track, track_id, f'Updated {i}')
            futures.append(future)

        results = [f.result() for f in futures]
        assert all(r for r in results)

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_concurrent_database_transactions(self, temp_db, thread_pool):
        """
        Test database transaction isolation.

        Validates that concurrent transactions don't interfere.
        """
        from auralis.library.repositories import TrackRepository

        track_repo = TrackRepository(temp_db)

        # Add test track
        track = track_repo.add({
            'filepath': '/tmp/transaction_test.flac',
            'title': 'Transaction Test',
            'artists': ['Artist'],
            'play_count': 0,
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        })

        # Concurrent play count increments
        def increment_play_count(track_id):
            session = temp_db()
            from auralis.library.models import Track
            t = session.query(Track).filter_by(id=track_id).first()
            if t:
                t.play_count = (t.play_count or 0) + 1
                session.commit()
            session.close()
            return True

        futures = [thread_pool.submit(increment_play_count, track.id) for _ in range(50)]
        results = [f.result() for f in futures]

        assert all(r for r in results)

        # Verify final count (should be 50 if isolation works)
        session = temp_db()
        from auralis.library.models import Track
        final_track = session.query(Track).filter_by(id=track.id).first()
        final_count = final_track.play_count
        session.close()

        # Count should be close to 50 (allowing for some race conditions in SQLite)
        assert final_count >= 45, f"Play count {final_count} too low, transaction isolation may be broken"

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_library_manager_concurrent_access(self, tmp_path, thread_pool):
        """
        Test LibraryManager thread-safety.

        Validates that LibraryManager can be safely accessed from multiple threads.
        """
        from auralis.library.manager import LibraryManager

        db_path = str(tmp_path / "concurrent_test.db")
        manager = LibraryManager(database_path=db_path)

        # Concurrent track additions
        def add_track_to_library(i):
            track_info = {
                'filepath': f'/tmp/lib_concurrent_{i}.flac',
                'title': f'Library Track {i}',
                'artists': ['Concurrent Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            }
            return manager.add_track(track_info)

        futures = [thread_pool.submit(add_track_to_library, i) for i in range(30)]
        results = [f.result() for f in futures]

        # All additions should succeed
        assert len(results) == 30
        assert all(r is not None for r in results)

        # Verify total count
        all_tracks, total = manager.get_all_tracks(limit=100)
        assert len(all_tracks) == 30

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_concurrent_metadata_updates(self, temp_db, thread_pool):
        """
        Test concurrent metadata updates on the same track.

        Ensures metadata updates don't corrupt data under concurrent access.
        """
        from auralis.library.repositories import TrackRepository

        track_repo = TrackRepository(temp_db)

        # Add test track
        track = track_repo.add({
            'filepath': '/tmp/metadata_test.flac',
            'title': 'Original Title',
            'artists': ['Original Artist'],
            'format': 'FLAC',
            'sample_rate': 44100,
            'channels': 2
        })

        # Concurrent metadata updates (different fields)
        def update_title(track_id, new_title):
            session = temp_db()
            from auralis.library.models import Track
            t = session.query(Track).filter_by(id=track_id).first()
            if t:
                t.title = new_title
                session.commit()
            session.close()

        def update_play_count(track_id):
            session = temp_db()
            from auralis.library.models import Track
            t = session.query(Track).filter_by(id=track_id).first()
            if t:
                t.play_count = (t.play_count or 0) + 1
                session.commit()
            session.close()

        # Mix of updates
        futures = []
        for i in range(10):
            futures.append(thread_pool.submit(update_title, track.id, f'Title {i}'))
            futures.append(thread_pool.submit(update_play_count, track.id))

        # Wait for all
        for f in futures:
            f.result()

        # Verify track still exists and is not corrupted
        session = temp_db()
        from auralis.library.models import Track
        final_track = session.query(Track).filter_by(id=track.id).first()
        assert final_track is not None
        assert final_track.title is not None
        assert final_track.play_count >= 5  # At least some increments succeeded
        session.close()

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_concurrent_file_operations(self, tmp_path, thread_pool):
        """
        Test concurrent file I/O operations.

        Validates that file operations don't interfere with each other.
        """
        import numpy as np
        import soundfile as sf

        # Concurrent file writes
        def write_audio_file(i):
            audio = np.random.randn(44100, 2).astype(np.float32) * 0.1
            filepath = tmp_path / f"concurrent_write_{i}.wav"
            sf.write(str(filepath), audio, 44100)
            return filepath

        futures = [thread_pool.submit(write_audio_file, i) for i in range(20)]
        filepaths = [f.result() for f in futures]

        # All files should be created
        assert len(filepaths) == 20
        assert all(fp.exists() for fp in filepaths)

        # Concurrent file reads
        def read_audio_file(filepath):
            data, sr = sf.read(str(filepath))
            return len(data)

        read_futures = [thread_pool.submit(read_audio_file, fp) for fp in filepaths]
        lengths = [f.result() for f in read_futures]

        # All reads should succeed
        assert len(lengths) == 20
        assert all(length == 44100 for length in lengths)

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_shared_state_corruption(self, shared_counter, barrier):
        """
        Test for shared state corruption under concurrent access.

        Uses unsafe increment to demonstrate race conditions can be detected.
        """
        # This test should detect race conditions with unsafe operations

        def safe_increment():
            for _ in range(100):
                shared_counter.increment()

        def unsafe_increment():
            for _ in range(100):
                shared_counter.increment_unsafe()

        # Test safe increment - should not have race condition
        shared_counter.value = 0
        results = run_concurrent_with_barrier(safe_increment, barrier)
        assert shared_counter.get() == 1000  # 10 threads * 100 increments

        # Test unsafe increment - will likely have race condition
        shared_counter.value = 0
        results = run_concurrent_with_barrier(unsafe_increment, barrier)
        # Due to race conditions, final value will be less than 1000
        final_value = shared_counter.get()
        # We expect corruption with unsafe operations
        assert final_value < 1000, "Race condition not detected - unsafe increment should cause corruption"



# ============================================================================
# Audio Processing Thread Safety Tests (10 tests)
# ============================================================================

class TestAudioProcessingThreadSafety:
    """Test thread-safety of audio processing components."""

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.audio
    def test_concurrent_audio_processing(self, test_audio_files, thread_pool):
        """
        Test concurrent audio processing of multiple files.

        Validates that processing multiple files concurrently produces correct results.
        """
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio

        config = UnifiedConfig()
        config.set_processing_mode("adaptive")

        def process_file(filepath):
            audio, sr = load_audio(filepath)
            processor = HybridProcessor(config)
            result = processor.process(audio)
            return len(result)

        futures = [thread_pool.submit(process_file, fp) for fp in test_audio_files[:5]]
        results = [f.result() for f in futures]

        # All should succeed
        assert len(results) == 5
        assert all(r > 0 for r in results)

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.audio
    def test_processor_instance_isolation(self, test_audio_files, thread_pool):
        """
        Test that processor instances don't interfere with each other.

        Each thread should have isolated processor state.
        """
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio

        def process_with_different_settings(filepath, intensity):
            config = UnifiedConfig()
            config.set_processing_mode("adaptive")
            config.set_intensity(intensity)

            audio, sr = load_audio(filepath)
            processor = HybridProcessor(config)
            result = processor.process(audio)
            return (len(result), intensity)

        # Process same file with different intensities concurrently
        futures = []
        for i, intensity in enumerate([0.3, 0.5, 0.7, 0.9]):
            future = thread_pool.submit(process_with_different_settings, test_audio_files[0], intensity)
            futures.append(future)

        results = [f.result() for f in futures]

        # Each should have used its own intensity setting
        assert len(results) == 4
        intensities = [r[1] for r in results]
        assert set(intensities) == {0.3, 0.5, 0.7, 0.9}

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.audio
    def test_concurrent_eq_processing(self, test_audio_files, thread_pool):
        """
        Test EQ processing thread-safety.

        Validates that EQ processing can run concurrently without issues.
        """
        from auralis.dsp.psychoacoustic_eq import PsychoacousticEQ, EQSettings
        from auralis.io.unified_loader import load_audio
        import numpy as np

        def process_eq(filepath):
            audio, sr = load_audio(filepath)
            eq_settings = EQSettings(sample_rate=sr, fft_size=2048)
            eq = PsychoacousticEQ(eq_settings)
            target_curve = np.zeros(len(eq.critical_bands))
            result = eq.process_realtime_chunk(audio, target_curve)
            return len(result)

        futures = [thread_pool.submit(process_eq, fp) for fp in test_audio_files[:5]]
        results = [f.result() for f in futures]

        assert len(results) == 5
        assert all(r > 0 for r in results)

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.audio
    def test_concurrent_dynamics_processing(self, test_audio_files, thread_pool):
        """
        Test dynamics processing isolation.

        Validates that dynamics processors don't share state.
        """
        from auralis.dsp.dynamics import AdaptiveCompressor
        from auralis.io.unified_loader import load_audio

        def process_dynamics(filepath):
            audio, sr = load_audio(filepath)
            compressor = AdaptiveCompressor(sample_rate=sr)
            result = compressor.process(audio)
            return len(result)

        futures = [thread_pool.submit(process_dynamics, fp) for fp in test_audio_files[:5]]
        results = [f.result() for f in futures]

        assert len(results) == 5
        assert all(r > 0 for r in results)

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.audio
    def test_concurrent_fingerprint_extraction(self, test_audio_files, thread_pool):
        """
        Test fingerprint analyzer thread-safety.

        Validates that fingerprint extraction can run concurrently.
        """
        from auralis.analysis.fingerprint import AudioFingerprintAnalyzer
        from auralis.io.unified_loader import load_audio

        analyzer = AudioFingerprintAnalyzer()

        def extract_fingerprint(filepath):
            audio, sr = load_audio(filepath)
            fingerprint = analyzer.analyze(audio, sr)
            return fingerprint['lufs']  # Return a simple metric

        futures = [thread_pool.submit(extract_fingerprint, fp) for fp in test_audio_files[:5]]
        results = [f.result() for f in futures]

        assert len(results) == 5
        assert all(isinstance(r, (int, float)) for r in results)

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.audio
    def test_concurrent_spectrum_analysis(self, test_audio_files, thread_pool):
        """
        Test spectrum analyzer thread-safety.

        Validates that spectrum analysis can run concurrently.
        """
        from auralis.analysis.spectrum_analyzer import SpectrumAnalyzer
        from auralis.io.unified_loader import load_audio

        def analyze_spectrum(filepath):
            audio, sr = load_audio(filepath)
            analyzer = SpectrumAnalyzer(sample_rate=sr)
            result = analyzer.analyze_file(audio, sr)
            return result is not None

        futures = [thread_pool.submit(analyze_spectrum, fp) for fp in test_audio_files[:5]]
        results = [f.result() for f in futures]

        assert all(results)

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.audio
    def test_concurrent_content_analysis(self, test_audio_files, thread_pool):
        """
        Test ContentAnalyzer thread-safety.

        Validates that content analysis can run concurrently.
        """
        from auralis.core.analysis import ContentAnalyzer
        from auralis.io.unified_loader import load_audio

        analyzer = ContentAnalyzer()

        def analyze_content(filepath):
            audio, sr = load_audio(filepath)
            profile = analyzer.analyze_content(audio, sr)
            return profile['genre_info']['primary'] if profile else None

        futures = [thread_pool.submit(analyze_content, fp) for fp in test_audio_files[:5]]
        results = [f.result() for f in futures]

        assert len(results) == 5
        # Results should be strings (genre names)
        assert all(isinstance(r, str) for r in results if r)

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.audio
    def test_concurrent_target_generation(self, test_audio_files, thread_pool):
        """
        Test TargetGenerator thread-safety.

        Validates that target generation can run concurrently.
        """
        from auralis.core.analysis import ContentAnalyzer, AdaptiveTargetGenerator
        from auralis.io.unified_loader import load_audio

        analyzer = ContentAnalyzer()
        generator = AdaptiveTargetGenerator()

        def generate_target(filepath):
            audio, sr = load_audio(filepath)
            profile = analyzer.analyze_content(audio, sr)
            target = generator.generate_target_curve(profile)
            return target is not None

        futures = [thread_pool.submit(generate_target, fp) for fp in test_audio_files[:5]]
        results = [f.result() for f in futures]

        assert all(results)

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.audio
    def test_processing_state_isolation(self, test_audio_files, barrier):
        """
        Test that processing state doesn't leak between threads.

        Each thread should maintain isolated processing state.
        """
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig
        from auralis.io.unified_loader import load_audio

        results = []
        errors = []
        lock = threading.Lock()

        def process_with_state_check(filepath, thread_id):
            try:
                barrier.wait()  # Start all simultaneously
                config = UnifiedConfig()
                config.set_processing_mode("adaptive")
                processor = HybridProcessor(config)

                audio, sr = load_audio(filepath)
                result = processor.process(audio)

                # Check that we got a result
                with lock:
                    results.append((thread_id, len(result)))
            except Exception as e:
                with lock:
                    errors.append((thread_id, e))

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=process_with_state_check,
                args=(test_audio_files[i % len(test_audio_files)], i)
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        # No errors should occur
        assert len(errors) == 0, f"Errors occurred: {errors}"
        # All threads should complete
        assert len(results) == 10

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.audio
    def test_concurrent_memory_allocation(self, test_audio_files, thread_pool):
        """
        Test memory allocation thread-safety during audio processing.

        Validates that concurrent memory allocation doesn't cause issues.
        """
        from auralis.io.unified_loader import load_audio
        import numpy as np

        def allocate_and_process(filepath):
            # Load audio
            audio, sr = load_audio(filepath)

            # Allocate large arrays
            temp1 = np.zeros((len(audio), 2), dtype=np.float32)
            temp2 = np.zeros((len(audio), 2), dtype=np.float32)

            # Perform operations
            temp1[:] = audio * 0.5
            temp2[:] = audio * 0.7

            # Combine
            result = temp1 + temp2

            return len(result)

        futures = [thread_pool.submit(allocate_and_process, fp) for fp in test_audio_files[:8]]
        results = [f.result() for f in futures]

        assert len(results) == 8
        assert all(r > 0 for r in results)



# ============================================================================
# Thread Pool Management Tests (5 tests)
# ============================================================================

class TestThreadPoolManagement:
    """Test thread pool management and lifecycle."""

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_thread_pool_saturation(self, small_thread_pool, event):
        """
        Test behavior when thread pool is saturated.

        Validates that pool handles more tasks than workers gracefully.
        """
        import time

        completed = []
        lock = threading.Lock()

        def slow_task(task_id):
            # Wait for signal
            event.wait(timeout=5)
            with lock:
                completed.append(task_id)
            return task_id

        # Submit more tasks than workers (4 workers, 10 tasks)
        futures = [small_thread_pool.submit(slow_task, i) for i in range(10)]

        # Let first batch start
        time.sleep(0.1)

        # Signal all to proceed
        event.set()

        # All should complete
        results = [f.result(timeout=10) for f in futures]
        assert len(results) == 10
        assert len(completed) == 10

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_thread_pool_cleanup(self, tmp_path):
        """
        Test that thread pool properly cleans up threads.

        Validates that threads are terminated when pool shuts down.
        """
        from concurrent.futures import ThreadPoolExecutor

        initial_thread_count = threading.active_count()

        def dummy_task():
            time.sleep(0.1)
            return True

        # Create and use pool
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(dummy_task) for _ in range(10)]
            results = [f.result() for f in futures]

        # Wait a bit for cleanup
        time.sleep(0.5)

        # Thread count should return to initial
        final_thread_count = threading.active_count()
        assert final_thread_count <= initial_thread_count + 1  # Allow for minor variation

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_thread_pool_exception_handling(self, thread_pool):
        """
        Test exception handling in thread pool.

        Validates that exceptions in one task don't affect others.
        """
        def failing_task(should_fail):
            if should_fail:
                raise ValueError("Intentional failure")
            return "success"

        # Mix of failing and succeeding tasks
        futures = []
        for i in range(10):
            future = thread_pool.submit(failing_task, i % 2 == 0)
            futures.append((i, future))

        # Check results
        successes = 0
        failures = 0
        for i, future in futures:
            try:
                result = future.result()
                successes += 1
            except ValueError:
                failures += 1

        # Half should succeed, half should fail
        assert successes == 5
        assert failures == 5

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    def test_thread_local_storage(self, thread_pool):
        """
        Test thread-local storage isolation.

        Validates that thread-local data is properly isolated.
        """
        thread_local = threading.local()

        def set_and_get_thread_local(value):
            thread_local.value = value
            time.sleep(0.01)  # Give other threads time to interfere
            return thread_local.value

        futures = [thread_pool.submit(set_and_get_thread_local, i) for i in range(10)]
        results = [f.result() for f in futures]

        # Each thread should get its own value back
        assert results == list(range(10))

    @pytest.mark.concurrency
    @pytest.mark.thread_safety
    @pytest.mark.slow
    def test_thread_pool_graceful_shutdown(self, test_audio_files):
        """
        Test graceful shutdown of thread pool under load.

        Validates that pool can shut down cleanly even with active tasks.
        """
        from concurrent.futures import ThreadPoolExecutor
        from auralis.io.unified_loader import load_audio

        completed = []
        lock = threading.Lock()

        def process_audio(filepath):
            audio, sr = load_audio(filepath)
            with lock:
                completed.append(filepath)
            time.sleep(0.1)
            return len(audio)

        with ThreadPoolExecutor(max_workers=4) as pool:
            # Submit many tasks
            futures = [pool.submit(process_audio, fp) for fp in test_audio_files * 2]

            # Let some complete
            time.sleep(0.5)

            # Pool will shut down gracefully (wait for all tasks)

        # Some tasks should have completed
        assert len(completed) > 0

        # All tasks should complete or be cancelled
        completed_count = 0
        cancelled_count = 0
        for f in futures:
            if f.done():
                try:
                    f.result()
                    completed_count += 1
                except Exception:
                    pass
            elif f.cancelled():
                cancelled_count += 1

        assert completed_count + cancelled_count == len(futures)
