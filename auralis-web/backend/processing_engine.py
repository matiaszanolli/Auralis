#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Processing Engine for Auralis Web Backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles audio processing jobs using the HybridProcessor from the core Auralis system.
Manages job queue, progress tracking, and result caching.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import uuid
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import sys

# Add parent directory to path for Auralis imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig, AdaptiveConfig
from auralis.io.unified_loader import load_audio
from auralis.io.saver import save
import numpy as np


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
        settings: Dict[str, Any],
        mode: str = "adaptive"
    ):
        self.job_id = job_id
        self.input_path = input_path
        self.output_path = output_path
        self.settings = settings
        self.mode = mode  # "adaptive", "reference", "hybrid"

        self.status = ProcessingStatus.QUEUED
        self.progress = 0.0
        self.error_message: Optional[str] = None
        self.result_data: Optional[Dict[str, Any]] = None

        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
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

    def __init__(self, max_concurrent_jobs: int = 2):
        self.jobs: Dict[str, ProcessingJob] = {}
        self.max_concurrent_jobs = max_concurrent_jobs
        self.active_jobs = 0
        self.job_queue = asyncio.Queue()

        # Processing components
        self.processors: Dict[str, HybridProcessor] = {}

        # Temporary file management
        self.temp_dir = Path(tempfile.gettempdir()) / "auralis_processing"
        self.temp_dir.mkdir(exist_ok=True)

        # Progress callbacks
        self.progress_callbacks: Dict[str, Callable] = {}

    def create_job(
        self,
        input_path: str,
        settings: Dict[str, Any],
        mode: str = "adaptive",
        reference_path: Optional[str] = None
    ) -> ProcessingJob:
        """Create a new processing job"""

        job_id = str(uuid.uuid4())

        # Generate output path
        input_file = Path(input_path)
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
        """Submit a job to the processing queue"""
        await self.job_queue.put(job)
        return job.job_id

    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Get job by ID"""
        return self.jobs.get(job_id)

    def register_progress_callback(self, job_id: str, callback: Callable):
        """Register a callback for job progress updates"""
        self.progress_callbacks[job_id] = callback

    async def _notify_progress(self, job_id: str, progress: float, message: str = ""):
        """Notify progress callback"""
        job = self.jobs.get(job_id)
        if job:
            job.progress = progress

            if job_id in self.progress_callbacks:
                callback = self.progress_callbacks[job_id]
                await callback(job_id, progress, message)

    def _create_processor_config(self, job: ProcessingJob) -> UnifiedConfig:
        """Create UnifiedConfig from job settings"""

        config = UnifiedConfig()

        # Set processing mode
        if job.mode == "adaptive":
            config.set_processing_mode("adaptive")
        elif job.mode == "reference":
            config.set_processing_mode("reference")
        elif job.mode == "hybrid":
            config.set_processing_mode("hybrid")

        # Apply EQ settings
        if "eq" in job.settings and job.settings["eq"].get("enabled"):
            eq_settings = job.settings["eq"]
            # Apply EQ settings to config (simplified for now)
            # TODO: Map UI EQ settings to processor config

        # Apply dynamics settings
        if "dynamics" in job.settings and job.settings["dynamics"].get("enabled"):
            dynamics_settings = job.settings["dynamics"]
            # TODO: Map UI dynamics settings to processor config

        # Apply level matching settings
        if "levelMatching" in job.settings and job.settings["levelMatching"].get("enabled"):
            level_settings = job.settings["levelMatching"]
            config.adaptive.target_lufs = level_settings.get("targetLufs", -16.0)

        # Genre override
        if "genre_override" in job.settings:
            config.adaptive.genre_override = job.settings["genre_override"]

        return config

    async def process_job(self, job: ProcessingJob):
        """
        Process a single job using the HybridProcessor
        """

        try:
            job.status = ProcessingStatus.PROCESSING
            job.started_at = datetime.now()
            self.active_jobs += 1

            await self._notify_progress(job.job_id, 0.0, "Loading audio file...")

            # Load input audio
            audio, sample_rate = load_audio(job.input_path)

            await self._notify_progress(job.job_id, 20.0, "Analyzing audio content...")

            # Create processor config
            config = self._create_processor_config(job)

            # Get or create processor for this job
            processor = HybridProcessor(config)

            await self._notify_progress(job.job_id, 40.0, "Processing audio...")

            # Process audio
            if job.mode == "reference" or job.mode == "hybrid":
                # Load reference audio if needed
                reference_path = job.settings.get("reference_path")
                if reference_path and Path(reference_path).exists():
                    reference_audio, reference_sr = load_audio(reference_path)
                    # Resample reference if needed
                    if reference_sr != sample_rate:
                        # TODO: Implement resampling
                        pass
                    result = processor.process(audio, reference_audio)
                else:
                    # Fall back to adaptive mode if no reference
                    result = processor.process(audio)
            else:
                # Adaptive mode
                result = processor.process(audio)

            await self._notify_progress(job.job_id, 80.0, "Saving processed audio...")

            # Save output audio
            output_format = job.settings.get("output_format", "wav")
            bit_depth = job.settings.get("bit_depth", 16)

            # Determine subtype based on bit depth
            subtype_map = {16: 'PCM_16', 24: 'PCM_24', 32: 'PCM_32'}
            subtype = subtype_map.get(bit_depth, 'PCM_16')

            save(
                file_path=job.output_path,
                audio_data=result.audio,
                sample_rate=sample_rate,
                subtype=subtype
            )

            await self._notify_progress(job.job_id, 100.0, "Processing complete!")

            # Store result metadata
            job.result_data = {
                "output_path": job.output_path,
                "sample_rate": int(sample_rate),
                "duration": float(len(result.audio) / sample_rate),
                "format": output_format,
                "bit_depth": bit_depth,
                "processing_time": result.processing_time if hasattr(result, "processing_time") else None,
                "genre_detected": result.genre if hasattr(result, "genre") else None,
                "lufs": float(result.lufs) if hasattr(result, "lufs") else None,
            }

            job.status = ProcessingStatus.COMPLETED
            job.completed_at = datetime.now()

        except Exception as e:
            job.status = ProcessingStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()

            await self._notify_progress(job.job_id, 100.0, f"Processing failed: {str(e)}")

        finally:
            self.active_jobs -= 1

    async def start_worker(self):
        """Start the job processing worker"""
        while True:
            try:
                # Wait for a job
                job = await self.job_queue.get()

                # Check if we can process (max concurrent jobs)
                while self.active_jobs >= self.max_concurrent_jobs:
                    await asyncio.sleep(0.5)

                # Process the job
                await self.process_job(job)

            except Exception as e:
                print(f"Worker error: {e}")
                await asyncio.sleep(1)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status in [ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING]:
            job.status = ProcessingStatus.CANCELLED
            job.completed_at = datetime.now()
            return True

        return False

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up old completed jobs and their files"""
        now = datetime.now()
        jobs_to_remove = []

        for job_id, job in self.jobs.items():
            if job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.CANCELLED]:
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

    def get_all_jobs(self) -> list[ProcessingJob]:
        """Get all jobs"""
        return list(self.jobs.values())

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            "total_jobs": len(self.jobs),
            "queued": len([j for j in self.jobs.values() if j.status == ProcessingStatus.QUEUED]),
            "processing": self.active_jobs,
            "completed": len([j for j in self.jobs.values() if j.status == ProcessingStatus.COMPLETED]),
            "failed": len([j for j in self.jobs.values() if j.status == ProcessingStatus.FAILED]),
            "max_concurrent": self.max_concurrent_jobs,
        }