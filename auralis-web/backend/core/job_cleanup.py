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
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import tempfile
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from core.job_models import TERMINAL_STATUSES, ProcessingJob, ProcessingStatus
from config.limits import UPLOAD_TEMP_DIRNAME
from config.retention import SECONDS_PER_HOUR

logger = logging.getLogger(__name__)


def upload_temp_dir() -> Path:
    """Where upload-and-process writes its inputs; the job sweeps and the startup reclaim look here."""
    return Path(tempfile.gettempdir()) / UPLOAD_TEMP_DIRNAME


def discard_upload_input(job: ProcessingJob, upload_dir: Path | None = None) -> None:
    """Delete a FAILED or CANCELLED job's input when it is an upload the job owns (#6517).

    Nothing can use it again: there is no retry, and the output is the only thing
    a client fetches. Left for the TTL sweep, a client loop posting large uploads
    that fail at decode held ~500 MB each for an hour. A COMPLETED job's input is
    left to that sweep, like its output; an input outside the uploads directory
    (a library track) is never touched, the same rule the sweep applies.
    """
    if job.status not in (ProcessingStatus.FAILED, ProcessingStatus.CANCELLED):
        return
    input_path = Path(job.input_path)
    if not input_path.is_relative_to(upload_dir or upload_temp_dir()):
        return
    try:
        input_path.unlink(missing_ok=True)
    except OSError as e:
        logger.warning(f"Failed to delete the input of job {job.job_id}: {e}")


async def cleanup_expired_jobs(
    jobs: dict[str, ProcessingJob],
    jobs_lock: asyncio.Lock,
    upload_dir: Path,
    max_age_hours: float,
    on_removed: Callable[[list[str]], Awaitable[None]] | None = None,
) -> int:
    """Clean up old completed jobs and their files.

    Protected by `jobs_lock` so that concurrent invocations (periodic sweep
    vs. explicit cleanup request) do not iterate and
    delete `jobs` simultaneously, which would raise RuntimeError in CPython
    when another coroutine modifies the dict mid-iteration (#2435).

    Args:
        jobs: The engine's live job registry (mutated in place).
        jobs_lock: The engine's `_jobs_lock`, guarding `jobs`.
        upload_dir: Directory holding uploaded input files; only input files
            under this directory are eligible for deletion, so a job whose
            input lives outside it (e.g. a library track) is left alone.
        max_age_hours: Age threshold, measured from `job.completed_at`.
        on_removed: Awaited with the removed job ids, so the persisted
            records expire with the live ones (#5278).

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
            if job.status not in TERMINAL_STATUSES or job.completed_at is None:
                continue
            age_hours = (now - job.completed_at).total_seconds() / SECONDS_PER_HOUR
            if age_hours > max_age_hours:
                candidate_paths.append((Path(job.output_path), Path(job.input_path)))
                jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            del jobs[job_id]

    if not jobs_to_remove:
        return 0

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
                logger.warning(f"Failed to delete {file_path.name}: {e}")

    await asyncio.to_thread(_delete_expired_files)
    if on_removed is not None and jobs_to_remove:
        await on_removed(jobs_to_remove)

    return len(jobs_to_remove)
