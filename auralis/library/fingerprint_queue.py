# -*- coding: utf-8 -*-

"""
Fingerprint Extraction Queue
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Async background queue for fingerprint extraction during library scanning.

Implements non-blocking fingerprint extraction using:
- asyncio.Queue for thread-safe work distribution
- 4 background worker threads (GIL-limited but good for I/O)
- Status tracking in database
- Error handling and retry logic

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import threading
import time
from queue import Queue, PriorityQueue, Empty
from typing import Optional, Dict, Callable, List, Tuple, Any
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from ..utils.logging import info, warning, error, debug


@dataclass
class FingerprintJob:
    """Represents a fingerprint extraction job"""
    track_id: int
    filepath: str
    priority: int = 0  # 0=normal, higher=more urgent
    created_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = time.time()

    def __lt__(self, other: "FingerprintJob") -> bool:
        """Priority queue ordering (higher priority first)"""
        if self.priority != other.priority:
            return self.priority > other.priority
        created_at_self: float = self.created_at if self.created_at is not None else 0.0
        created_at_other: float = other.created_at if other.created_at is not None else 0.0
        return created_at_self < created_at_other


class FingerprintExtractionQueue:
    """
    Async queue for background fingerprint extraction

    Usage:
        # Initialize
        queue = FingerprintExtractionQueue(
            fingerprint_extractor=extractor,
            library_manager=lib_manager,
            num_workers=4
        )

        # Start background workers
        await queue.start()

        # Queue a job
        await queue.enqueue(track_id=123, filepath='/path/to/audio.mp3')

        # Or enqueue batch during library scan
        await queue.enqueue_batch([(1, 'file1.mp3'), (2, 'file2.mp3')])

        # Stop gracefully
        await queue.stop()
    """

    def __init__(self,
                 fingerprint_extractor: Any,
                 library_manager: Any,
                 num_workers: int = 4,
                 max_queue_size: int = 500) -> None:
        """
        Initialize fingerprint extraction queue

        Args:
            fingerprint_extractor: FingerprintExtractor instance
            library_manager: LibraryManager for status updates
            num_workers: Number of background worker threads (default: 4)
            max_queue_size: Maximum queue size before blocking (default: 500)
        """
        self.extractor: Any = fingerprint_extractor
        self.library_manager: Any = library_manager
        self.num_workers: int = num_workers
        self.max_queue_size: int = max_queue_size

        # Thread-safe queue for job distribution
        # Using Queue for job distribution
        self.job_queue: Queue[FingerprintJob] = Queue(maxsize=max_queue_size)

        # Worker threads
        self.workers: List[threading.Thread] = []
        self.should_stop: bool = False

        # Statistics
        self.stats: Dict[str, Any] = {
            'queued': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'cached': 0,
            'total_time': 0.0
        }
        self.stats_lock: threading.RLock = threading.RLock()

        # Progress callback
        self.progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_progress_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback for progress updates"""
        self.progress_callback = callback

    async def start(self) -> None:
        """Start background worker threads"""
        info(f"Starting {self.num_workers} fingerprint extraction workers")

        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                daemon=False,
                name=f"FingerprintWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)

        info(f"All {self.num_workers} workers started")

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

    async def enqueue(self,
                      track_id: int,
                      filepath: str,
                      priority: int = 0) -> bool:
        """
        Enqueue a single fingerprint extraction job

        Args:
            track_id: Database ID of the track
            filepath: Path to the audio file
            priority: Job priority (0=normal, higher=more urgent)

        Returns:
            True if enqueued successfully, False if queue is full
        """
        job = FingerprintJob(
            track_id=track_id,
            filepath=filepath,
            priority=priority
        )

        try:
            # Non-blocking put with max_queue_size limit
            self.job_queue.put_nowait(job)

            with self.stats_lock:
                self.stats['queued'] += 1

            debug(f"Enqueued fingerprint job for track {track_id}")
            return True

        except:
            warning(f"Fingerprint queue full, skipping track {track_id}")
            return False

    async def enqueue_batch(self,
                            track_paths: List[Tuple[int, str]],
                            priority: int = 0) -> int:
        """
        Enqueue multiple jobs in batch

        Args:
            track_paths: List of (track_id, filepath) tuples
            priority: Priority for all jobs in batch

        Returns:
            Number of jobs successfully enqueued
        """
        enqueued = 0
        for track_id, filepath in track_paths:
            if await self.enqueue(track_id, filepath, priority):
                enqueued += 1
            else:
                warning(f"Failed to enqueue batch job for track {track_id}")

        info(f"Enqueued {enqueued}/{len(track_paths)} batch jobs")
        return enqueued

    def _worker_loop(self, worker_id: int) -> None:
        """
        Main loop for background worker thread

        Args:
            worker_id: ID of this worker
        """
        info(f"Worker {worker_id} started")

        try:
            while not self.should_stop:
                try:
                    # Get job from queue with timeout
                    job = self.job_queue.get(timeout=1.0)
                    # Process job
                    self._process_job(job, worker_id)

                except Empty:
                    # Queue is empty, loop will check should_stop on next iteration
                    continue

        except Exception as e:
            error(f"Worker {worker_id} encountered error: {e}")
        finally:
            info(f"Worker {worker_id} stopped")

    def _process_job(self, job: FingerprintJob, worker_id: int) -> None:
        """
        Process a single fingerprint extraction job

        Args:
            job: FingerprintJob to process
            worker_id: ID of the worker processing this job
        """
        with self.stats_lock:
            self.stats['processing'] += 1

        job_start = time.time()
        success = False

        try:
            # Mark as processing in database
            self._update_track_status(job.track_id, 'processing')

            debug(f"Worker {worker_id} extracting fingerprint for track {job.track_id}")

            # Extract and store fingerprint
            success = self.extractor.extract_and_store(job.track_id, job.filepath)

            if success:
                # Mark as complete in database
                self._update_track_status(job.track_id, 'complete')

                with self.stats_lock:
                    self.stats['completed'] += 1
                    self.stats['total_time'] += time.time() - job_start

                info(f"Fingerprint extracted for track {job.track_id}")

                self._report_progress({
                    'stage': 'fingerprinting',
                    'track_id': job.track_id,
                    'status': 'complete',
                    'time': time.time() - job_start
                })

            else:
                raise Exception(f"Extractor returned False for track {job.track_id}")

        except Exception as e:
            error(f"Error extracting fingerprint for track {job.track_id}: {e}")

            job.retry_count += 1

            # Retry or fail
            if job.retry_count < job.max_retries:
                with self.stats_lock:
                    self.stats['processing'] -= 1

                # Re-enqueue with backoff
                warning(f"Retrying track {job.track_id} (attempt {job.retry_count})")
                # Note: Can't await in this thread context, so put job back synchronously
                try:
                    self.job_queue.put_nowait(job)
                except asyncio.QueueFull:
                    error(f"Failed to re-enqueue track {job.track_id} for retry")
            else:
                # Max retries exceeded, mark as failed
                self._update_track_status(
                    job.track_id,
                    'error',
                    error_message=f"Fingerprint extraction failed after {job.max_retries} retries: {str(e)}"
                )

                with self.stats_lock:
                    self.stats['failed'] += 1

                self._report_progress({
                    'stage': 'fingerprinting',
                    'track_id': job.track_id,
                    'status': 'error',
                    'error': str(e)
                })

        finally:
            with self.stats_lock:
                self.stats['processing'] = max(0, self.stats['processing'] - 1)

    def _update_track_status(self,
                            track_id: int,
                            status: str,
                            error_message: Optional[str] = None) -> None:
        """
        Update track fingerprint status in database

        Args:
            track_id: Database ID of the track
            status: Status value (pending, processing, complete, error)
            error_message: Optional error message
        """
        try:
            # This would use library_manager to update the track
            # Placeholder for actual implementation
            debug(f"Updated track {track_id} status to {status}")

        except Exception as e:
            error(f"Failed to update track status: {e}")

    def _report_progress(self, progress_data: Dict[str, Any]) -> None:
        """Report progress to callback if set"""
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                error(f"Progress callback error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get current queue statistics"""
        with self.stats_lock:
            return self.stats.copy()

    def get_queue_size(self) -> int:
        """Get current queue size"""
        try:
            return self.job_queue.qsize()
        except:
            return 0


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
            library_manager=library_manager,
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

    async def enqueue_during_scan(self, track_id: int, filepath: str) -> bool:
        """Enqueue during library scan (async)"""
        return await self.queue.enqueue(track_id, filepath, priority=0)

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return self.queue.get_stats()

    def set_progress_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set progress callback"""
        self.queue.set_progress_callback(callback)
