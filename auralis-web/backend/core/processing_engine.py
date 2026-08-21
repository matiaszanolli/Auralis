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
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

# Add parent directory to path for Auralis imports
sys.path.append(str(Path(__file__).parent.parent.parent))


from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.io.processing import resample_audio
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio
from auralis.utils.logging import Code, ModuleError

# ProcessingJob / ProcessingStatus live in job_models so the worker can import
# them without a circular dependency; re-exported here so existing
# `from core.processing_engine import ProcessingJob, ProcessingStatus` keeps
# working (#4250).
from config.limits import PROCESSING_TEMP_DIRNAME, UPLOAD_TEMP_DIRNAME
from core.encoding import WAVEncoderError
from core.job_models import ProcessingJob, ProcessingStatus
from core.job_worker import JobWorker
from core.processor_pool import ProcessorPool

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
    # #5147: WAVEncoderError used to be appended here inside a
    # `try: from encoding.wav_encoder import ... except ImportError: pass`,
    # because that module was only importable when auralis-web/backend
    # happened to be on sys.path. Any environment where that failed silently
    # lost the mapping and reported encoder failures under the generic
    # message. It now comes from the core.encoding package, which is a normal
    # relative sibling and cannot fail to import, so it is stated inline.
    (WAVEncoderError, "Audio encoding failed"),
    (FileNotFoundError, "Audio file not found"),
    (PermissionError, "Permission denied accessing audio file"),
    (OSError, "Audio file could not be read"),
    (ValueError, "Invalid audio data or parameters"),
    (MemoryError, "Insufficient memory to process audio"),
]

# auralis.io.unified_loader (and its loaders/ siblings) raise ModuleError — a
# bare Exception subclass — for every load failure instead of a stdlib
# exception type, so it never matched _ERROR_CATEGORIES above and every load
# failure collapsed into the generic fallback (#4769). ModuleError.code is the
# formatted "<Code.* value>: <detail>" string, so match on its prefix rather
# than isinstance. Order matters: first match wins.
_MODULE_ERROR_CATEGORIES: list[tuple[str, str]] = [
    (Code.ERROR_FILE_NOT_FOUND, "Audio file not found"),
    (Code.ERROR_EMPTY_FILE, "Audio file is empty"),
    (Code.ERROR_EMPTY_AUDIO, "Audio file contains no audio data"),
    (Code.ERROR_UNSUPPORTED_FORMAT, "Unsupported audio format"),
    (Code.ERROR_INVALID_SAMPLE_RATE, "Invalid audio sample rate"),
    (Code.ERROR_INVALID_AUDIO, "Invalid or corrupted audio data"),
    (Code.ERROR_TRUNCATED_FILE, "Audio file appears to be truncated or incomplete"),
    (Code.ERROR_CORRUPTED, "Audio file is corrupted or unsupported"),
    (Code.ERROR_FFMPEG_NOT_FOUND, "Audio decoder unavailable on server"),
    (Code.ERROR_FFMPEG_TIMEOUT, "Audio conversion timed out"),
    (Code.ERROR_FFMPEG_CONVERSION, "Audio file could not be converted"),
    (Code.ERROR_LOADING, "Audio file could not be loaded"),
    (Code.ERROR_VALIDATION, "Audio validation failed"),
    (Code.ERROR_NAN_DETECTED, "Audio file contains invalid sample values"),
]


def _safe_error_message(exc: Exception) -> str:
    """Return a user-safe error category for *exc*.

    The raw exception is intentionally NOT included — callers must log
    it separately so internal paths / library internals stay server-side.
    This also applies to ModuleError.code, which can embed absolute paths
    or raw FFmpeg stderr; only the mapped category string is ever returned.
    """
    if isinstance(exc, ModuleError):
        code = getattr(exc, "code", "") or ""
        for prefix, message in _MODULE_ERROR_CATEGORIES:
            if code.startswith(prefix):
                return message
        return "Audio file could not be processed"
    for exc_type, message in _ERROR_CATEGORIES:
        if isinstance(exc, exc_type):
            return message
    return "An unexpected error occurred during processing"


