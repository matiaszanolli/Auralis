# -*- coding: utf-8 -*-

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
from typing import Any, Callable, Dict, List, Optional

from auralis.library.fingerprint_extractor import FingerprintExtractor
from auralis.library.repositories.factory import RepositoryFactory

from ..utils.logging import debug, error, info, warning
from .resource_monitor import AdaptiveResourceMonitor, ResourceLimits


class FingerprintExtractionQueue:
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
                 num_workers: Optional[int] = None,
                 enable_adaptive_scaling: bool = True,
                 max_workers: Optional[int] = None) -> None:
        """
        Initialize fingerprint extraction worker pool.

        Args:
            fingerprint_extractor: FingerprintExtractor instance
            get_repository_factory: Callable that returns RepositoryFactory for querying tracks
            num_workers: Number of background worker threads (default: 0.5x CPU cores)
            enable_adaptive_scaling: Enable adaptive resource monitoring (default: True)
            max_workers: Maximum workers for adaptive scaling (default: 2.0x CPU cores)
        """
        import os

        # Auto-detect optimal worker bounds based on CPU cores
        cpu_count = os.cpu_count() or 16

        # Set initial worker count if not specified (0.5x ratio - conservative)
        if num_workers is None:
            num_workers = max(4, int(cpu_count * 0.5))

        # Set max worker ceiling if not specified (2.0x ratio - aggressive)
        if max_workers is None:
            max_workers = int(cpu_count * 2.0)

        self.extractor: FingerprintExtractor = fingerprint_extractor
        self._get_repository_factory: Callable[[], RepositoryFactory] = get_repository_factory
        self.initial_num_workers: int = num_workers
        self.current_num_workers: int = num_workers
        self.max_workers_limit: int = max_workers

        # Worker threads (no job queue needed)
        self.workers: List[threading.Thread] = []
        self.should_stop: bool = False

        # Statistics (removed 'queued' since no queue)
        self.stats: Dict[str, Any] = {
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'cached': 0,
            'total_time': 0.0,
            'scale_events': 0
        }
        self.stats_lock: threading.RLock = threading.RLock()

        # Memory-aware processing semaphore
        # Limits concurrent audio file loading to prevent memory bloat
        # Generous limit: 1 semaphore per worker (allows full parallelism with Rust server)
        # Rust server has 64 blocking threads, so allow high concurrency in Python
        self.processing_semaphore: threading.Semaphore = threading.Semaphore(
            max(8, max_workers)  # At least 8, up to max_workers
        )

        # Adaptive resource monitoring
        self.enable_adaptive_scaling: bool = enable_adaptive_scaling
        self.resource_monitor: Optional[AdaptiveResourceMonitor] = None
        if enable_adaptive_scaling:
            # Create adaptive monitor with 75% RAM limit and dynamic worker bounds
            limits = ResourceLimits(
                max_memory_percent=75.0,
                min_workers=num_workers,  # Start at 0.5x ratio
                max_workers=max_workers,  # Scale up to 2.0x ratio based on RAM
                max_semaphore=max(8, max_workers),  # Allow full parallelism with Rust server
                check_interval=2.0,
                scale_up_threshold=50.0,  # Scale up if RAM < 50%
                scale_down_threshold=80.0  # Scale down if RAM > 80%
            )
            self.resource_monitor = AdaptiveResourceMonitor(
                limits=limits,
                on_worker_count_change=self._on_worker_count_change,
                on_semaphore_change=self._on_semaphore_change
            )

        # Progress callback
        self.progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    @property
    def num_workers(self) -> int:
        """Get current worker count (includes adaptive scaling adjustments)"""
        return self.current_num_workers

    def set_progress_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback for progress updates"""
        self.progress_callback = callback

    def _on_worker_count_change(self, new_worker_count: int) -> None:
        """
        Callback invoked by AdaptiveResourceMonitor when worker count should change.

        Args:
            new_worker_count: New recommended worker count
        """
        with self.stats_lock:
            old_count = self.current_num_workers
            self.current_num_workers = new_worker_count
            self.stats['scale_events'] += 1

        if len(self.workers) > 0:
            direction = "↑" if new_worker_count > old_count else "↓"
            info(
                f"{direction} Worker scaling callback: {old_count} → {new_worker_count} "
                f"(Note: dynamic scaling requires worker pool restart)"
            )

    def _on_semaphore_change(self, new_semaphore_size: int) -> None:
        """
        Callback invoked by AdaptiveResourceMonitor when semaphore size changes.

        NOTE: Python's threading.Semaphore doesn't support safe dynamic resizing.
        The semaphore is pre-configured at initialization based on max_workers.
        We log the monitor's recommendation but don't modify the semaphore.

        Args:
            new_semaphore_size: Recommended concurrent audio processing limit from monitor
        """
        # Python's Semaphore doesn't provide a safe way to dynamically resize.
        # To properly implement this, we'd need to replace it with a custom semaphore class
        # that uses locks and a counter internally. For now, we just log the recommendation.
        debug(
            f"Adaptive monitor recommends semaphore size: {new_semaphore_size} "
            f"(using pre-configured value based on max_workers)"
        )

    async def start(self) -> None:
        """Start background worker threads and resource monitor"""
        # Start adaptive resource monitor if enabled
        if self.resource_monitor:
            self.resource_monitor.start()
            info("Adaptive resource monitor started (RAM threshold: 75%, workers: 4-32)")

        info(f"Starting {self.initial_num_workers} fingerprint extraction workers")

        for i in range(self.initial_num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                daemon=False,
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

        # Stop resource monitor if running
        if self.resource_monitor:
            monitor_stats = self.resource_monitor.get_stats()
            self.resource_monitor.stop()
            info(
                f"Adaptive resource monitor stopped. "
                f"Stats: {monitor_stats['scale_ups']} scale-ups, "
                f"{monitor_stats['scale_downs']} scale-downs, "
                f"avg RAM: {monitor_stats['avg_memory_percent']:.1f}%, "
                f"max RAM: {monitor_stats['max_memory_percent']:.1f}%"
            )

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
            while not self.should_stop:
                # Atomically claim next unfingerprinted track from database
                # This prevents race condition where multiple workers fetch the same track
                try:
                    factory = self._get_repository_factory()
                    track = factory.fingerprints.claim_next_unfingerprinted_track()
                    if not track:
                        # No more unfingerprinted tracks, exit loop
                        debug(f"Worker {worker_id}: No more unfingerprinted tracks")
                        break

                    # Process the claimed track
                    self._process_track(track, worker_id)

                except Exception as e:
                    error(f"Worker {worker_id} error during processing: {e}")
                    # Brief sleep before retrying to avoid busy-loop on persistent errors
                    time.sleep(0.1)

        except Exception as e:
            error(f"Worker {worker_id} encountered critical error: {e}")
        finally:
            info(f"Worker {worker_id} stopped")

    def _process_track(self, track: Any, worker_id: int) -> None:
        """
        Process a single track: extract and store fingerprint.

        Acquires memory-aware semaphore to limit concurrent audio processing.
        This prevents memory bloat when loading large audio files.

        Args:
            track: Track object with id and filepath attributes
            worker_id: ID of the worker processing this track
        """
        # Acquire semaphore to limit concurrent audio processing
        # Only 3 workers can process audio simultaneously (prevents ~1.2GB memory spikes)
        # Other workers wait here while still able to fetch from database
        debug(f"Worker {worker_id} waiting for processing slot (currently {self.stats['processing']}/3 in use)")
        self.processing_semaphore.acquire()

        with self.stats_lock:
            self.stats['processing'] += 1

        job_start = time.time()
        success = False

        try:
            debug(f"Worker {worker_id} extracting fingerprint for track {track.id}")

            # Extract and store fingerprint
            success = self.extractor.extract_and_store(track.id, track.filepath)

            if success:
                with self.stats_lock:
                    self.stats['completed'] += 1
                    self.stats['total_time'] += time.time() - job_start

                info(f"Fingerprint extracted for track {track.id}")

                self._report_progress({
                    'stage': 'fingerprinting',
                    'track_id': track.id,
                    'status': 'complete',
                    'time': time.time() - job_start
                })

            else:
                raise Exception(f"Extractor returned False for track {track.id}")

        except Exception as e:
            error(f"Error extracting fingerprint for track {track.id}: {e}")

            with self.stats_lock:
                self.stats['failed'] += 1

            self._report_progress({
                'stage': 'fingerprinting',
                'track_id': track.id,
                'status': 'error',
                'error': str(e)
            })

        finally:
            with self.stats_lock:
                self.stats['processing'] = max(0, self.stats['processing'] - 1)

            # Release semaphore to allow next worker to process
            self.processing_semaphore.release()

    def _report_progress(self, progress_data: Dict[str, Any]) -> None:
        """Report progress to callback if set"""
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                error(f"Progress callback error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics"""
        with self.stats_lock:
            return self.stats.copy()


class FingerprintQueueManager:
    """
    Manager for fingerprint extraction queue lifecycle

    Handles initialization, starting, stopping, and integration
    with the library scanner.
    """

    def __init__(self,
                 fingerprint_extractor: Any,
                 library_manager: Any,
                 num_workers: int = 4) -> None:
        """Initialize queue manager"""
        self.queue: FingerprintExtractionQueue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor,
            get_repository_factory=lambda: library_manager.repository_factory,
            num_workers=num_workers
        )
        self.is_running: bool = False

    async def initialize(self) -> None:
        """Initialize and start the queue"""
        if not self.is_running:
            await self.queue.start()
            self.is_running = True
            info("Fingerprint queue manager initialized and started")

    async def shutdown(self, timeout: float = 30.0) -> bool:
        """Shutdown the queue gracefully"""
        if self.is_running:
            success = await self.queue.stop(timeout=timeout)
            self.is_running = False
            if success:
                info("Fingerprint queue manager shut down successfully")
            else:
                warning("Fingerprint queue manager shutdown timed out")
            return success
        return True


    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return self.queue.get_stats()

    def set_progress_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set progress callback"""
        self.queue.set_progress_callback(callback)
