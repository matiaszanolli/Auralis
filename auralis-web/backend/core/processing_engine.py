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
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from collections.abc import Callable

import numpy as np

# Add parent directory to path for Auralis imports
sys.path.append(str(Path(__file__).parent.parent.parent))


from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.config import UnifiedConfig
from auralis.io.processing import resample_audio
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio

# ProcessingJob / ProcessingStatus live in job_models so the worker can import
# them without a circular dependency; re-exported here so existing
# `from core.processing_engine import ProcessingJob, ProcessingStatus` keeps
# working (#4250).
from core.job_models import ProcessingJob, ProcessingStatus
from core.processor_pool import ProcessorPool
from core.job_worker import JobWorker

__all__ = [
    "ProcessingEngine",
    "ProcessingJob",
    "ProcessingStatus",
    "_safe_error_message",
]


logger = logging.getLogger(__name__)

# Maps exception types to user-safe messages.  Order matters: first
# match wins, so put specific types before broad ones.
_ERROR_CATEGORIES: list[tuple[type[BaseException], str]] = [
    (FileNotFoundError, "Audio file not found"),
    (PermissionError, "Permission denied accessing audio file"),
    (OSError, "Audio file could not be read"),
    (ValueError, "Invalid audio data or parameters"),
    (MemoryError, "Insufficient memory to process audio"),
]

try:
    from encoding.wav_encoder import WAVEncoderError
    _ERROR_CATEGORIES.insert(0, (WAVEncoderError, "Audio encoding failed"))
except ImportError:
    pass


