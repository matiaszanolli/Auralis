"""
Fingerprint Extraction Worker Pool
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fingerprinting workers that pull directly from database instead of a job queue.

Architecture:
- Workers fetch unfingerprinted tracks from database as they finish previous track
- No pre-loaded track list - eliminates memory accumulation
- No job queue - no enqueue/dequeue overhead or backpressure issues
- Natural rate limiting - workers fetch only when ready
- Bounded memory: only one audio file per worker in memory at a time

Worker Pool:
- Adaptive worker threads: auto-detects CPU cores (4-24 threads)
  - High-end systems (16+ cores): uses 75% of CPU cores for maximum parallelism
  - Low-end systems (< 8 cores): uses 4 workers as default
- Thread-safe statistics tracking
- Progress callbacks for monitoring

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
import time
from typing import Any
from collections.abc import Callable

from auralis.services.fingerprint_extractor import FingerprintExtractor
from auralis.services.fingerprint_queue_scaling import (
    AdaptiveScalingMixin, build_processing_semaphore, build_resource_monitor,
    resolve_worker_bounds, start_resource_monitor, stop_resource_monitor,
)
from auralis.services.fingerprint_worker import (
    DEFAULT_TRACK_TIMEOUT_SECONDS, FingerprintWorkerExecution, _default_track_timeout,
)
from auralis.services.resizable_semaphore import ResizableSemaphore
from auralis.library.repositories.factory import RepositoryFactory
from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION

from ..library.resource_monitor import AdaptiveResourceMonitor
from ..utils.logging import debug, error, info, warning


class FingerprintExtractionQueue(FingerprintWorkerExecution, AdaptiveScalingMixin):
    """
    Fingerprint extraction worker pool - workers pull directly from database.

    Architecture:
    - No job queue: Eliminates pre-loading tracks and queue accumulation
    - Workers pull next unfingerprinted track from database after finishing
    - Natural rate limiting: Workers only fetch when ready
    - No memory buildup: Only one track in memory per worker at a time
    - Fully async: Workers block only on disk I/O, not queue operations

    Usage:
        # Initialize (automatically starts workers)
        queue = FingerprintExtractionQueue(
            fingerprint_extractor=extractor,
            library_manager=lib_manager,
            num_workers=16
        )
        await queue.start()

        # Workers automatically process all unfingerprinted tracks from database
        # Monitor progress via queue.stats

        # Stop gracefully
        await queue.stop()
    """

    def __init__(self,
                 fingerprint_extractor: FingerprintExtractor,
                 get_repository_factory: Callable[[], RepositoryFactory],
                 num_workers: int | None = None,
                 enable_adaptive_scaling: bool = True,
                 max_workers: int | None = None,
                 track_timeout: float | None = None) -> None:
        """
        Initialize fingerprint extraction worker pool.

        Args:
            fingerprint_extractor: FingerprintExtractor instance
            get_repository_factory: Callable that returns RepositoryFactory for querying tracks
            num_workers: Number of background worker threads (default: 0.5x CPU cores)
            enable_adaptive_scaling: Enable adaptive resource monitoring (default: True)
            max_workers: Maximum workers for adaptive scaling (default: 2.0x CPU cores)
            track_timeout: Per-track bound on extraction in seconds (#4837; default
                from AURALIS_FINGERPRINT_TRACK_TIMEOUT, else 600)
        """
        num_workers, max_workers = resolve_worker_bounds(num_workers, max_workers)

        self.extractor: FingerprintExtractor = fingerprint_extractor
        self._get_repository_factory: Callable[[], RepositoryFactory] = get_repository_factory
        self.initial_num_workers: int = num_workers
        self.current_num_workers: int = num_workers
        self.max_workers_limit: int = max_workers
        self.track_timeout: float = (
            track_timeout if track_timeout is not None else _default_track_timeout()
        )

        # Worker threads (no job queue needed)
        self.workers: list[threading.Thread] = []
        self.should_stop: bool = False

        # Statistics (removed 'queued' since no queue)
        self.stats: dict[str, Any] = {
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'cached': 0,
            'total_time': 0.0,
            'scale_events': 0
        }
        self.stats_lock: threading.RLock = threading.RLock()

        self.processing_semaphore: ResizableSemaphore = build_processing_semaphore(
            max_workers
        )

        # Adaptive resource monitoring
        self.enable_adaptive_scaling: bool = enable_adaptive_scaling
        self.resource_monitor: AdaptiveResourceMonitor | None = None
        if enable_adaptive_scaling:
            self.resource_monitor = build_resource_monitor(
                min_workers=num_workers,
                max_workers=max_workers,
                on_worker_count_change=self._on_worker_count_change,
                on_semaphore_change=self._on_semaphore_change
            )

        # Progress callback
        self.progress_callback: Callable[[dict[str, Any]], None] | None = None

        # #3479: drain callback — fired once per "drain wave" (transition from
        # busy → idle) after at least one track was processed in the wave.
        # Used to trigger reference-cloud refresh when fresh fingerprints land.
        self.on_drained: Callable[[], None] | None = None
        self._drain_state_lock: threading.Lock = threading.Lock()
        self._processed_since_drain: int = 0
        self._drained_workers: int = 0

    @property
    def num_workers(self) -> int:
        """Get current worker count (includes adaptive scaling adjustments)"""
        return self.current_num_workers

    def set_progress_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Set callback for progress updates"""
        self.progress_callback = callback

    async def start(self) -> None:
        """Start background worker threads and resource monitor"""
        start_resource_monitor(self.resource_monitor)

        info(f"Starting {self.initial_num_workers} fingerprint extraction workers")

        for i in range(self.initial_num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                daemon=True,   # daemon=True: process exits cleanly even without stop() (#2247)
                name=f"FingerprintWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)

        info(f"All {self.initial_num_workers} workers started")

    async def stop(self, timeout: float = 30.0) -> bool:
        """
        Stop all worker threads gracefully

        Args:
            timeout: Maximum time to wait for workers to finish (seconds)

        Returns:
            True if all workers stopped cleanly, False if timeout
        """
        info("Stopping fingerprint extraction workers...")
        self.should_stop = True

        stop_resource_monitor(self.resource_monitor)

        # Wait for all workers to finish
        start_time = time.time()
        for worker in self.workers:
            remaining = timeout - (time.time() - start_time)
            if remaining <= 0:
                warning("Worker shutdown timeout exceeded")
                return False

            worker.join(timeout=remaining)
            if worker.is_alive():
                warning(f"Worker {worker.name} did not stop within timeout")
                return False

        info(f"All workers stopped. Stats: {self.stats}")
        return True

    def _worker_loop(self, worker_id: int) -> None:
        """
        Main loop for background worker thread.

        Workers atomically claim unfingerprinted tracks from database and process them.
        No job queue - workers pull directly from DB when ready.

        CRITICAL FIX FOR RACE CONDITION: Uses atomic database transaction
        to claim tracks before processing, preventing multiple workers from
        processing the same track simultaneously.

        Args:
            worker_id: ID of this worker
        """
        info(f"Worker {worker_id} started")

        try:
            # Phase 1: Process newly added tracks (no fingerprint row at all).
            while not self.should_stop:
                try:
                    factory = self._get_repository_factory()
                    track = factory.fingerprint_scheduler.claim_next_unfingerprinted_track()
                    if not track:
                        debug(f"Worker {worker_id}: No more unfingerprinted tracks")
                        break
                    self._process_track(track, worker_id)
                    self._on_track_processed()  # #3479
                except Exception as e:
                    error(f"Worker {worker_id} error during processing: {e}")
                    time.sleep(0.1)

            # #3479: Phase 1 drained (or worker is stopping) — record the
            # transition so on_drained fires when all workers settle.
            if not self.should_stop:
                self._on_worker_drained()

            # Phase 2: Re-fingerprint tracks whose fingerprint was computed with an
            # older algorithm version.  Only runs when FINGERPRINT_ALGORITHM_VERSION
            # has been bumped; claim_next_outdated_fingerprint() returns None
            # immediately when current_version <= 1.
            if not self.should_stop:
                info(f"Worker {worker_id}: Checking for outdated fingerprints (v<{FINGERPRINT_ALGORITHM_VERSION})")
            while not self.should_stop:
                try:
                    factory = self._get_repository_factory()
                    track = factory.fingerprint_scheduler.claim_next_outdated_fingerprint(FINGERPRINT_ALGORITHM_VERSION)
                    if not track:
                        debug(f"Worker {worker_id}: No more outdated fingerprints")
                        break
                    self._process_track(track, worker_id)
                    self._on_track_processed()  # #3479
                except Exception as e:
                    error(f"Worker {worker_id} error during outdated re-fingerprinting: {e}")
                    time.sleep(0.1)

            # #3479: Phase 2 drained — same drain-wave bookkeeping.
            if not self.should_stop:
                self._on_worker_drained()

        except Exception as e:
            error(f"Worker {worker_id} encountered critical error: {e}")
        finally:
            info(f"Worker {worker_id} stopped")

    def get_stats(self) -> dict[str, Any]:
        """Get worker pool statistics"""
        with self.stats_lock:
            return self.stats.copy()


def __getattr__(name: str) -> Any:
    """Lazily re-export `FingerprintQueueManager` (#5039).

    The class moved to `fingerprint_queue_manager`, which imports
    `FingerprintExtractionQueue` from here — so a module-level re-export would
    be a circular import. Resolving it on first attribute access keeps the
    historical `from auralis.services.fingerprint_queue import
    FingerprintQueueManager` path working from either import order.
    """
    if name == "FingerprintQueueManager":
        from auralis.services.fingerprint_queue_manager import FingerprintQueueManager

        return FingerprintQueueManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_TRACK_TIMEOUT_SECONDS",
    "FingerprintExtractionQueue",
    "FingerprintQueueManager",
    "_default_track_timeout",
]
