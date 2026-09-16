#!/usr/bin/env python3

"""
Processing Engine for Auralis Web Backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles audio processing jobs using the HybridProcessor from the core Auralis system.
Manages job queue, progress tracking, and result caching.

Coordinator over the job_*/processor_pool sibling modules; every method body
here is either real queue/lock bookkeeping or a thin delegate kept as a bound
method so tests can `patch.object(engine, ...)` it. #4250 waived this file at
365 LOC when it closed; #5454 re-affirms a 330 LOC waiver ceiling after
trimming re-documentation duplicated in the sibling modules' own docstrings
(379 -> 316) -- further reduction would mean cutting load-bearing behavioral
notes (e.g. submit_job's QueueFull contract, #3886, #2217), not more
duplication.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import sys
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

# Add parent directory to path for Auralis imports
sys.path.append(str(Path(__file__).parent.parent.parent))


from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor

# ProcessingJob/ProcessingStatus/_safe_error_message re-exported here so
# existing `from core.processing_engine import ...` callers keep working
# (#4250 follow-up).
from config.limits import PROCESSING_TEMP_DIRNAME, UPLOAD_TEMP_DIRNAME, create_secure_temp_dir
from core.job_cleanup import cleanup_expired_jobs
from core.job_config import create_processor_config
from core.job_error_mapping import _safe_error_message

# A test patches load_audio()/save() at 'core.job_execution.load_audio' /
# '.save' — see that module's docstring (#4250 follow-up).
from core.job_execution import execute_job, prepare_job
from core.job_finalize import finalize_job
from core.job_lifecycle import cancel_job as _cancel_job_impl
from core.job_lifecycle import create_job as _create_job_impl
from core.job_lifecycle import process_job as _process_job_impl
from core.job_models import ProcessingJob, ProcessingStatus
from core.job_progress import ProgressNotifier
from core.job_store import JobStore
from core.job_worker import JobWorker
from core.processor_pool import ProcessorPool

__all__ = [
    "ProcessingEngine",
    "ProcessingJob",
    "ProcessingStatus",
    "_safe_error_message",
]


logger = logging.getLogger(__name__)


class ProcessingEngine:
    """Audio processing engine managing the job queue and adaptive
    mastering via HybridProcessor."""

    # Ceiling for a single processor.process() call (seconds) -- unblocks
    # the queue if a Rust/PyO3 call hangs (fixes #2747).
    DEFAULT_PROCESSING_TIMEOUT: float = 300.0
    job_store: JobStore = JobStore()  # durable copy of `jobs` (#5278); no-op until wired

    def __init__(
        self,
        max_concurrent_jobs: int = 2,
        max_queue_size: int = 20,
        completed_job_ttl_hours: float = 1.0,
        processing_timeout: float | None = None,
        job_store: JobStore | None = None,
    ) -> None:
        self.jobs: dict[str, ProcessingJob] = {}
        self.job_store = job_store or JobStore()
        self.max_concurrent_jobs: int = max_concurrent_jobs
        self.max_queue_size: int = max_queue_size
        self.completed_job_ttl_hours: float = completed_job_ttl_hours
        self.processing_timeout: float = (
            processing_timeout if processing_timeout is not None else self.DEFAULT_PROCESSING_TIMEOUT
        )

        # Processor cache / worker loop: see ProcessorPool / JobWorker (#4250).
        self._pool: ProcessorPool = ProcessorPool(self._construct_processor)
        self._worker: JobWorker = JobWorker(self, max_concurrent_jobs, max_queue_size)
        # Same object as self._worker.job_queue — a legacy test that assigns
        # engine.job_queue directly still works.
        self.job_queue: "asyncio.Queue[ProcessingJob]" = self._worker.job_queue

        # Guards concurrent access to jobs / progress_callbacks (fixes #2435)
        self._jobs_lock: asyncio.Lock = asyncio.Lock()

        # Temporary file management
        self.temp_dir: Path = Path(tempfile.gettempdir()) / PROCESSING_TEMP_DIRNAME
        create_secure_temp_dir(self.temp_dir)

        # Progress-callback fan-out: see ProgressNotifier (#4250 follow-up).
        self._progress: ProgressNotifier = ProgressNotifier(self.jobs, self._jobs_lock)

        # Per-job cooperative cancellation tokens; see job_execution.py /
        # job_lifecycle.py (#4496/#4759).
        self._cancel_events: dict[str, threading.Event] = {}

    # Delegate to the worker's objects (stable identity, so a test that
    # mutates ._tasks / .job_queue directly still works, #4250).

    @property
    def _tasks(self) -> dict[str, "asyncio.Task[None]"]:
        return self._worker._tasks

    @property
    def _active_job_count(self) -> int:
        return self._worker.active_job_count

    @_active_job_count.setter
    def _active_job_count(self, value: int) -> None:
        # Some tests mutate this directly to simulate slot occupancy (#2459).
        self._worker.active_job_count = value

    @property
    def _concurrency_semaphore(self) -> asyncio.Semaphore:
        return self._worker._concurrency_semaphore

    @property
    def processors(self) -> dict[str, HybridProcessor]:
        return self._pool.processors

    @property
    def progress_callbacks(self) -> dict[str, list[Callable[..., Any]]]:
        return self._progress.callbacks

    @progress_callbacks.setter
    def progress_callbacks(self, value: dict[str, list[Callable[..., Any]]]) -> None:
        # Some tests reset this directly between cases (#3868 test fixtures).
        self._progress.callbacks = value

    async def _construct_processor(self, config: UnifiedConfig) -> HybridProcessor:
        """Factory for the ProcessorPool, kept on the engine so HybridProcessor
        stays patchable in tests. Offloaded to a thread: construction is
        CPU-bound (200-500 ms) and the pool lock is held during the call."""
        return await asyncio.to_thread(HybridProcessor, config)

    async def create_job(
        self,
        input_path: str,
        settings: dict[str, Any],
        mode: str = "adaptive",
        reference_path: str | None = None
    ) -> ProcessingJob:
        """Create a new processing job. Thin delegate; see job_lifecycle.py."""
        return await _create_job_impl(self, input_path, settings, mode, reference_path)

    async def submit_job(self, job: ProcessingJob) -> str:
        """Submit a job to the processing queue.

        Raises:
            asyncio.QueueFull: when the queue is at capacity (callers should
                translate this to an HTTP 503 response).
        """
        try:
            self.job_queue.put_nowait(job)
        except asyncio.QueueFull:
            async with self._jobs_lock:
                self.jobs.pop(job.job_id, None)
            await self.job_store.forget([job.job_id])
            raise
        return job.job_id

    async def restore_jobs(self) -> int:
        """Reload persisted jobs after a restart (#5278). See JobStore.restore."""
        restored = await self.job_store.restore(self.completed_job_ttl_hours)
        async with self._jobs_lock:
            for job in restored:
                self.jobs.setdefault(job.job_id, job)
        return len(restored)

    async def get_job(self, job_id: str) -> ProcessingJob | None:
        """Get job by ID"""
        async with self._jobs_lock:
            return self.jobs.get(job_id)

    # Thin wrappers delegating to self._progress (#4250 follow-up).
    async def register_progress_callback(self, job_id: str, callback: Callable[..., Any]) -> None:
        """Add a callback for job progress updates. See ProgressNotifier.register."""
        await self._progress.register(job_id, callback)

    async def unregister_progress_callback(
        self, job_id: str, callback: Callable[..., Any] | None = None
    ) -> None:
        """Remove progress callbacks for `job_id`. See ProgressNotifier.unregister."""
        await self._progress.unregister(job_id, callback)

    async def _notify_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Notify every subscriber registered for this job. See ProgressNotifier.notify."""
        await self._progress.notify(job_id, progress, message)

    # Thin wrappers delegating to self._pool (#4250).
    def _get_processor_cache_key(self, mode: str, config: UnifiedConfig) -> str:
        return self._pool.cache_key(mode, config)

    async def _get_or_create_processor(self, mode: str, config: UnifiedConfig) -> HybridProcessor:
        return await self._pool.get_or_create(mode, config)

    async def _return_processor(self, mode: str, config: UnifiedConfig, processor: HybridProcessor) -> None:
        await self._pool.return_to_cache(mode, config, processor)

    async def _discard_processor(self, processor: HybridProcessor) -> None:
        """Close and drop a processor without returning it to the pool (#4727)."""
        await self._pool.discard(processor)

    async def close_processor_pool(self) -> None:
        """Drain and close every cached processor on shutdown. Thin delegate;
        see ProcessorPool.close_all() (#5061). Called from startup.py."""
        await self._pool.close_all()

    async def _cleanup_processor(
        self,
        job: ProcessingJob,
        config: UnifiedConfig,
        processor: HybridProcessor,
        poisoned: bool,
    ) -> None:
        """Return or discard an owned processor. Thin delegate; see ProcessorPool.cleanup()."""
        await self._pool.cleanup(job.job_id, job.mode, config, processor, poisoned)

    # Thin delegates to job_config.py/job_execution.py/job_finalize.py, kept
    # as bound methods for patch.object() in test_process_job_nonblocking.py
    # / test_processor_return_on_failure.py (#4250 follow-up).
    def _create_processor_config(
        self, job: ProcessingJob, sample_rate: int
    ) -> UnifiedConfig:
        return create_processor_config(job, sample_rate)

    async def _prepare_job(
        self, job: ProcessingJob
    ) -> tuple[np.ndarray, int, UnifiedConfig, HybridProcessor]:
        return await prepare_job(self, job)

    async def _execute_job(
        self,
        job: ProcessingJob,
        audio: np.ndarray,
        sample_rate: int,
        processor: HybridProcessor,
    ) -> np.ndarray:
        return await execute_job(self, job, audio, sample_rate, processor)

    def _finalize_job(
        self,
        job: ProcessingJob,
        audio_data: np.ndarray,
        sample_rate: int,
        processor: HybridProcessor,
    ) -> None:
        finalize_job(job, audio_data, sample_rate, processor)

    async def process_job(self, job: ProcessingJob) -> None:
        """Process a single job. Thin delegate; kept as a bound method for
        patch.object(engine, "process_job", ...) — see job_lifecycle.py."""
        await _process_job_impl(self, job)

    async def stop_worker(self) -> None:
        """Stop the worker loop and cancel all in-progress jobs. See JobWorker."""
        await self._worker.stop()

    async def start_worker(self) -> None:
        """Start the job processing worker. See JobWorker."""
        await self._worker.start()

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job. Thin delegate; see job_lifecycle.py.

        For QUEUED jobs: marks the status so process_job() skips it.
        For PROCESSING jobs: cancels the asyncio Task, which injects
        CancelledError at the next await point (fixes #2217).
        """
        return await _cancel_job_impl(self, job_id)

    async def cleanup_old_jobs(self, max_age_hours: float = 24) -> int:
        """Clean up old completed jobs and their files. Thin delegate; see
        job_cleanup.cleanup_expired_jobs().

        Returns:
            int: Number of jobs removed
        """
        upload_dir = Path(tempfile.gettempdir()) / UPLOAD_TEMP_DIRNAME
        return await cleanup_expired_jobs(
            self.jobs, self._jobs_lock, self.progress_callbacks, upload_dir, max_age_hours,
            on_removed=self.job_store.forget,
        )

    def get_all_jobs(self) -> list[ProcessingJob]:
        """Get all jobs"""
        return list(self.jobs.values())

    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status. Populates both `total`/`cancelled` (the
        QueueStatusResponse fields) and `total_jobs` (the older extra field
        callers/tests already read) so the two agree instead of the client
        seeing `total=0` next to a populated `total_jobs` (#3886)."""
        # Snapshot to avoid RuntimeError if cleanup_old_jobs mutates self.jobs concurrently (#2435)
        jobs = list(self.jobs.values())
        return {
            "total_jobs": len(jobs),
            "total": len(jobs),
            "queued": len([j for j in jobs if j.status == ProcessingStatus.QUEUED]),
            "processing": self._active_job_count,  # replaces ._value private attr (#2459)
            "completed": len([j for j in jobs if j.status == ProcessingStatus.COMPLETED]),
            "failed": len([j for j in jobs if j.status == ProcessingStatus.FAILED]),
            "cancelled": len([j for j in jobs if j.status == ProcessingStatus.CANCELLED]),
            "max_concurrent": self.max_concurrent_jobs,
            "max_queue_size": self.max_queue_size,
            "queue_full": self.job_queue.full(),
        }