def _reset_processor_state(processor: HybridProcessor) -> None:
    """Reset the per-job cross-call state on a pooled/cached processor.

    Run via a single `asyncio.to_thread` call (fixes #4797) rather than as
    bare synchronous calls on the event loop, since each acquires
    `_process_lock` (#3787).

    `reset_realtime_eq()` was dropped with the unwired real-time EQ path in
    #4873; `reset_psychoacoustic_eq()` below covers the EQ the live
    adaptive/continuous path actually uses.
    """
    processor.reset_dynamics()
    processor.reset_psychoacoustic_eq()
    processor.reset_limiter()


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

        # Progress callbacks, per job_id. A LIST, not a single callable (#3868):
        # each WebSocket that subscribes to a job registers its own closure, and
        # a single-value dict silently let the newest subscriber overwrite every
        # earlier one — so with two subscribers (multi-window Electron, or one
        # client subscribing twice) all but the last stopped receiving
        # `job_progress` events, with no error anywhere.
        self.progress_callbacks: dict[str, list[Callable[..., Any]]] = {}

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

        # Store the reference path for BOTH reference-consuming modes. This
        # read is served by the single `job.settings.get("reference_path")` in
        # _execute_job, whose branch already covers `reference` and `hybrid` —
        # so gating the *write* on hybrid alone silently discarded the
        # reference for every mode="reference" job, which then fell through to
        # `processor.process(audio)` with reference=None while the config was
        # already in reference mode, and HybridProcessor._process_impl matched
        # none of its three dispatch arms: ValueError, 100% of the time (#4735).
        if mode in ("reference", "hybrid") and reference_path:
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
        """Add a callback for job progress updates.

        Additive: every subscriber for `job_id` is retained and notified
        (#3868). Re-registering the same callable is a no-op rather than a
        double subscription, so a duplicate `subscribe_job_progress` cannot
        make the client receive each tick twice.
        """
        async with self._jobs_lock:
            callbacks = self.progress_callbacks.setdefault(job_id, [])
            if callback not in callbacks:
                callbacks.append(callback)

    async def unregister_progress_callback(
        self, job_id: str, callback: Callable[..., Any] | None = None
    ) -> None:
        """Remove progress callbacks for `job_id` (e.g. on WebSocket disconnect).

        Args:
            job_id: The job whose subscribers are being removed.
            callback: Remove only this subscriber, leaving other subscribers of
                the same job intact — what a per-connection disconnect wants.
                `None` removes every subscriber, for job-wide teardown
                (cancel_job, job cleanup). Passing `None` from a per-connection
                path would evict other live clients' subscriptions (#3868).
        """
        async with self._jobs_lock:
            if callback is None:
                self.progress_callbacks.pop(job_id, None)
                return
            callbacks = self.progress_callbacks.get(job_id)
            if not callbacks:
                return
            # Identity/equality removal; tolerate an already-removed callback so
            # a self-unregister racing with disconnect cleanup is not an error.
            try:
                callbacks.remove(callback)
            except ValueError:
                pass
            if not callbacks:
                self.progress_callbacks.pop(job_id, None)

    async def _notify_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Notify every subscriber registered for this job.

        Silences and removes callbacks that raise (e.g. dead WebSocket),
        so a WS disconnect does not abort the processing job (#3325).

        Subscribers run concurrently and are pruned individually (#3868):
        serial delivery would let one slow/wedged socket delay every other
        subscriber's tick, and removing the whole `job_id` entry on the first
        failure — as the single-callback version did — would silently
        unsubscribe the healthy clients along with the dead one.
        """
        async with self._jobs_lock:
            job = self.jobs.get(job_id)
            if job:
                job.progress = progress
            # Snapshot: the awaits below run outside the lock, and a callback
            # may unregister itself (or others) while we are iterating.
            callbacks = list(self.progress_callbacks.get(job_id, ()))

        if not (job and callbacks):
            return

        results = await asyncio.gather(
            *(cb(job_id, progress, message) for cb in callbacks),
            return_exceptions=True,
        )
        failed = [cb for cb, result in zip(callbacks, results) if isinstance(result, BaseException)]
        if not failed:
            return

        logger.debug(
            "%d/%d progress callbacks for job %s failed, removing them",
            len(failed), len(callbacks), job_id,
        )
        async with self._jobs_lock:
            remaining = self.progress_callbacks.get(job_id)
            if remaining is None:
                return
            for cb in failed:
                try:
                    remaining.remove(cb)
                except ValueError:
                    pass
            if not remaining:
                self.progress_callbacks.pop(job_id, None)

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
        """Return or discard an owned processor without leaking it."""
        if poisoned:
            try:
                await self._discard_processor(processor)
            except Exception:
                logger.warning(
                    "Failed to discard poisoned processor for job %s",
                    job.job_id, exc_info=True,
                )
            return

        try:
            await self._return_processor(job.mode, config, processor)
        except Exception as return_err:
            logger.warning(
                "Failed to return processor for job %s: %s",
                job.job_id, return_err,
            )
            try:
                processor.close()
            except Exception:
                logger.debug("Processor close() also failed", exc_info=True)

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
            # The 25D-fingerprint-to-mastering-parameter mapper this once fed
            # (auralis/analysis/fingerprint/parameter_mapper.py) was deleted
            # as dead code (#4926) — superseded by the continuous-parameter-
            # space mastering path (auralis/core/processing/continuous_space.py).
            # No frontend control sends this setting; kept defensive in case a
            # client still submits it.
            unsupported.append("fingerprint (superseded by continuous-space mastering)")
        eq_settings = job.settings.get("eq")
        if eq_settings and eq_settings.get("enabled"):
            unsupported.append("eq")
        dynamics_settings = job.settings.get("dynamics")
        if dynamics_settings and dynamics_settings.get("enabled"):
            unsupported.append("dynamics")
        level_settings = job.settings.get("level_matching") or job.settings.get("levelMatching")
        if level_settings and level_settings.get("enabled"):
            unsupported.append("level_matching")
        # Value check, not key presence (#5060 fix): ProcessingSettings.model_dump()
        # always includes "genre_override" with a None default even when the
        # client never set it (same trap #3819 already fixed for "fingerprint"
        # above), so `"genre_override" in job.settings` was True — and thus
        # reported as ignored — on every single job, not just ones that set it.
        if job.settings.get("genre_override") is not None:
            unsupported.append("genre_override")
        # sample_rate: None means "keep original" (router default) and is a
        # legitimate no-op, not an ignored request; any other value is accepted
        # by the API but never actually applied — the offline pipeline writes
        # at the input file's rate (#5060).
        if job.settings.get("sample_rate") is not None:
            unsupported.append("sample_rate")

        # Surfaced in result_data (#5060) so a client can tell "applied" from
        # "accepted but silently ignored" instead of only via this INFO log.
        job.ignored_settings = unsupported

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
        # The adaptive/continuous path's main psychoacoustic EQ is the one that
        # matters here; the separate real-time EQ path this used to also reset
        # was deleted as unreachable in #4873.
        # reset_limiter() clears the brick-wall limiter's cross-call gain-reduction
        # state so a loud track doesn't leave the next one starting pre-attenuated
        # (fixes #4811).
        #
        # Each reset acquires `_process_lock` (#3787), a plain threading.RLock.
        # #4727 guarantees a timed-out job's processor is discarded rather than
        # reused, so this lock is never held by an orphaned thread by the time we
        # get here — but the acquire is still offloaded to a thread (fixes #4797)
        # so the event loop is never the thing that blocks if that guarantee is
        # ever broken by some other path in the future.
        await asyncio.to_thread(_reset_processor_state, processor)

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
                # Fall back to adaptive if the reference is unavailable. The
                # config was already switched to reference/hybrid mode in
                # _build_config, and `is_reference_mode() and reference is not
                # None` is the only arm that accepts reference mode — so
                # calling process(audio) without ALSO moving the config back
                # raised ValueError instead of falling back at all (#4735).
                #
                # The router now rejects mode="reference" with no reference at
                # submit time, so this is the narrow race where the file
                # vanished between request and execution; make it degrade
                # rather than crash, and say so in the log.
                logger.warning(
                    "Job %s: mode=%s but reference %r is unavailable; "
                    "falling back to adaptive processing.",
                    job.job_id, job.mode, reference_path,
                )
                processor.config.set_processing_mode("adaptive")
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
        """Collect best-effort telemetry and record the completed result (#4250).

        #4757: get_processing_info() returns a fixed 7-key dict of static
        config (mode/sample_rate/fft_size/...) — it never has "processing_time"
        or "lufs" keys, so those two lookups always missed. And
        last_content_profile is a dict (either ContinuousMode's
        {'fingerprint', 'coordinates', 'parameters'} or, on the legacy
        AdaptiveMode path, ContentAnalyzer.analyze_content()'s dict), so
        getattr(dict_instance, "genre", None) could never succeed either —
        dicts don't expose keys as attributes. All three fields were
        permanently null.
        """
        genre_detected: str | None = None
        lufs: float | None = None
        try:
            content_profile = getattr(processor, "last_content_profile", None)
            if isinstance(content_profile, dict):
                # Legacy AdaptiveMode path (use_continuous_space=False, or the
                # adaptive component of hybrid/reference modes): genre lives
                # under genre_info.primary, not a top-level "genre" key.
                genre_info = content_profile.get("genre_info")
                if isinstance(genre_info, dict):
                    genre_detected = genre_info.get("primary")
                estimated_lufs = content_profile.get("estimated_lufs")
                if estimated_lufs is not None:
                    lufs = float(estimated_lufs)

            # Default/production path (use_continuous_space=True, the only
            # value the app ever sets): ContinuousMode never runs genre
            # classification, but its 25D fingerprint carries a real measured
            # LUFS — prefer it over the legacy estimate above when present.
            continuous_mode = getattr(processor, "continuous_mode", None)
            fingerprint = getattr(continuous_mode, "last_fingerprint", None)
            if isinstance(fingerprint, dict) and fingerprint.get("lufs") is not None:
                lufs = float(fingerprint["lufs"])
        except Exception:
            # Telemetry is non-critical; never let it fail the job.
            pass

        output_format = job.settings.get("output_format", "wav")
        bit_depth = job.settings.get("bit_depth", 16)

        # Real wall-clock duration from job.started_at (set in _prepare_job)
        # to now — covers load + analysis + DSP, not just the DSP call, which
        # is what "processing_time" for a submitted job actually means to a
        # caller. Reuse the same timestamp for completed_at so the two never
        # disagree.
        completed_at = datetime.now()
        processing_time = (
            (completed_at - job.started_at).total_seconds()
            if job.started_at is not None else None
        )

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
            # Settings accepted at submit time but not consumed by the
            # offline pipeline (#5060) — see _create_processor_config.
            "ignored_settings": job.ignored_settings,
        }

        job.status = ProcessingStatus.COMPLETED
        job.completed_at = completed_at

    async def process_job(self, job: ProcessingJob) -> None:
        """
        Process a single job using the HybridProcessor
        """
        # Guard: if cancel_job() fired before the worker started this job, skip it.
        if job.status == ProcessingStatus.CANCELLED:
            return

        processor = None
        config = None
        # Set when the DSP call is abandoned mid-flight (a wait_for timeout) —
        # the underlying OS thread may still be running inside
        # processor.process() and mutating its internals, so the instance
        # must never be handed to another job (#4727).
        processor_poisoned = False
        try:
            audio, sample_rate, config, processor = await self._prepare_job(job)
            audio_data = await self._execute_job(job, audio, sample_rate, processor)
            self._finalize_job(job, audio_data, sample_rate, processor)

        except TimeoutError:
            # asyncio.wait_for raised TimeoutError — the DSP call hung.
            # Mark FAILED so the semaphore slot is released (fixes #2747).
            # wait_for only cancels the asyncio-side wrapper future; the OS
            # thread running processor.process() keeps running, so the
            # instance must be discarded rather than returned to the pool for
            # the next same-config job to reuse (#4727).
            processor_poisoned = True
            job.status = ProcessingStatus.FAILED
            job.error_message = (
                f"Processing timed out after {self.processing_timeout:.0f}s"
            )
            job.completed_at = datetime.now()

            await self._notify_progress(
                job.job_id, 100.0, job.error_message
            )

        except asyncio.CancelledError:
            # task.cancel() was called — mark cancelled and re-raise so asyncio
            # correctly records the task as cancelled (fixes #2217).
            # Conservatively discard any acquired processor: cancellation may
            # have abandoned an uncancellable to_thread DSP call just like a
            # timeout does (#4727/#4759).
            processor_poisoned = processor is not None
            if job.status == ProcessingStatus.PROCESSING:
                job.status = ProcessingStatus.CANCELLED
                job.completed_at = datetime.now()
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
            # Return the processor here rather than per-branch (#4567).
            # get_or_create() POPS it from the pool, so whoever took it owns it
            # and must give it back (#3201). Three of the four exit paths did;
            # the catch-all `except Exception` did not, so every failed job
            # dropped a warm processor without returning or closing it,
            # forcing the next same-config job to pay the full 200-500 ms
            # HybridProcessor.__init__ again. (#3746 also cited a permanently
            # leaked 5-thread fingerprint executor; that executor is gone —
            # see #4744 — but the reconstruction cost is not.) Hoisting it means a future branch
            # cannot reintroduce the same omission.
            #
            # A timed-out or cancelled processor is the one exception: it must
            # be closed and discarded, never cached, since an orphaned thread
            # may still be running inside it (#4727/#4759).
            try:
                if processor is not None and config is not None:
                    cleanup_task = asyncio.create_task(
                        self._cleanup_processor(
                            job, config, processor, processor_poisoned
                        )
                    )
                    try:
                        # Cleanup owns a popped processor and must finish even
                        # if cancellation lands while it waits for the pool
                        # lock (#4759).
                        await asyncio.shield(cleanup_task)
                    except asyncio.CancelledError:
                        await cleanup_task
                        raise
            finally:
                # Never let a cancellation during cleanup skip registry
                # removal (#4496/#4759).
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
        upload_dir = Path(tempfile.gettempdir()) / UPLOAD_TEMP_DIRNAME

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

        # Phase 2: filesystem checks and deletions outside the lock (#3327).
        # Offloaded via asyncio.to_thread (#4754) — an unbounded per-job
        # loop of stat()/unlink() calls that grows with job count, running
        # directly on the event loop.
        def _delete_expired_files() -> None:
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

        await asyncio.to_thread(_delete_expired_files)

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