def _safe_error_message(exc: Exception) -> str:
    """Return a user-safe error category for *exc*.

    The raw exception is intentionally NOT included — callers must log
    it separately so internal paths / library internals stay server-side.
    """
    for exc_type, message in _ERROR_CATEGORIES:
        if isinstance(exc, exc_type):
            return message
    return "An unexpected error occurred during processing"


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
        self.temp_dir: Path = Path(tempfile.gettempdir()) / "auralis_processing"
        self.temp_dir.mkdir(exist_ok=True)

        # Progress callbacks
        self.progress_callbacks: dict[str, Callable[..., Any]] = {}

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
        """Create a new processing job"""

        job_id = str(uuid.uuid4())

        # Generate output path
        output_format = settings.get("output_format", "wav")
        output_path = str(self.temp_dir / f"{job_id}_processed.{output_format}")

        job = ProcessingJob(
            job_id=job_id,
            input_path=input_path,
            output_path=output_path,
            settings=settings,
            mode=mode
        )

        # Store reference path if hybrid mode
        if mode == "hybrid" and reference_path:
            job.settings["reference_path"] = reference_path

        async with self._jobs_lock:
            self.jobs[job_id] = job

        return job

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

    async def register_progress_callback(self, job_id: str, callback: Callable[..., Any]) -> None:
        """Register a callback for job progress updates"""
        async with self._jobs_lock:
            self.progress_callbacks[job_id] = callback

    async def unregister_progress_callback(self, job_id: str) -> None:
        """Remove a progress callback (e.g. on WebSocket disconnect)."""
        async with self._jobs_lock:
            self.progress_callbacks.pop(job_id, None)

    async def _notify_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Notify progress callback.

        Silences and removes callbacks that raise (e.g. dead WebSocket),
        so a WS disconnect does not abort the processing job (#3325).
        """
        async with self._jobs_lock:
            job = self.jobs.get(job_id)
            if job:
                job.progress = progress
            callback = self.progress_callbacks.get(job_id)

        if job and callback:
            try:
                await callback(job_id, progress, message)
            except Exception:
                logger.debug("Progress callback for job %s failed, removing", job_id)
                async with self._jobs_lock:
                    self.progress_callbacks.pop(job_id, None)

    # Processor-pool operations delegate to self._pool (#4250). Thin wrappers are
    # kept so any caller/test using the engine-level names still works.
    def _get_processor_cache_key(self, mode: str, config: UnifiedConfig) -> str:
        return self._pool.cache_key(mode, config)

    async def _get_or_create_processor(self, mode: str, config: UnifiedConfig) -> HybridProcessor:
        return await self._pool.get_or_create(mode, config)

    async def _return_processor(self, mode: str, config: UnifiedConfig, processor: HybridProcessor) -> None:
        await self._pool.return_to_cache(mode, config, processor)

    def _create_processor_config(self, job: ProcessingJob) -> UnifiedConfig:
        """
        Create UnifiedConfig from job settings.

        Currently supports ONLY adaptive / reference / hybrid mode selection.
        The offline-mastering pipeline (HybridProcessor.process) drives EQ /
        dynamics / level / genre from its OWN internal fingerprint analysis
        via ContinuousMode — it does NOT read from `config.adaptive.eq_gains`,
        `config.adaptive.compressor`, `config.adaptive.target_lufs`,
        `config.adaptive.gain`, or `config.adaptive.genre_override`.

        Until those readers exist (tracked as the wire-up follow-up for
        #3490), any "eq" / "dynamics" / "level_matching" / "genre_override"
        keys in `job.settings` are logged at INFO and ignored. Prior code
        silently wrote them into dynamic attributes on `AdaptiveConfig` —
        the UI looked responsive while changing nothing audible.
        """

        config = UnifiedConfig()

        # Set processing mode
        if job.mode == "adaptive":
            config.set_processing_mode("adaptive")
        elif job.mode == "reference":
            config.set_processing_mode("reference")
        elif job.mode == "hybrid":
            config.set_processing_mode("hybrid")

        # Log (don't silently drop) any UI settings the engine cannot consume.
        # The frontend should hide these controls until the engine reads them
        # (see #3490 follow-up). Logging at INFO so developers see it in dev.
        unsupported: list[str] = []
        # Guard each lookup against an explicit `None` value, not just a missing
        # key — ProcessingSettings.model_dump() always includes "eq"/"dynamics"/
        # "fingerprint" with a None default when the client doesn't set them, so
        # `"eq" in job.settings` is True while `job.settings["eq"]` is None and
        # `.get()` on it raises AttributeError (fixes #3819, found while writing
        # the first end-to-end test to drive a real ProcessingEngine — every job
        # submitted with default settings failed with "unexpected error").
        fingerprint_settings = job.settings.get("fingerprint")
        if fingerprint_settings and fingerprint_settings.get("enabled"):
            # parameter_mapper.generate_mastering_parameters used to be called
            # here and its output written to dead config attrs. Kept for
            # reference in case a future wire-up needs the intermediate dict.
            unsupported.append("fingerprint (parameter-mapper output is currently unread by engine)")
        eq_settings = job.settings.get("eq")
        if eq_settings and eq_settings.get("enabled"):
            unsupported.append("eq")
        dynamics_settings = job.settings.get("dynamics")
        if dynamics_settings and dynamics_settings.get("enabled"):
            unsupported.append("dynamics")
        level_settings = job.settings.get("level_matching") or job.settings.get("levelMatching")
        if level_settings and level_settings.get("enabled"):
            unsupported.append("level_matching")
        if "genre_override" in job.settings:
            unsupported.append("genre_override")

        if unsupported:
            logger.info(
                "Job %s: requested settings (%s) are accepted but not consumed "
                "by the offline pipeline — HybridProcessor drives these from "
                "internal fingerprint analysis. See #3490 for the wire-up plan.",
                job.job_id,
                ", ".join(unsupported),
            )

        return config

    async def _prepare_job(
        self, job: ProcessingJob
    ) -> tuple[np.ndarray, int, UnifiedConfig, HybridProcessor]:
        """Mark the job started, load its input audio, build its config, and
        acquire an exclusively-owned processor (#4250). The processor is popped
        from the pool (#3201) and MUST be returned by the caller — process_job
        does so on every exit path."""
        job.status = ProcessingStatus.PROCESSING
        job.started_at = datetime.now()

        await self._notify_progress(job.job_id, 0.0, "Loading audio file...")

        # Register a cooperative cancellation token so cancel_job() can abort an
        # in-flight FFmpeg decode running in the to_thread worker (#4496).
        cancel_event = self._cancel_events.setdefault(job.job_id, threading.Event())

        # Load input audio — disk-bound; offload to thread (fixes #2319)
        audio, sample_rate = await asyncio.to_thread(
            load_audio, job.input_path, cancel_event=cancel_event
        )

        await self._notify_progress(job.job_id, 20.0, "Analyzing audio content...")

        # Create processor config
        config = self._create_processor_config(job)

        # Get or create processor — exclusively owned until returned (#3201)
        processor = await self._get_or_create_processor(job.mode, config)

        return audio, sample_rate, config, processor

    async def _execute_job(
        self,
        job: ProcessingJob,
        audio: np.ndarray,
        sample_rate: int,
        processor: HybridProcessor,
    ) -> np.ndarray:
        """Reset processor state, run the timeout-guarded DSP process, and save
        the output. Returns the processed audio array (#4250)."""
        await self._notify_progress(job.job_id, 40.0, "Processing audio...")

        # Reset EQ state before each job so cached processors don't bleed
        # the previous track's psychoacoustic EQ curve into the new track (fixes #2400).
        # reset_realtime_eq() only clears the real-time EQ path's own EQ; the
        # adaptive/continuous path uses a separate main psychoacoustic EQ whose
        # gain-smoothing state also has to be reset here (completes #2400).
        processor.reset_realtime_eq()
        processor.reset_dynamics()
        processor.reset_psychoacoustic_eq()

        # Process audio — CPU-bound; offload to thread (fixes #2319)
        # Wrap with wait_for so a hung DSP/Rust call cannot hold the
        # semaphore slot indefinitely (fixes #2747).
        timeout = self.processing_timeout
        if job.mode == "reference" or job.mode == "hybrid":
            # Load reference audio if needed
            reference_path = job.settings.get("reference_path")
            if reference_path and Path(reference_path).exists():
                # Same cooperative-cancel token as the input load (#4496 SIBLING):
                # the reference decode is the identical to_thread(load_audio)
                # pattern and must also stop its FFmpeg child on cancel.
                cancel_event = self._cancel_events.get(job.job_id)
                reference_audio, reference_sr = await asyncio.to_thread(
                    load_audio, reference_path, cancel_event=cancel_event
                )
                # Resample reference if needed — CPU-bound; offload to thread
                if reference_sr != sample_rate:
                    reference_audio = await asyncio.to_thread(
                        resample_audio, reference_audio, reference_sr, sample_rate
                    )
                result = await asyncio.wait_for(
                    asyncio.to_thread(processor.process, audio, reference_audio),
                    timeout=timeout,
                )
            else:
                # Fall back to adaptive mode if no reference
                result = await asyncio.wait_for(
                    asyncio.to_thread(processor.process, audio),
                    timeout=timeout,
                )
        else:
            # Adaptive mode
            result = await asyncio.wait_for(
                asyncio.to_thread(processor.process, audio),
                timeout=timeout,
            )

        await self._notify_progress(job.job_id, 80.0, "Saving processed audio...")

        # Save output audio (output_format is recorded in _finalize_job).
        bit_depth = job.settings.get("bit_depth", 16)

        # Determine subtype based on bit depth
        subtype_map: dict[int, str] = {16: 'PCM_16', 24: 'PCM_24', 32: 'PCM_32'}
        subtype = subtype_map.get(bit_depth, 'PCM_16')

        # HybridProcessor.process() returns a bare np.ndarray. Earlier
        # versions of this code accessed `result.audio` / `result.lufs` /
        # `result.processing_time` etc., which silently raised
        # AttributeError on every successful job and routed every job
        # through the catch-all "An unexpected error occurred" branch
        # (fixes #3489). Pull richer telemetry from the processor's
        # last_content_profile / get_processing_info() in _finalize_job.
        if not isinstance(result, np.ndarray):
            raise TypeError(
                f"HybridProcessor.process() returned {type(result).__name__}, "
                "expected numpy.ndarray"
            )
        audio_data: np.ndarray = result

        # Disk-bound write; offload to thread (fixes #2319)
        await asyncio.to_thread(
            save,
            file_path=job.output_path,
            audio_data=audio_data,
            sample_rate=sample_rate,
            subtype=subtype,
        )

        await self._notify_progress(job.job_id, 100.0, "Processing complete!")

        return audio_data

    def _finalize_job(
        self,
        job: ProcessingJob,
        audio_data: np.ndarray,
        sample_rate: int,
        processor: HybridProcessor,
    ) -> None:
        """Collect best-effort telemetry and record the completed result (#4250)."""
        # Extract optional telemetry from processor side-channels (best-effort).
        processing_time: float | None = None
        genre_detected: str | None = None
        lufs: float | None = None
        try:
            proc_info = processor.get_processing_info() if hasattr(processor, "get_processing_info") else None
            if isinstance(proc_info, dict):
                processing_time = proc_info.get("last_processing_time") or proc_info.get("processing_time")
                lufs_val = proc_info.get("last_lufs") or proc_info.get("lufs")
                if lufs_val is not None:
                    lufs = float(lufs_val)
            content_profile = getattr(processor, "last_content_profile", None)
            if content_profile is not None:
                genre_detected = getattr(content_profile, "genre", None) or genre_detected
        except Exception:
            # Telemetry is non-critical; never let it fail the job.
            pass

        output_format = job.settings.get("output_format", "wav")
        bit_depth = job.settings.get("bit_depth", 16)

        # Store result metadata — use filename-only for output_file so
        # the absolute temp path never appears in API responses (#3848,
        # sibling of the input_file sanitisation in #3322).
        job.result_data = {
            "output_file": Path(job.output_path).name,
            "sample_rate": int(sample_rate),
            "duration": float(len(audio_data) / sample_rate),
            "format": output_format,
            "bit_depth": bit_depth,
            "processing_time": processing_time,
            "genre_detected": genre_detected,
            "lufs": lufs,
        }

        job.status = ProcessingStatus.COMPLETED
        job.completed_at = datetime.now()

    async def process_job(self, job: ProcessingJob) -> None:
        """
        Process a single job using the HybridProcessor
        """
        # Guard: if cancel_job() fired before the worker started this job, skip it.
        if job.status == ProcessingStatus.CANCELLED:
            return

        processor = None
        config = None
        try:
            audio, sample_rate, config, processor = await self._prepare_job(job)
            audio_data = await self._execute_job(job, audio, sample_rate, processor)
            self._finalize_job(job, audio_data, sample_rate, processor)

            # Return processor to cache for reuse (#3201)
            await self._return_processor(job.mode, config, processor)

        except TimeoutError:
            # asyncio.wait_for raised TimeoutError — the DSP call hung.
            # Mark FAILED so the semaphore slot is released (fixes #2747).
            job.status = ProcessingStatus.FAILED
            job.error_message = (
                f"Processing timed out after {self.processing_timeout:.0f}s"
            )
            job.completed_at = datetime.now()
            if processor is not None and config is not None:
                await self._return_processor(job.mode, config, processor)

            await self._notify_progress(
                job.job_id, 100.0, job.error_message
            )

        except asyncio.CancelledError:
            # task.cancel() was called — mark cancelled and re-raise so asyncio
            # correctly records the task as cancelled (fixes #2217).
            if job.status == ProcessingStatus.PROCESSING:
                job.status = ProcessingStatus.CANCELLED
                job.completed_at = datetime.now()
            if processor is not None and config is not None:
                await self._return_processor(job.mode, config, processor)
            raise

        except Exception as e:
            job.status = ProcessingStatus.FAILED
            # Log full exception for debugging; expose only a safe
            # category string to the API caller (fixes #2741).
            logger.error(
                "Processing job %s failed: %s",
                job.job_id, e, exc_info=True,
            )
            job.error_message = _safe_error_message(e)
            job.completed_at = datetime.now()

            await self._notify_progress(
                job.job_id, 100.0, f"Processing failed: {job.error_message}"
            )
        finally:
            # Drop the cancellation token now the job is terminal so the
            # registry cannot leak an entry per job (#4496).
            self._cancel_events.pop(job.job_id, None)


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

        For QUEUED jobs: marks the status so process_job() skips it.
        For PROCESSING jobs: cancels the asyncio Task, which injects
        CancelledError at the next await point (fixes #2217).
        """
        async with self._jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                return False

            if job.status not in [ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING]:
                return False

            job.status = ProcessingStatus.CANCELLED
            job.completed_at = datetime.now()
            self.progress_callbacks.pop(job_id, None)

        # Signal the loader to terminate any in-flight FFmpeg child (#4496).
        # task.cancel() alone injects CancelledError only at the next await, but
        # the task is parked inside a to_thread FFmpeg decode that cannot be
        # interrupted that way; setting the event kills the child promptly and
        # frees the worker thread. Safe to set even if no decode is in flight.
        cancel_event = self._cancel_events.get(job_id)
        if cancel_event is not None:
            cancel_event.set()

        # Cancel the asyncio Task outside the lock — task.cancel() is
        # thread-safe and the await would block under the lock.
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
        return True

    async def cleanup_old_jobs(self, max_age_hours: float = 24) -> int:
        """Clean up old completed jobs and their files.

        Protected by _jobs_lock so that concurrent invocations (worker finally-
        block vs. explicit DELETE /jobs/cleanup request) do not iterate and
        delete self.jobs simultaneously, which would raise RuntimeError in
        CPython when another coroutine modifies the dict mid-iteration (#2435).

        Returns:
            int: Number of jobs removed
        """
        now = datetime.now()
        jobs_to_remove: list[str] = []
        files_to_delete: list[Path] = []

        # Phase 1: identify expired jobs under lock (no blocking I/O)
        candidate_paths: list[tuple[Path, Path]] = []  # (output_path, input_path)
        upload_dir = Path(tempfile.gettempdir()) / "auralis_uploads"

        async with self._jobs_lock:
            for job_id, job in self.jobs.items():
                if job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.CANCELLED]:
                    if job.completed_at is not None:
                        age_hours = (now - job.completed_at).total_seconds() / 3600
                        if age_hours > max_age_hours:
                            candidate_paths.append((Path(job.output_path), Path(job.input_path)))
                            jobs_to_remove.append(job_id)

            for job_id in jobs_to_remove:
                del self.jobs[job_id]
                if job_id in self.progress_callbacks:
                    del self.progress_callbacks[job_id]

        # Phase 2: filesystem checks and deletions outside the lock (#3327)
        for output_path, input_path in candidate_paths:
            try:
                if output_path.exists():
                    files_to_delete.append(output_path)
                if input_path.exists() and input_path.is_relative_to(upload_dir):
                    files_to_delete.append(input_path)
            except OSError:
                pass  # Path check failed — skip

        for file_path in files_to_delete:
            try:
                file_path.unlink(missing_ok=True)
            except OSError as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

        return len(jobs_to_remove)

    def get_all_jobs(self) -> list[ProcessingJob]:
        """Get all jobs"""
        return list(self.jobs.values())

    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status"""
        # Snapshot to avoid RuntimeError if cleanup_old_jobs mutates self.jobs concurrently (#2435)
        jobs = list(self.jobs.values())
        return {
            "total_jobs": len(jobs),
            "queued": len([j for j in jobs if j.status == ProcessingStatus.QUEUED]),
            "processing": self._active_job_count,  # replaces ._value private attr (#2459)
            "completed": len([j for j in jobs if j.status == ProcessingStatus.COMPLETED]),
            "failed": len([j for j in jobs if j.status == ProcessingStatus.FAILED]),
            "max_concurrent": self.max_concurrent_jobs,
            "max_queue_size": self.max_queue_size,
            "queue_full": self.job_queue.full(),
        }