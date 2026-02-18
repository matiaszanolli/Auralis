"""
Lifecycle tests for FingerprintExtractionQueue (issue #2309)

Covers:
- start(): worker thread creation
- stop(): graceful shutdown and timeout
- _worker_loop: normal drain, should_stop exit, error recovery
- _process_track: stats tracking, semaphore, progress callback
- FingerprintQueueManager: initialize / shutdown / stats
"""

import asyncio
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from auralis.services.fingerprint_queue import (
    FingerprintExtractionQueue,
    FingerprintQueueManager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_track(track_id: int = 1, filepath: str = "/tmp/track.wav") -> SimpleNamespace:
    return SimpleNamespace(id=track_id, filepath=filepath)


def _make_queue(
    num_workers: int = 2,
    extractor: MagicMock | None = None,
    factory: MagicMock | None = None,
) -> tuple[FingerprintExtractionQueue, MagicMock, MagicMock]:
    if extractor is None:
        extractor = MagicMock()
        extractor.extract_and_store.return_value = True

    if factory is None:
        factory = MagicMock()
        factory.fingerprints.claim_next_unfingerprinted_track.return_value = None

    queue = FingerprintExtractionQueue(
        fingerprint_extractor=extractor,
        get_repository_factory=lambda: factory,
        num_workers=num_workers,
        enable_adaptive_scaling=False,
    )
    return queue, extractor, factory


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------

class TestFingerprintQueueStart:
    """start() must spawn exactly num_workers daemon threads."""

    @pytest.mark.asyncio
    async def test_start_spawns_correct_worker_count(self):
        queue, _, factory = _make_queue(num_workers=3)
        # Workers exit immediately when no tracks are available
        factory.fingerprints.claim_next_unfingerprinted_track.return_value = None

        await queue.start()

        assert len(queue.workers) == 3, (
            f"Expected 3 workers, got {len(queue.workers)}"
        )
        # Give threads a moment to exit naturally
        for w in queue.workers:
            w.join(timeout=2.0)

    @pytest.mark.asyncio
    async def test_start_threads_have_correct_names(self):
        queue, _, _ = _make_queue(num_workers=2)

        await queue.start()

        names = {w.name for w in queue.workers}
        assert "FingerprintWorker-0" in names
        assert "FingerprintWorker-1" in names
        for w in queue.workers:
            w.join(timeout=2.0)

    @pytest.mark.asyncio
    async def test_start_workers_are_alive_immediately(self):
        """Workers must be alive right after start() with blocking work available."""
        block = threading.Event()
        queue, _, factory = _make_queue(num_workers=2)

        # Workers block until released
        factory.fingerprints.claim_next_unfingerprinted_track.side_effect = (
            lambda: (block.wait(timeout=5.0) or None)
        )

        await queue.start()

        try:
            assert all(w.is_alive() for w in queue.workers), (
                "All workers must be alive immediately after start()"
            )
        finally:
            queue.should_stop = True
            block.set()
            for w in queue.workers:
                w.join(timeout=3.0)


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------

class TestFingerprintQueueStop:
    """stop() must shut down all workers gracefully."""

    @pytest.mark.asyncio
    async def test_stop_sets_should_stop_flag(self):
        queue, _, _ = _make_queue(num_workers=1)
        await queue.start()
        for w in queue.workers:
            w.join(timeout=2.0)  # let it drain naturally

        assert not queue.should_stop
        await queue.stop(timeout=1.0)
        assert queue.should_stop

    @pytest.mark.asyncio
    async def test_stop_joins_all_workers(self):
        """After stop(), no worker threads are alive."""
        queue, _, _ = _make_queue(num_workers=2)
        await queue.start()

        result = await queue.stop(timeout=5.0)

        assert result is True
        for w in queue.workers:
            assert not w.is_alive(), f"{w.name} is still alive after stop()"

    @pytest.mark.asyncio
    async def test_stop_returns_true_on_clean_shutdown(self):
        queue, _, _ = _make_queue(num_workers=2)
        await queue.start()

        result = await queue.stop(timeout=5.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_stop_returns_false_on_timeout(self):
        """stop() returns False if workers don't finish before the timeout."""
        block = threading.Event()
        queue, _, factory = _make_queue(num_workers=1)

        # Worker blocks indefinitely (simulates slow I/O)
        factory.fingerprints.claim_next_unfingerprinted_track.side_effect = (
            lambda: (block.wait(timeout=60.0) or None)
        )

        await queue.start()

        try:
            result = await queue.stop(timeout=0.05)
            assert result is False
        finally:
            block.set()
            for w in queue.workers:
                w.join(timeout=3.0)


# ---------------------------------------------------------------------------
# _worker_loop
# ---------------------------------------------------------------------------

class TestWorkerLoop:
    """_worker_loop must drain tracks, respect should_stop, and recover from errors."""

    def test_worker_processes_all_tracks_then_exits(self):
        """Worker calls claim_next... until None is returned, then exits."""
        tracks = [_make_track(1), _make_track(2), _make_track(3)]
        queue, extractor, factory = _make_queue(num_workers=1)
        factory.fingerprints.claim_next_unfingerprinted_track.side_effect = (
            tracks + [None]
        )

        t = threading.Thread(target=queue._worker_loop, args=(0,))
        t.start()
        t.join(timeout=5.0)

        assert not t.is_alive(), "Worker must exit after draining all tracks"
        assert extractor.extract_and_store.call_count == 3

    def test_worker_exits_when_should_stop_is_set(self):
        """Worker exits promptly when should_stop is True."""
        queue, _, factory = _make_queue(num_workers=1)
        queue.should_stop = True
        # Would return a track if loop ran — but it shouldn't
        factory.fingerprints.claim_next_unfingerprinted_track.return_value = _make_track()

        t = threading.Thread(target=queue._worker_loop, args=(0,))
        t.start()
        t.join(timeout=2.0)

        assert not t.is_alive(), "Worker must exit when should_stop is True"
        factory.fingerprints.claim_next_unfingerprinted_track.assert_not_called()

    def test_worker_recovers_from_processing_exception(self):
        """Exception during _process_track causes a brief sleep, then loop continues."""
        queue, extractor, factory = _make_queue(num_workers=1)
        # First call raises, second returns None to end the loop
        factory.fingerprints.claim_next_unfingerprinted_track.side_effect = [
            _make_track(1),
            None,
        ]
        extractor.extract_and_store.side_effect = RuntimeError("extraction failed")

        with patch("time.sleep"):   # skip sleep(0.1)
            t = threading.Thread(target=queue._worker_loop, args=(0,))
            t.start()
            t.join(timeout=3.0)

        assert not t.is_alive(), "Worker must exit even after processing exception"
        assert queue.stats["failed"] == 1

    def test_worker_stops_mid_run_when_should_stop_set(self):
        """Setting should_stop while worker is running causes it to exit after current track."""
        processed = threading.Event()
        queue, extractor, factory = _make_queue(num_workers=1)

        def slow_extract(track_id, filepath):
            processed.set()
            time.sleep(0.05)  # brief pause — should_stop gets set during this
            return True

        extractor.extract_and_store.side_effect = slow_extract
        factory.fingerprints.claim_next_unfingerprinted_track.return_value = _make_track()

        t = threading.Thread(target=queue._worker_loop, args=(0,))
        t.start()

        processed.wait(timeout=5.0)
        queue.should_stop = True

        t.join(timeout=3.0)
        assert not t.is_alive(), "Worker must stop after current track finishes"


# ---------------------------------------------------------------------------
# _process_track — stats and semaphore
# ---------------------------------------------------------------------------

class TestProcessTrack:
    """_process_track updates stats and respects the processing semaphore."""

    def test_success_increments_completed_stat(self):
        queue, extractor, _ = _make_queue()
        extractor.extract_and_store.return_value = True

        queue._process_track(_make_track(1), worker_id=0)

        assert queue.stats["completed"] == 1
        assert queue.stats["failed"] == 0

    def test_failure_increments_failed_stat(self):
        queue, extractor, _ = _make_queue()
        extractor.extract_and_store.return_value = False  # falsy → exception path

        queue._process_track(_make_track(1), worker_id=0)

        assert queue.stats["failed"] == 1
        assert queue.stats["completed"] == 0

    def test_exception_increments_failed_stat(self):
        queue, extractor, _ = _make_queue()
        extractor.extract_and_store.side_effect = RuntimeError("oops")

        queue._process_track(_make_track(1), worker_id=0)

        assert queue.stats["failed"] == 1

    def test_processing_stat_returns_to_zero_after_track(self):
        """processing counter must be 0 after _process_track finishes."""
        queue, extractor, _ = _make_queue()
        extractor.extract_and_store.return_value = True

        queue._process_track(_make_track(1), worker_id=0)

        assert queue.stats["processing"] == 0

    def test_semaphore_released_on_success(self):
        """Semaphore must be released after successful processing."""
        queue, extractor, _ = _make_queue()
        extractor.extract_and_store.return_value = True
        initial = queue.processing_semaphore._value

        queue._process_track(_make_track(1), worker_id=0)

        assert queue.processing_semaphore._value == initial

    def test_semaphore_released_on_failure(self):
        """Semaphore must be released even when processing raises."""
        queue, extractor, _ = _make_queue()
        extractor.extract_and_store.side_effect = RuntimeError("fail")
        initial = queue.processing_semaphore._value

        queue._process_track(_make_track(1), worker_id=0)

        assert queue.processing_semaphore._value == initial

    def test_semaphore_limits_concurrent_processing(self):
        """At most semaphore_value tracks may be processed concurrently."""
        sem_size = 2
        queue, extractor, factory = _make_queue(num_workers=sem_size + 2)
        queue.processing_semaphore = threading.Semaphore(sem_size)

        concurrent_peak = [0]
        lock = threading.Lock()
        in_flight = [0]
        errors: list[str] = []

        def slow_extract(track_id, filepath):
            with lock:
                in_flight[0] += 1
                if in_flight[0] > sem_size:
                    errors.append(f"concurrency {in_flight[0]} > sem_size {sem_size}")
                if in_flight[0] > concurrent_peak[0]:
                    concurrent_peak[0] = in_flight[0]
            time.sleep(0.02)
            with lock:
                in_flight[0] -= 1
            return True

        extractor.extract_and_store.side_effect = slow_extract

        threads = [
            threading.Thread(target=queue._process_track, args=(_make_track(i), i))
            for i in range(sem_size + 2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Semaphore violated: {errors}"
        assert concurrent_peak[0] <= sem_size


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------

class TestProgressCallback:
    """_report_progress must invoke the callback with correct data."""

    def test_progress_called_with_success_data(self):
        queue, extractor, _ = _make_queue()
        extractor.extract_and_store.return_value = True
        cb = MagicMock()
        queue.set_progress_callback(cb)

        queue._process_track(_make_track(42), worker_id=0)

        cb.assert_called_once()
        args = cb.call_args[0][0]
        assert args["stage"] == "fingerprinting"
        assert args["track_id"] == 42
        assert args["status"] == "complete"

    def test_progress_called_with_error_data(self):
        queue, extractor, _ = _make_queue()
        extractor.extract_and_store.side_effect = RuntimeError("bad file")
        cb = MagicMock()
        queue.set_progress_callback(cb)

        queue._process_track(_make_track(7), worker_id=0)

        cb.assert_called_once()
        args = cb.call_args[0][0]
        assert args["status"] == "error"
        assert args["track_id"] == 7

    def test_progress_callback_exception_does_not_crash(self):
        """Exception inside the callback must not propagate."""
        queue, extractor, _ = _make_queue()
        extractor.extract_and_store.return_value = True
        queue.set_progress_callback(MagicMock(side_effect=RuntimeError("cb error")))

        # Must not raise
        queue._process_track(_make_track(1), worker_id=0)


# ---------------------------------------------------------------------------
# Graceful shutdown with in-flight work
# ---------------------------------------------------------------------------

class TestGracefulShutdown:
    """stop() must wait for in-flight work to finish, not cut it short."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown_finishes_current_track(self):
        """Workers finish the track they are processing before stopping."""
        track_done = threading.Event()
        queue, extractor, factory = _make_queue(num_workers=1)

        # Worker will process one track then there are no more
        factory.fingerprints.claim_next_unfingerprinted_track.side_effect = [
            _make_track(1),
            None,
        ]

        def slow_extract(track_id, filepath):
            time.sleep(0.05)
            track_done.set()
            return True

        extractor.extract_and_store.side_effect = slow_extract

        await queue.start()
        result = await queue.stop(timeout=5.0)

        assert result is True
        assert track_done.is_set(), "Track must have been fully processed"
        assert queue.stats["completed"] == 1

    @pytest.mark.asyncio
    async def test_stats_accurate_after_full_run(self):
        """Stats reflect all processed tracks after a complete start→stop cycle."""
        n_tracks = 5
        queue, extractor, factory = _make_queue(num_workers=2)

        factory.fingerprints.claim_next_unfingerprinted_track.side_effect = (
            [_make_track(i) for i in range(n_tracks)] + [None, None]
        )
        extractor.extract_and_store.return_value = True

        await queue.start()
        await queue.stop(timeout=10.0)

        assert queue.stats["completed"] == n_tracks
        assert queue.stats["failed"] == 0


# ---------------------------------------------------------------------------
# FingerprintQueueManager
# ---------------------------------------------------------------------------

class TestFingerprintQueueManager:
    """FingerprintQueueManager lifecycle: initialize / shutdown / stats."""

    def _make_manager(self) -> FingerprintQueueManager:
        mock_extractor = MagicMock()
        mock_lib = MagicMock()
        mock_lib.repository_factory.fingerprints.claim_next_unfingerprinted_track.return_value = None
        return FingerprintQueueManager(
            fingerprint_extractor=mock_extractor,
            library_manager=mock_lib,
            num_workers=1,
        )

    @pytest.mark.asyncio
    async def test_initialize_sets_is_running(self):
        mgr = self._make_manager()
        assert not mgr.is_running

        await mgr.initialize()
        try:
            assert mgr.is_running
        finally:
            await mgr.shutdown(timeout=3.0)

    @pytest.mark.asyncio
    async def test_initialize_is_idempotent(self):
        """Calling initialize() twice must not double-start workers."""
        mgr = self._make_manager()
        await mgr.initialize()
        workers_after_first = len(mgr.queue.workers)

        await mgr.initialize()  # second call must be a no-op

        try:
            assert len(mgr.queue.workers) == workers_after_first
        finally:
            await mgr.shutdown(timeout=3.0)

    @pytest.mark.asyncio
    async def test_shutdown_clears_is_running(self):
        mgr = self._make_manager()
        await mgr.initialize()
        assert mgr.is_running

        result = await mgr.shutdown(timeout=3.0)

        assert result is True
        assert not mgr.is_running

    @pytest.mark.asyncio
    async def test_shutdown_without_initialize_is_noop(self):
        """shutdown() on an un-initialized manager must return True immediately."""
        mgr = self._make_manager()
        result = await mgr.shutdown(timeout=1.0)
        assert result is True
        assert not mgr.is_running

    def test_get_stats_returns_dict(self):
        mgr = self._make_manager()
        stats = mgr.get_stats()
        assert isinstance(stats, dict)
        assert "completed" in stats
        assert "failed" in stats

    def test_set_progress_callback(self):
        mgr = self._make_manager()
        cb = MagicMock()
        mgr.set_progress_callback(cb)
        assert mgr.queue.progress_callback is cb
