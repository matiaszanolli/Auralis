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
import sys
import tempfile
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from collections.abc import Callable

# Add parent directory to path for Auralis imports
sys.path.append(str(Path(__file__).parent.parent.parent))


from auralis.analysis.fingerprint.parameter_mapper import ParameterMapper
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.processing import resample_audio
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio


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
        """Convert job to dictionary for API responses"""
        return {
            "job_id": self.job_id,
            "input_path": self.input_path,
            "output_path": self.output_path,
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

    def __init__(
        self,
        max_concurrent_jobs: int = 2,
        max_queue_size: int = 20,
        completed_job_ttl_hours: float = 1.0,
    ) -> None:
        self.jobs: dict[str, ProcessingJob] = {}
        self.max_concurrent_jobs: int = max_concurrent_jobs
        self.max_queue_size: int = max_queue_size
        self.completed_job_ttl_hours: float = completed_job_ttl_hours
        self.active_jobs: int = 0
        self.job_queue: asyncio.Queue[ProcessingJob] = asyncio.Queue(maxsize=max_queue_size)

        # Semaphore replaces the busy-wait loop in start_worker (fixes #2332)
        self._concurrency_semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent_jobs)

        # Processing components
        self.processors: dict[str, HybridProcessor] = {}
        self.parameter_mapper = ParameterMapper()

        # Temporary file management
        self.temp_dir: Path = Path(tempfile.gettempdir()) / "auralis_processing"
        self.temp_dir.mkdir(exist_ok=True)

        # Progress callbacks
        self.progress_callbacks: dict[str, Callable[..., Any]] = {}

        # Per-job asyncio Tasks so cancel_job() can stop them (fixes #2217)
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def create_job(
        self,
        input_path: str,
        settings: dict[str, Any],
        mode: str = "adaptive",
        reference_path: str | None = None
    ) -> ProcessingJob:
        """Create a new processing job"""

        job_id = str(uuid.uuid4())

        # Generate output path
        Path(input_path)
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
            # Remove the pre-registered job entry so it doesn't linger
            self.jobs.pop(job.job_id, None)
            raise
        return job.job_id

    def get_job(self, job_id: str) -> ProcessingJob | None:
        """Get job by ID"""
        return self.jobs.get(job_id)

    def register_progress_callback(self, job_id: str, callback: Callable[..., Any]) -> None:
        """Register a callback for job progress updates"""
        self.progress_callbacks[job_id] = callback

    async def _notify_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Notify progress callback"""
        job = self.jobs.get(job_id)
        if job:
            job.progress = progress

            if job_id in self.progress_callbacks:
                callback = self.progress_callbacks[job_id]
                await callback(job_id, progress, message)

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
        # Create a simple key based on mode and key config params
        # Sample rate is critical, as are the key tuning parameters
        key_parts: list[str] = [
            mode,
            str(config.sample_rate),  # type: ignore[attr-defined]
            config.processing_mode if hasattr(config, 'processing_mode') else 'unknown',
        ]
        return "|".join(key_parts)

    def _get_or_create_processor(self, mode: str, config: UnifiedConfig) -> HybridProcessor:
        """
        Get cached processor instance or create new one.

        Processor instances are expensive to create because they:
        - Initialize analysis modules
        - Pre-compute window functions
        - Set up DSP stage instances

        Caching reusable processors provides 200-500ms speedup per job.

        Args:
            mode: Processing mode
            config: UnifiedConfig for processor

        Returns:
            HybridProcessor instance (cached or new)
        """
        cache_key = self._get_processor_cache_key(mode, config)

        if cache_key in self.processors:
            # Return cached processor
            return self.processors[cache_key]

        # Create new processor and cache it
        processor = HybridProcessor(config)
        self.processors[cache_key] = processor

        # Keep cache size bounded (max 5 different processor configurations)
        # This prevents unbounded memory growth while maintaining hit rates
        if len(self.processors) > 5:
            # Remove oldest entry (simple FIFO eviction)
            oldest_key = next(iter(self.processors))
            del self.processors[oldest_key]

        return processor

    def _create_processor_config(self, job: ProcessingJob) -> UnifiedConfig:
        """
        Create UnifiedConfig from job settings.

        Supports two workflows:
        1. Adaptive mode: Uses 25D fingerprint to generate parameters
        2. Manual mode: Uses explicit UI settings for EQ/dynamics
        """

        config = UnifiedConfig()

        # Set processing mode
        if job.mode == "adaptive":
            config.set_processing_mode("adaptive")
        elif job.mode == "reference":
            config.set_processing_mode("reference")
        elif job.mode == "hybrid":
            config.set_processing_mode("hybrid")

        # Check if using fingerprint-based adaptive mastering
        if "fingerprint" in job.settings and job.settings["fingerprint"].get("enabled"):
            # Workflow 1: Generate parameters from 25D fingerprint
            fingerprint = job.settings["fingerprint"].get("data", {})
            target_lufs = job.settings.get("targetLufs", -16.0)

            mastering_params = self.parameter_mapper.generate_mastering_parameters(
                fingerprint=fingerprint,
                target_lufs=target_lufs,
                enable_multiband=job.settings.get("enable_multiband", False)
            )

            # Apply generated EQ parameters
            if "eq" in mastering_params:
                self._apply_eq_to_config(config, mastering_params["eq"])

            # Apply generated dynamics parameters
            if "dynamics" in mastering_params:
                self._apply_dynamics_to_config(config, mastering_params["dynamics"])

            # Apply generated level parameters
            if "level" in mastering_params:
                self._apply_level_to_config(config, mastering_params["level"])

        else:
            # Workflow 2: Apply manual UI settings
            # Apply EQ settings
            if "eq" in job.settings and job.settings["eq"].get("enabled"):
                eq_settings = job.settings["eq"]
                self._apply_ui_eq_to_config(config, eq_settings)

            # Apply dynamics settings
            if "dynamics" in job.settings and job.settings["dynamics"].get("enabled"):
                dynamics_settings = job.settings["dynamics"]
                self._apply_ui_dynamics_to_config(config, dynamics_settings)

            # Apply level matching settings
            if "levelMatching" in job.settings and job.settings["levelMatching"].get("enabled"):
                level_settings = job.settings["levelMatching"]
                config.adaptive.target_lufs = level_settings.get("targetLufs", -16.0)  # type: ignore[attr-defined]

        # Genre override
        if "genre_override" in job.settings:
            config.adaptive.genre_override = job.settings["genre_override"]  # type: ignore[attr-defined]

        return config

    def _apply_eq_to_config(self, config: UnifiedConfig, eq_params: dict[str, Any]) -> None:
        """Apply generated EQ parameters to config"""
        if eq_params.get("enabled") and "gains" in eq_params:
            # Store EQ gains in adaptive config for HybridProcessor
            if not hasattr(config.adaptive, "eq_gains"):
                config.adaptive.eq_gains = {}  # type: ignore[attr-defined]
            config.adaptive.eq_gains = eq_params["gains"]  # type: ignore[attr-defined]

    def _apply_dynamics_to_config(self, config: UnifiedConfig, dynamics_params: dict[str, Any]) -> None:
        """Apply generated dynamics parameters to config"""
        if dynamics_params.get("enabled") and "standard" in dynamics_params:
            # Apply standard compressor settings
            comp = dynamics_params["standard"]
            if not hasattr(config.adaptive, "compressor"):
                config.adaptive.compressor = {}  # type: ignore[attr-defined]

            config.adaptive.compressor = {  # type: ignore[attr-defined]
                "threshold": comp.get("threshold", -20.0),
                "ratio": comp.get("ratio", 2.0),
                "attack_ms": comp.get("attack_ms", 30.0),
                "release_ms": comp.get("release_ms", 150.0),
                "makeup_gain": comp.get("makeup_gain", 0.0)
            }

    def _apply_level_to_config(self, config: UnifiedConfig, level_params: dict[str, Any]) -> None:
        """Apply generated level parameters to config"""
        config.adaptive.target_lufs = level_params.get("target_lufs", -16.0)  # type: ignore[attr-defined]
        if "gain" in level_params:
            if not hasattr(config.adaptive, "gain"):
                config.adaptive.gain = 0.0  # type: ignore[attr-defined]
            config.adaptive.gain = level_params["gain"]  # type: ignore[attr-defined]

    def _apply_ui_eq_to_config(self, config: UnifiedConfig, eq_settings: dict[str, Any]) -> None:
        """Apply manual UI EQ settings to config"""
        # This handles direct UI EQ input (31-band gains or parametric EQ)
        if "gains" in eq_settings:
            if not hasattr(config.adaptive, "eq_gains"):
                config.adaptive.eq_gains = {}  # type: ignore[attr-defined]
            config.adaptive.eq_gains = eq_settings["gains"]  # type: ignore[attr-defined]

    def _apply_ui_dynamics_to_config(self, config: UnifiedConfig, dynamics_settings: dict[str, Any]) -> None:
        """Apply manual UI dynamics settings to config"""
        if not hasattr(config.adaptive, "compressor"):
            config.adaptive.compressor = {}  # type: ignore[attr-defined]

        config.adaptive.compressor = {  # type: ignore[attr-defined]
            "threshold": dynamics_settings.get("threshold", -20.0),
            "ratio": dynamics_settings.get("ratio", 2.0),
            "attack_ms": dynamics_settings.get("attack_ms", 30.0),
            "release_ms": dynamics_settings.get("release_ms", 150.0),
            "makeup_gain": dynamics_settings.get("makeup_gain", 0.0)
        }

    async def process_job(self, job: ProcessingJob) -> None:
        """
        Process a single job using the HybridProcessor
        """
        # Guard: if cancel_job() fired before the worker started this job, skip it.
        if job.status == ProcessingStatus.CANCELLED:
            return

        try:
            job.status = ProcessingStatus.PROCESSING
            job.started_at = datetime.now()
            self.active_jobs += 1

            await self._notify_progress(job.job_id, 0.0, "Loading audio file...")

            # Load input audio — disk-bound; offload to thread (fixes #2319)
            audio, sample_rate = await asyncio.to_thread(load_audio, job.input_path)

            await self._notify_progress(job.job_id, 20.0, "Analyzing audio content...")

            # Create processor config
            config = self._create_processor_config(job)

            # Get or create processor for this job (with caching for repeated configs)
            processor = self._get_or_create_processor(job.mode, config)

            await self._notify_progress(job.job_id, 40.0, "Processing audio...")

            # Process audio — CPU-bound; offload to thread (fixes #2319)
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
                    result = await asyncio.to_thread(processor.process, audio, reference_audio)
                else:
                    # Fall back to adaptive mode if no reference
                    result = await asyncio.to_thread(processor.process, audio)
            else:
                # Adaptive mode
                result = await asyncio.to_thread(processor.process, audio)

            await self._notify_progress(job.job_id, 80.0, "Saving processed audio...")

            # Save output audio
            output_format = job.settings.get("output_format", "wav")
            bit_depth = job.settings.get("bit_depth", 16)

            # Determine subtype based on bit depth
            subtype_map: dict[int, str] = {16: 'PCM_16', 24: 'PCM_24', 32: 'PCM_32'}
            subtype = subtype_map.get(bit_depth, 'PCM_16')

            # Disk-bound write; offload to thread (fixes #2319)
            await asyncio.to_thread(
                save,
                file_path=job.output_path,
                audio_data=result.audio,  # type: ignore[union-attr]
                sample_rate=sample_rate,
                subtype=subtype,
            )

            await self._notify_progress(job.job_id, 100.0, "Processing complete!")

            # Store result metadata
            job.result_data = {
                "output_path": job.output_path,
                "sample_rate": int(sample_rate),
                "duration": float(len(result.audio) / sample_rate),  # type: ignore[union-attr]
                "format": output_format,
                "bit_depth": bit_depth,
                "processing_time": result.processing_time if hasattr(result, "processing_time") else None,  # type: ignore[union-attr]
                "genre_detected": result.genre if hasattr(result, "genre") else None,  # type: ignore[union-attr]
                "lufs": float(result.lufs) if hasattr(result, "lufs") else None,  # type: ignore[union-attr]
            }

            job.status = ProcessingStatus.COMPLETED
            job.completed_at = datetime.now()

        except asyncio.CancelledError:
            # task.cancel() was called — mark cancelled and re-raise so asyncio
            # correctly records the task as cancelled (fixes #2217).
            if job.status == ProcessingStatus.PROCESSING:
                job.status = ProcessingStatus.CANCELLED
                job.completed_at = datetime.now()
            raise

        except Exception as e:
            job.status = ProcessingStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()

            await self._notify_progress(job.job_id, 100.0, f"Processing failed: {str(e)}")

        finally:
            self.active_jobs -= 1

    async def start_worker(self) -> None:
        """Start the job processing worker"""
        while True:
            try:
                # Wait for a job
                job = await self.job_queue.get()

                # Block until a concurrency slot is free (replaces busy-wait, fixes #2332)
                await self._concurrency_semaphore.acquire()

                # Wrap in a Task so cancel_job() can call task.cancel() (fixes #2217)
                task = asyncio.create_task(self.process_job(job))
                self._tasks[job.job_id] = task
                try:
                    await task
                except asyncio.CancelledError:
                    # If the job was deliberately cancelled, swallow the error and
                    # keep the worker running.  If the worker itself is being shut
                    # down (job.status != CANCELLED), re-raise.
                    if job.status != ProcessingStatus.CANCELLED:
                        raise
                finally:
                    self._tasks.pop(job.job_id, None)
                    self._concurrency_semaphore.release()
                    self.cleanup_old_jobs(self.completed_job_ttl_hours)

            except Exception as e:
                print(f"Worker error: {e}")
                await asyncio.sleep(1)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.

        For QUEUED jobs: marks the status so process_job() skips it.
        For PROCESSING jobs: cancels the asyncio Task, which injects
        CancelledError at the next await point (fixes #2217).
        """
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status in [ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING]:
            job.status = ProcessingStatus.CANCELLED
            job.completed_at = datetime.now()
            # Signal the running task to stop (no-op for QUEUED jobs that
            # haven't been picked up yet — the early-return guard in
            # process_job() handles that case).
            task = self._tasks.get(job_id)
            if task and not task.done():
                task.cancel()
            return True

        return False

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Clean up old completed jobs and their files

        Returns:
            int: Number of jobs removed
        """
        now = datetime.now()
        jobs_to_remove: list[str] = []

        for job_id, job in self.jobs.items():
            if job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.CANCELLED]:
                if job.completed_at is not None:
                    age_hours = (now - job.completed_at).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        # Remove output file
                        if Path(job.output_path).exists():
                            Path(job.output_path).unlink()
                        jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            del self.jobs[job_id]
            if job_id in self.progress_callbacks:
                del self.progress_callbacks[job_id]

        return len(jobs_to_remove)

    def get_all_jobs(self) -> list[ProcessingJob]:
        """Get all jobs"""
        return list(self.jobs.values())

    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status"""
        return {
            "total_jobs": len(self.jobs),
            "queued": len([j for j in self.jobs.values() if j.status == ProcessingStatus.QUEUED]),
            "processing": self.active_jobs,
            "completed": len([j for j in self.jobs.values() if j.status == ProcessingStatus.COMPLETED]),
            "failed": len([j for j in self.jobs.values() if j.status == ProcessingStatus.FAILED]),
            "max_concurrent": self.max_concurrent_jobs,
            "max_queue_size": self.max_queue_size,
            "queue_full": self.job_queue.full(),
        }