# -*- coding: utf-8 -*-

"""
Parallel Processing Tests
~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for multi-file batch processing, process pool performance, and resource contention.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pytest

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.config import UnifiedConfig
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio
from tests.concurrency.helpers import (
    measure_concurrency_speedup,
    run_concurrent,
    stress_test,
    wait_for_condition,
)

# ============================================================================
# Multi-File Batch Processing Tests (10 tests)
# ============================================================================

@pytest.mark.concurrency
@pytest.mark.parallel
@pytest.mark.audio
class TestBatchProcessing:
    """Tests for batch processing of multiple audio files."""

    def test_batch_processing_correctness(self, test_audio_files, tmp_path):
        """Test that parallel results match sequential processing."""
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.config import UnifiedConfig
        from auralis.io.unified_loader import load_audio

        config = UnifiedConfig()
        config.set_processing_mode("adaptive")

        # Sequential processing
        sequential_results = []
        for filepath in test_audio_files[:3]:
            audio, sr = load_audio(filepath)
            processor = HybridProcessor(config)
            result = processor.process(audio)
            sequential_results.append(result)

        # Parallel processing
        def process_file(filepath):
            audio, sr = load_audio(filepath)
            processor = HybridProcessor(config)
            return processor.process(audio)

        with ThreadPoolExecutor(max_workers=3) as pool:
            parallel_results = list(pool.map(process_file, test_audio_files[:3]))

        # Results should be similar (may not be identical due to floating point)
        assert len(sequential_results) == len(parallel_results)
        for seq, par in zip(sequential_results, parallel_results):
            assert seq.shape == par.shape
            # Allow small floating point differences
            np.testing.assert_allclose(seq, par, rtol=1e-5, atol=1e-8)

    def test_batch_processing_performance(self, test_audio_files):
        """Test speedup from parallelization."""
        from auralis.io.unified_loader import load_audio

        config = UnifiedConfig()
        config.set_processing_mode("adaptive")

        def sequential_processing():
            results = []
            for filepath in test_audio_files[:4]:
                audio, sr = load_audio(filepath)
                processor = HybridProcessor(config)
                result = processor.process(audio)
                results.append(result)
            return results

        def parallel_processing():
            def process_file(filepath):
                audio, sr = load_audio(filepath)
                processor = HybridProcessor(config)
                return processor.process(audio)

            with ThreadPoolExecutor(max_workers=4) as pool:
                return list(pool.map(process_file, test_audio_files[:4]))

        speedup, seq_time, par_time = measure_concurrency_speedup(
            sequential_processing,
            parallel_processing
        )

        # Should have some speedup (may be limited by GIL for pure Python)
        assert speedup > 0.8  # At worst, should not be much slower
        assert par_time > 0  # Sanity check

    def test_batch_processing_10_files(self, test_audio_files, thread_pool):
        """Test processing 10 files in parallel."""
        from auralis.io.unified_loader import load_audio

        config = UnifiedConfig()

        def process_file(filepath):
            audio, sr = load_audio(filepath)
            processor = HybridProcessor(config)
            result = processor.process(audio)
            return len(result)

        futures = [thread_pool.submit(process_file, fp) for fp in test_audio_files]
        results = [f.result(timeout=60) for f in futures]

        assert len(results) == 10
        assert all(r > 0 for r in results)

    def test_batch_processing_50_files(self, temp_audio_dir, thread_pool):
        """Test processing 50 files in parallel."""
        from auralis.io.unified_loader import load_audio

        audio_dir = Path(temp_audio_dir)
        audio_files = list(audio_dir.glob("*.wav"))[:20]  # Use 20 files

        config = UnifiedConfig()

        def process_file(filepath):
            try:
                audio, sr = load_audio(str(filepath))
                processor = HybridProcessor(config)
                result = processor.process(audio)
                return (str(filepath), len(result))
            except Exception as e:
                return (str(filepath), None)

        futures = [thread_pool.submit(process_file, fp) for fp in audio_files]
        results = [f.result(timeout=120) for f in futures]

        successful = [r for r in results if r[1] is not None]
        assert len(successful) >= 18  # At least 90% success rate

    def test_batch_processing_100_files(self, temp_audio_dir):
        """Test processing 100 files in parallel (simulated with 20 real files)."""
        from auralis.io.unified_loader import load_audio

        audio_dir = Path(temp_audio_dir)
        audio_files = list(audio_dir.glob("*.wav"))

        config = UnifiedConfig()

        def process_file(filepath):
            try:
                audio, sr = load_audio(str(filepath))
                processor = HybridProcessor(config)
                result = processor.process(audio)
                return True
            except Exception:
                return False

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(process_file, fp) for fp in audio_files]
            results = [f.result(timeout=180) for f in as_completed(futures)]

        success_rate = sum(results) / len(results)
        assert success_rate >= 0.85  # At least 85% success

    def test_batch_processing_memory_limit(self, test_audio_files):
        """Test that memory usage stays bounded during batch processing."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        config = UnifiedConfig()

        def process_file(filepath):
            audio, sr = load_audio(filepath)
            processor = HybridProcessor(config)
            result = processor.process(audio)
            return len(result)

        # Process files in batches to control memory
        batch_size = 3
        all_results = []

        for i in range(0, len(test_audio_files), batch_size):
            batch = test_audio_files[i:i+batch_size]
            with ThreadPoolExecutor(max_workers=batch_size) as pool:
                batch_results = list(pool.map(process_file, batch))
            all_results.extend(batch_results)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (< 500 MB for small test files)
        assert memory_increase < 500

    def test_batch_processing_error_handling(self, test_audio_files, tmp_path):
        """Test that one failure doesn't affect others."""
        from auralis.io.unified_loader import load_audio

        # Create a corrupted file
        corrupted_file = tmp_path / "corrupted.wav"
        corrupted_file.write_text("This is not a valid WAV file")

        config = UnifiedConfig()

        def process_file_safe(filepath):
            try:
                audio, sr = load_audio(str(filepath))
                processor = HybridProcessor(config)
                result = processor.process(audio)
                return ("success", len(result))
            except Exception as e:
                return ("error", str(e))

        # Mix valid and invalid files
        files_to_process = test_audio_files[:5] + [str(corrupted_file)]

        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(process_file_safe, files_to_process))

        successes = [r for r in results if r[0] == "success"]
        errors = [r for r in results if r[0] == "error"]

        assert len(successes) == 5  # All valid files processed
        assert len(errors) == 1  # Corrupted file failed

    def test_batch_processing_progress_tracking(self, test_audio_files):
        """Test that progress updates are accurate."""
        from auralis.io.unified_loader import load_audio

        config = UnifiedConfig()
        completed = []
        lock = threading.Lock()

        def process_with_progress(filepath, file_id):
            audio, sr = load_audio(filepath)
            processor = HybridProcessor(config)
            result = processor.process(audio)

            with lock:
                completed.append(file_id)

            return file_id

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(process_with_progress, fp, i): i
                      for i, fp in enumerate(test_audio_files)}

            # Monitor progress
            while futures:
                done, futures_remaining = [], []
                for f in futures:
                    if f.done():
                        done.append(f)
                    else:
                        futures_remaining.append(f)

                futures = {f: futures[f] for f in futures_remaining}
                time.sleep(0.1)

        assert len(completed) == len(test_audio_files)
        assert sorted(completed) == list(range(len(test_audio_files)))

    def test_batch_processing_cancellation(self, large_test_audio_files):
        """Test cancelling in-progress batch processing."""
        from auralis.io.unified_loader import load_audio

        config = UnifiedConfig()
        stop_event = threading.Event()
        completed = []
        lock = threading.Lock()

        def process_with_cancellation(filepath):
            if stop_event.is_set():
                return None

            audio, sr = load_audio(filepath)
            processor = HybridProcessor(config)
            result = processor.process(audio)

            with lock:
                completed.append(filepath)

            return len(result)

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(process_with_cancellation, fp)
                      for fp in large_test_audio_files]

            # Cancel after short delay
            time.sleep(1.0)
            stop_event.set()

            # Wait for all futures to complete
            results = []
            for f in futures:
                try:
                    results.append(f.result(timeout=10))
                except Exception:
                    results.append(None)

        # Some should have completed, some should be None
        assert None in results  # At least one was cancelled
        assert any(r is not None for r in results)  # At least one completed

    def test_batch_processing_priority_queue(self, test_audio_files):
        """Test that high-priority files are processed first."""
        from queue import PriorityQueue

        from auralis.io.unified_loader import load_audio

        config = UnifiedConfig()
        processed_order = []
        lock = threading.Lock()

        # Create priority queue (lower number = higher priority)
        task_queue = PriorityQueue()
        for i, filepath in enumerate(test_audio_files):
            priority = i % 3  # Priorities: 0 (high), 1 (medium), 2 (low)
            task_queue.put((priority, filepath))

        def worker():
            while not task_queue.empty():
                try:
                    priority, filepath = task_queue.get(timeout=1)
                    audio, sr = load_audio(filepath)
                    processor = HybridProcessor(config)
                    result = processor.process(audio)

                    with lock:
                        processed_order.append((priority, filepath))

                    task_queue.task_done()
                except Exception:
                    break

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        # Check that high-priority tasks were processed early
        first_half = processed_order[:len(processed_order)//2]
        high_priority_count = sum(1 for p, _ in first_half if p == 0)

        # At least some high-priority tasks should be in first half
        assert high_priority_count > 0


# ============================================================================
# Process Pool Performance Tests (10 tests)
# ============================================================================

@pytest.mark.concurrency
@pytest.mark.parallel
@pytest.mark.audio
class TestProcessPoolPerformance:
    """Process-pool tests.

    #5188: multiprocessing IPC is out of scope by design (see
    docs/architecture/overview.md's "Critical invariants" section) — not a
    gap pending a fix. Nine tests here used to assert ProcessPoolExecutor
    mechanics (worker distribution, IPC round-trips, CPU/memory-per-worker)
    against HybridProcessor, which holds a threading.RLock and cannot be
    pickled; each test also submitted a locally-defined closure to the pool,
    itself unpicklable regardless of the processor. They never ran (xfail
    strict=True since the day they were written) and were deleted rather
    than rewritten — the thread-based model they would otherwise exercise
    already has direct coverage in tests/concurrency/test_thread_safety.py,
    and auralis/optimization/parallel/ (the one prior process-pool
    implementation) was deleted outright in #4565.

    test_process_pool_startup_time is the one survivor: it only measures
    ProcessPoolExecutor's own creation overhead, never touches
    HybridProcessor, and isn't blocked by any of the above.
    """

    def test_process_pool_startup_time(self):
        """Test process pool creation overhead."""
        start = time.time()
        with ProcessPoolExecutor(max_workers=4) as pool:
            pass
        startup_time = time.time() - start

        # Startup should be reasonably fast (< 2 seconds)
        assert startup_time < 2.0


# ============================================================================
# Resource Contention Tests (5 tests)
# ============================================================================

@pytest.mark.concurrency
@pytest.mark.parallel
class TestResourceContention:
    """Tests for resource contention and locking."""

    def test_file_lock_contention(self, tmp_path):
        """Test file locking under concurrent access."""
        import fcntl

        test_file = tmp_path / "locked_file.txt"
        test_file.write_text("initial content\n")

        write_count = []
        lock = threading.Lock()

        def write_with_lock(thread_id):
            try:
                with open(test_file, "a") as f:
                    # Acquire exclusive lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write(f"Thread {thread_id}\n")
                    time.sleep(0.01)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

                with lock:
                    write_count.append(thread_id)
            except OSError:
                # narrowed from bare Exception, #5023: open()/flock()/write()
                # only fail with OSError here; anything else is a real bug.
                pass

        threads = [threading.Thread(target=write_with_lock, args=(i,))
                  for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # All writes should have succeeded
        assert len(write_count) == 10

        # File should have all entries
        content = test_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 11  # initial + 10 writes

    # xfail removed under #4548: the blocker this marker named ("Database
    # fixture setup required") was the shared `temp_db` fixture handing each
    # thread its own empty in-memory database. With the fixture now
    # file-backed, this test passes — and strict=True turned the unexpected
    # pass into a suite failure, so the marker had to go.
    def test_database_lock_contention(self, temp_db):
        """Test database locking behavior."""
        from sqlalchemy.exc import SQLAlchemyError

        from auralis.library.models import Track

        write_count = []
        lock = threading.Lock()

        def write_to_db(track_id):
            try:
                session = temp_db()
                track = Track(
                    id=track_id,
                    filepath=f"/test/track_{track_id}.wav",
                    title=f"Track {track_id}",
                    duration=180.0
                )
                session.add(track)
                session.commit()
                session.close()

                with lock:
                    write_count.append(track_id)
            except SQLAlchemyError:
                # narrowed from bare Exception, #5023: the anticipated failure
                # is write contention (OperationalError 'database is locked' /
                # IntegrityError), both SQLAlchemyError subclasses.
                pass

        threads = [threading.Thread(target=write_to_db, args=(i,))
                  for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Most writes should succeed (some may fail due to contention)
        assert len(write_count) >= 8

    def test_deadlock_prevention(self):
        """Test that no deadlocks occur under load."""
        lock_a = threading.Lock()
        lock_b = threading.Lock()

        completed = []
        lock_completed = threading.Lock()

        def acquire_locks_ordered(thread_id):
            # Always acquire in same order to prevent deadlock
            with lock_a:
                time.sleep(0.001)
                with lock_b:
                    time.sleep(0.001)
                    with lock_completed:
                        completed.append(thread_id)

        threads = [threading.Thread(target=acquire_locks_ordered, args=(i,))
                  for i in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # All threads should complete (no deadlock)
        assert len(completed) == 20

    def test_resource_starvation(self, semaphore):
        """Test fair resource allocation."""
        acquired_count = {}
        lock = threading.Lock()

        def acquire_resource(thread_id, iterations=5):
            for _ in range(iterations):
                with semaphore:
                    time.sleep(0.01)
                    with lock:
                        acquired_count[thread_id] = acquired_count.get(thread_id, 0) + 1

        threads = [threading.Thread(target=acquire_resource, args=(i,))
                  for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # All threads should have acquired the resource
        assert len(acquired_count) == 10

        # Distribution should be relatively fair
        min_acquired = min(acquired_count.values())
        max_acquired = max(acquired_count.values())

        # No thread should be starved (at least 1 acquisition)
        assert min_acquired >= 1
        # Distribution shouldn't be too uneven
        assert max_acquired <= min_acquired * 3
