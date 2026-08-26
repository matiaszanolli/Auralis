#!/usr/bin/env python3

"""
Processing Engine for Auralis Web Backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles audio processing jobs using the HybridProcessor from the core Auralis system.
Manages job queue, progress tracking, and result caching.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
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

# ProcessingJob / ProcessingStatus live in job_models so the worker can import
# them without a circular dependency; re-exported here so existing
# `from core.processing_engine import ProcessingJob, ProcessingStatus` keeps
# working (#4250).
from config.limits import PROCESSING_TEMP_DIRNAME, UPLOAD_TEMP_DIRNAME
from core.job_cleanup import cleanup_expired_jobs

# _safe_error_message lives in job_error_mapping so it (and its mapping
# tables) can be tested/imported independently; re-exported here for the
# same reason ProcessingJob/ProcessingStatus are (#4250 follow-up).
from core.job_config import create_processor_config
from core.job_error_mapping import _safe_error_message

# _prepare_job/_execute_job's bodies live in job_execution.py (load_audio()/
# save() calls and all) so a test can intercept those calls at
# 'core.job_execution.load_audio' / 'core.job_execution.save' — see that
# module's docstring (#4250 follow-up).
from core.job_execution import execute_job, prepare_job
from core.job_finalize import finalize_job

# create_job/process_job/cancel_job's bodies live in job_lifecycle.py;
# the ProcessingEngine methods below are thin delegating methods
# (#4250 follow-up).
from core.job_lifecycle import cancel_job as _cancel_job_impl
from core.job_lifecycle import create_job as _create_job_impl
from core.job_lifecycle import process_job as _process_job_impl
from core.job_models import ProcessingJob, ProcessingStatus
from core.job_progress import ProgressNotifier
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
    """
    Audio processing engine that manages the job queue and executes
    adaptive mastering using the HybridProcessor
    """

    # Default ceiling for a single processor.process() call (seconds).
    # Generous enough for long tracks; short enough to unblock the queue
    # if a Rust/PyO3 call hangs (fixes #2747).
    DEFAULT_PROCESSING_TIMEOUT: float = 300.0

    def __init__(
        self,
        max_concurrent_jobs: int = 2,
        max_queue_size: int = 20,
        completed_job_ttl_hours: float = 1.0,
        processing_timeout: float | None = None,
    ) -> None:
        self.jobs: dict[str, ProcessingJob] = {}
        self.max_concurrent_jobs: int = max_concurrent_jobs
        self.max_queue_size: int = max_queue_size
        self.completed_job_ttl_hours: float = completed_job_ttl_hours
        self.processing_timeout: float = (
            processing_timeout if processing_timeout is not None else self.DEFAULT_PROCESSING_TIMEOUT
        )

        # Processor instance cache (#4250: extracted to ProcessorPool). The
        # factory keeps HybridProcessor instantiation in this module so tests
        # patching core.processing_engine.HybridProcessor still intercept it.
        self._pool: ProcessorPool = ProcessorPool(self._construct_processor)

        # Queue / concurrency / dispatch loop (#4250: extracted to JobWorker).
        self._worker: JobWorker = JobWorker(self, max_concurrent_jobs, max_queue_size)
        # Expose the worker's queue as a plain (settable) attribute — same object,
        # so submit_job/get_queue_status and the worker share one queue, while a
        # legacy test that assigns engine.job_queue still works.
        self.job_queue: "asyncio.Queue[ProcessingJob]" = self._worker.job_queue

        # Guards concurrent access to jobs / progress_callbacks (fixes #2435)
        self._jobs_lock: asyncio.Lock = asyncio.Lock()

        # Temporary file management
        self.temp_dir: Path = Path(tempfile.gettempdir()) / PROCESSING_TEMP_DIRNAME
        self.temp_dir.mkdir(exist_ok=True)

        # Progress-callback fan-out (#4250: extracted to ProgressNotifier).
        # Shares this engine's jobs dict / _jobs_lock by reference so a
        # progress tick still updates the same job objects create_job() and
        # cancel_job() mutate.
        self._progress: ProgressNotifier = ProgressNotifier(self.jobs, self._jobs_lock)

        # Per-job cooperative cancellation tokens (#4496). A job's input/reference
        # FFmpeg decode runs in a `to_thread` worker that `task.cancel()` cannot
        # interrupt; `cancel_job()` sets this event so the loader terminates the
        # in-flight FFmpeg child and frees the thread-pool slot promptly. Keyed by
        # job_id; created in `_prepare_job`, removed when the job finishes.
        self._cancel_events: dict[str, threading.Event] = {}

    # --- Worker/pool state exposed for the engine's public methods and for
    # tests that reach directly into these (e.g. test_cancel_job_stops_processing
    # mutates ._tasks / .job_queue). They delegate to the worker's objects, whose
    # identity is stable, so in-place mutation works (#4250). ---

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
        """Factory for the ProcessorPool. Kept on the engine so HybridProcessor
        is resolved from this module (patchable in tests). Construction is
        CPU-bound (200-500 ms) — offloaded to a thread so the event loop stays
        responsive while the pool lock is held."""
        return await asyncio.to_thread(HybridProcessor, config)

    async def create_job(
        self,
        input_path: str,
        settings: dict[str, Any],
        mode: str = "adaptive",
        reference_path: str | None = None
    ) -> ProcessingJob:
        """Create a new processing job.

        Thin delegate over job_lifecycle.create_job() (#4250 follow-up).
        """
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
            raise
        return job.job_id

    async def get_job(self, job_id: str) -> ProcessingJob | None:
        """Get job by ID"""
        async with self._jobs_lock:
            return self.jobs.get(job_id)

    # Progress-callback fan-out delegates to self._progress (#4250 follow-up).
    # Thin wrappers are kept so any caller/test using the engine-level names
    # still works.
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

    # Processor-pool operations delegate to self._pool (#4250). Thin wrappers are
    # kept so any caller/test using the engine-level names still works.
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
        """Drain and close every cached HybridProcessor on shutdown (#5061).

        Thin wrapper over self._pool.close_all() — the engine's own processor
        cache had no equivalent to ProcessorFactory's shutdown-time
        clear_cache(), so up to _max_cached instances were never dropped on
        restart. Inert while HybridProcessor.close() releases nothing (#4744);
        this is the plumbing for when it does not. Called from startup.py's
        shutdown handler.
        """
        await self._pool.close_all()

    async def _cleanup_processor(
        self,
        job: ProcessingJob,
        config: UnifiedConfig,
        processor: HybridProcessor,
        poisoned: bool,
    ) -> None:
        """Return or discard an owned processor without leaking it.

        Thin delegate over self._pool.cleanup() (#4250 follow-up).
        """
        await self._pool.cleanup(job.job_id, job.mode, config, processor, poisoned)

    # _create_processor_config/_prepare_job/_execute_job/_finalize_job delegate
    # to job_config.py/job_execution.py/job_finalize.py (#4250 follow-up). Thin
    # wrappers are kept — rather than importing those functions directly into
    # process_job — so `patch.object(engine, "_prepare_job"/"_execute_job"/
    # "_finalize_job"/"_create_processor_config", ...)` in
    # tests/backend/test_process_job_nonblocking.py and
    # tests/backend/test_processor_return_on_failure.py keeps working
    # unmodified: those tests replace the bound method on the instance, which
    # only works while it's an attribute directly on ProcessingEngine.
    def _create_processor_config(self, job: ProcessingJob) -> UnifiedConfig:
        return create_processor_config(job)

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
        """Process a single job using the HybridProcessor.

        Thin delegate over job_lifecycle.process_job() (#4250 follow-up).
        Kept as a real bound method — rather than importing the function
        directly into callers — so `patch.object(engine, "process_job", ...)`
        in tests/backend/test_cancel_job_stops_processing.py and the plain
        `await engine.process_job(job)` call sites across the backend test
        suite and core/job_worker.py's dispatch loop keep working unmodified.
        """
        await _process_job_impl(self, job)

    async def stop_worker(self) -> None:
        """Stop the worker loop and cancel all in-progress jobs (#4250: delegated
        to JobWorker)."""
        await self._worker.stop()

    async def start_worker(self) -> None:
        """Start the job processing worker (#4250: delegated to JobWorker).

        Jobs are dispatched as concurrent tasks up to max_concurrent_jobs; the
        semaphore inside the worker governs how many execute simultaneously and
        the loop never blocks on a running job (#2746)."""
        await self._worker.start()

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.

        Thin delegate over job_lifecycle.cancel_job() (#4250 follow-up).

        For QUEUED jobs: marks the status so process_job() skips it.
        For PROCESSING jobs: cancels the asyncio Task, which injects
        CancelledError at the next await point (fixes #2217).
        """
        return await _cancel_job_impl(self, job_id)

    async def cleanup_old_jobs(self, max_age_hours: float = 24) -> int:
        """Clean up old completed jobs and their files (#4250 follow-up:
        delegated to job_cleanup.cleanup_expired_jobs). See that function's
        docstring for the locking/offload details (#2435, #3327, #4754).

        Returns:
            int: Number of jobs removed
        """
        upload_dir = Path(tempfile.gettempdir()) / UPLOAD_TEMP_DIRNAME
        return await cleanup_expired_jobs(
            self.jobs, self._jobs_lock, self.progress_callbacks, upload_dir, max_age_hours
        )

    def get_all_jobs(self) -> list[ProcessingJob]:
        """Get all jobs"""
        return list(self.jobs.values())

    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status.

        Populates both `total`/`cancelled` (the fields QueueStatusResponse
        declares) and `total_jobs` (the pre-existing extra field several
        callers/tests already read) so the two no longer disagree (#3886) --
        the schema's `extra="allow"` meant a client saw `total=0` next to
        `total_jobs=N` and `cancelled=0` even when cancelled jobs existed,
        with no way to know which was authoritative. `total_jobs` is kept
        rather than removed: it predates the schema fields and is still the
        one asserted by existing tests/callers.
        """
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
