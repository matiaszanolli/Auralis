#!/usr/bin/env python3

"""
Expired-job sweep for the ProcessingEngine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Removes completed/failed/cancelled jobs older than a TTL and deletes their
temp files. Extracted from processing_engine.py (#4250 follow-up: the
mechanical pool/worker/process_job split landed in 3b01a65e, but the engine
module itself kept growing past the 300-line convention through unrelated
bugfixes — this is the next safe slice out of it). Two-phase locking and the
offloaded filesystem sweep are unchanged (preserves #2435, #3327, #4754).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from core.job_models import ProcessingJob, ProcessingStatus

logger = logging.getLogger(__name__)


async def cleanup_expired_jobs(
    jobs: dict[str, ProcessingJob],
    jobs_lock: asyncio.Lock,
    progress_callbacks: dict[str, list[Callable[..., Any]]],
    upload_dir: Path,
    max_age_hours: float,
) -> int:
    """Clean up old completed jobs and their files.

    Protected by `jobs_lock` so that concurrent invocations (worker finally-
    block vs. explicit DELETE /jobs/cleanup request) do not iterate and
    delete `jobs` simultaneously, which would raise RuntimeError in CPython
    when another coroutine modifies the dict mid-iteration (#2435).

    Args:
        jobs: The engine's live job registry (mutated in place).
        jobs_lock: The engine's `_jobs_lock`, guarding both `jobs` and
            `progress_callbacks`.
        progress_callbacks: The engine's progress-subscriber map (mutated
            in place — an expired job's subscribers are dropped too).
        upload_dir: Directory holding uploaded input files; only input files
            under this directory are eligible for deletion, so a job whose
            input lives outside it (e.g. a library track) is left alone.
        max_age_hours: Age threshold, measured from `job.completed_at`.

    Returns:
        int: Number of jobs removed
    """
    now = datetime.now()
    jobs_to_remove: list[str] = []
    files_to_delete: list[Path] = []

    # Phase 1: identify expired jobs under lock (no blocking I/O)
    candidate_paths: list[tuple[Path, Path]] = []  # (output_path, input_path)

    async with jobs_lock:
        for job_id, job in jobs.items():
            if job.status in (ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.CANCELLED):
                if job.completed_at is not None:
                    age_hours = (now - job.completed_at).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        candidate_paths.append((Path(job.output_path), Path(job.input_path)))
                        jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            del jobs[job_id]
            if job_id in progress_callbacks:
                del progress_callbacks[job_id]

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
