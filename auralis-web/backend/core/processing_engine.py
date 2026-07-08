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
import uuid
from datetime import datetime
from enum import Enum
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


class ProcessingStatus(str, Enum):
    """Processing job status"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingJob:
    """Represents a single audio processing job"""

    def __init__(
        self,
        job_id: str,
        input_path: str,
        output_path: str,
        settings: dict[str, Any],
        mode: str = "adaptive"
    ):
        self.job_id = job_id
        self.input_path = input_path
        self.output_path = output_path
        self.settings = settings
        self.mode = mode  # "adaptive", "reference", "hybrid"

        self.status = ProcessingStatus.QUEUED
        self.progress = 0.0
        self.error_message: str | None = None
        self.result_data: dict[str, Any] | None = None

        self.created_at = datetime.now()
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert job to dictionary for API responses.

        Exposes filenames only (no absolute paths) to avoid leaking
        server-side directory structure (#3322).
        """
        return {
            "job_id": self.job_id,
            "input_file": Path(self.input_path).name,
            "output_file": Path(self.output_path).name,
            "mode": self.mode,
            "status": self.status.value,
            "progress": self.progress,
            "error_message": self.error_message,
            "result_data": self.result_data,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


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
        self.job_queue: asyncio.Queue[ProcessingJob] = asyncio.Queue(maxsize=max_queue_size)

        # Semaphore is the single source of truth for concurrency limiting.
        # Replaces the busy-wait loop in start_worker (fixes #2332) and the
        # unsynchronised active_jobs counter (fixes #2299).
        self._concurrency_semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent_jobs)

        # Public counter incremented after semaphore.acquire() and decremented
        # in the finally block of start_worker.  Replaces the fragile
        # `semaphore._value` CPython implementation detail (#2459).
        self._active_job_count: int = 0

        # Processing components
        self.processors: dict[str, HybridProcessor] = {}

        # Locks — guards concurrent access to the two shared dicts (fixes #2320, #2435)
        self._processor_lock: asyncio.Lock = asyncio.Lock()
        self._jobs_lock: asyncio.Lock = asyncio.Lock()

        # Temporary file management
        self.temp_dir: Path = Path(tempfile.gettempdir()) / "auralis_processing"
        self.temp_dir.mkdir(exist_ok=True)

        # Progress callbacks
        self.progress_callbacks: dict[str, Callable[..., Any]] = {}

        # Per-job asyncio Tasks so cancel_job() can stop them (fixes #2217)
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._stopping: bool = False
        self._worker_task: asyncio.Task[None] | None = None

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

    def _get_processor_cache_key(self, mode: str, config: UnifiedConfig) -> str:
        """
        Generate a cache key for processor instance caching.

        Processors can be reused across jobs if they have identical:
        - Processing mode (adaptive, reference, hybrid)
        - Key configuration parameters (sample rate, EQ target, dynamics params)

        This avoids expensive reinitialization for repeated configurations.

        Args:
            mode: Processing mode string
            config: UnifiedConfig instance

        Returns:
            Cache key string
        """
        import hashlib
        # Include mode, sample rate, adaptive mode, and an explicit set of
        # the actually-relevant settings (#2218 + fixes #3528 / BE-NEW-70).
        # Prior code hashed `vars(config)`; the @dataclass __repr__ on
        # AdaptiveConfig only covers declared fields, so dynamically-attached
        # attributes (eq_gains, compressor, target_lufs, gain, genre_override)
        # were silently excluded from the hash and two jobs with different
        # EQ settings produced identical cache keys. Also: `processing_mode`
        # is not a UnifiedConfig attribute — that slot collapsed to
        # 'unknown' for every key. Switched to config.adaptive.mode.
        adaptive = getattr(config, "adaptive", None)
        key_parts: list[str] = [
            mode,
            str(config.internal_sample_rate),
            getattr(adaptive, "mode", "unknown") if adaptive else "unknown",
            getattr(config, "mastering_profile", ""),
            repr(getattr(adaptive, "eq_gains", None)) if adaptive else "",
            repr(getattr(adaptive, "compressor", None)) if adaptive else "",
            repr(getattr(adaptive, "target_lufs", None)) if adaptive else "",
            repr(getattr(adaptive, "gain", None)) if adaptive else "",
            repr(getattr(adaptive, "genre_override", None)) if adaptive else "",
        ]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()

    async def _get_or_create_processor(self, mode: str, config: UnifiedConfig) -> HybridProcessor:
        """
        Get cached processor instance or create new one.

        Processor instances are expensive to create because they:
        - Initialize analysis modules
        - Pre-compute window functions
        - Set up DSP stage instances

        Caching reusable processors provides 200-500ms speedup per job.

        Access is serialised with _processor_lock so that:
        - Concurrent jobs with identical config share one HybridProcessor instead
          of each allocating ~200 MB.
        - FIFO eviction is never interleaved with a concurrent read or write,
          eliminating the "RuntimeError: dictionary changed size during iteration"
          reported in #2320.
        - HybridProcessor.__init__ (200-500 ms, CPU-bound) is offloaded to a
          thread so the event loop stays responsive while the lock is held.

        Args:
            mode: Processing mode
            config: UnifiedConfig for processor

        Returns:
            HybridProcessor instance (cached or new)
        """
        async with self._processor_lock:
            cache_key = self._get_processor_cache_key(mode, config)

            # Pop from cache so no concurrent job shares this instance (#3201).
            # Caller must return it via _return_processor() after use.
            if cache_key in self.processors:
                return self.processors.pop(cache_key)

            # Construction is CPU-bound (200-500 ms) — run off the event loop
            # so we don't stall request handling while the lock is held.
            processor = await asyncio.to_thread(HybridProcessor, config)

            return processor

    async def _return_processor(self, mode: str, config: 'UnifiedConfig', processor: 'HybridProcessor') -> None:
        """Return a processor to the cache after job completion (#3201)."""
        async with self._processor_lock:
            cache_key = self._get_processor_cache_key(mode, config)
            self.processors[cache_key] = processor

            # Keep cache size bounded (max 5 different processor configurations).
            if len(self.processors) > 5:
                cache_keys = list(self.processors)
                if cache_keys:
                    self.processors.pop(cache_keys[0], None)

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
            job.status = ProcessingStatus.PROCESSING
            job.started_at = datetime.now()

            await self._notify_progress(job.job_id, 0.0, "Loading audio file...")

            # Load input audio — disk-bound; offload to thread (fixes #2319)
            audio, sample_rate = await asyncio.to_thread(load_audio, job.input_path)

            await self._notify_progress(job.job_id, 20.0, "Analyzing audio content...")

            # Create processor config
            config = self._create_processor_config(job)

            # Get or create processor — exclusively owned until returned (#3201)
            processor = await self._get_or_create_processor(job.mode, config)

            await self._notify_progress(job.job_id, 40.0, "Processing audio...")

            # Reset EQ state before each job so cached processors don't bleed
            # the previous track's psychoacoustic EQ curve into the new track (fixes #2400).
            processor.reset_realtime_eq()
            processor.reset_dynamics()

            # Process audio — CPU-bound; offload to thread (fixes #2319)
            # Wrap with wait_for so a hung DSP/Rust call cannot hold the
            # semaphore slot indefinitely (fixes #2747).
            timeout = self.processing_timeout
            if job.mode == "reference" or job.mode == "hybrid":
                # Load reference audio if needed
                reference_path = job.settings.get("reference_path")
                if reference_path and Path(reference_path).exists():
                    reference_audio, reference_sr = await asyncio.to_thread(
                        load_audio, reference_path
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

            # Save output audio
            output_format = job.settings.get("output_format", "wav")
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
            # last_content_profile / get_processing_info() instead.
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


    async def _run_job(self, job: ProcessingJob) -> None:
        """Run a single job inside a concurrency slot, then clean up.

        Slot lifecycle is tracked via the local `acquired` flag so a
        CancelledError raised inside `acquire()` (queue full, then task
        cancelled while waiting) does NOT enter the finally with the
        semaphore unbalanced. Prior code unconditionally released, which
        would silently raise the effective concurrency cap above
        max_concurrent_jobs on every cancel-during-acquire (#3531 /
        BE-NEW-73).
        """
        acquired = False
        try:
            await self._concurrency_semaphore.acquire()
            acquired = True
            self._active_job_count += 1

            task = asyncio.current_task()
            if task is not None:
                self._tasks[job.job_id] = task

            try:
                await self.process_job(job)
            except asyncio.CancelledError:
                if job.status != ProcessingStatus.CANCELLED:
                    raise
        finally:
            self._tasks.pop(job.job_id, None)
            if acquired:
                self._active_job_count = max(0, self._active_job_count - 1)
                self._concurrency_semaphore.release()
            await self.cleanup_old_jobs(self.completed_job_ttl_hours)

    async def stop_worker(self) -> None:
        """Stop the worker loop and cancel all in-progress jobs.

        Cancels all running tasks, drains the queue, and signals the
        start_worker loop to exit via the _stopping flag.
        """
        self._stopping = True
        logger.info("Stopping processing engine worker...")

        # Cancel all in-progress tasks
        for job_id, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
                job = self.jobs.get(job_id)
                if job and job.status == ProcessingStatus.PROCESSING:
                    job.status = ProcessingStatus.CANCELLED
                    job.completed_at = datetime.now()

        # Drain the queue
        while not self.job_queue.empty():
            try:
                job = self.job_queue.get_nowait()
                job.status = ProcessingStatus.CANCELLED
                job.completed_at = datetime.now()
            except asyncio.QueueEmpty:
                break

        # Cancel the worker task itself
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        logger.info("Processing engine worker stopped")

    async def start_worker(self) -> None:
        """Start the job processing worker.

        Jobs are dispatched as concurrent tasks up to max_concurrent_jobs.
        The semaphore inside _run_job governs how many execute simultaneously;
        the worker loop itself never blocks on a running job (#2746).
        """
        self._stopping = False
        self._worker_task = asyncio.current_task()
        from helpers import spawn_background_task

        while not self._stopping:
            try:
                job = await self.job_queue.get()
                # Fire-and-forget: _run_job acquires a semaphore slot and
                # cleans up after itself.  The worker loop immediately
                # returns to dequeue the next job.  spawn_background_task
                # attaches a done-callback so an unhandled exception inside
                # _run_job is logged rather than silently swallowed
                # (fixes #3512 / BE-NEW-54).
                spawn_background_task(
                    self._run_job(job), name=f"_run_job:{job.job_id}"
                )
            except Exception as e:
                logger.exception(f"Worker error: {e}")
                await asyncio.sleep(1)

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