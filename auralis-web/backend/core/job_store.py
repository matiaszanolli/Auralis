#!/usr/bin/env python3

"""
Processing job persistence
~~~~~~~~~~~~~~~~~~~~~~~~~~

Writes each ProcessingJob to the library database at its lifecycle
transitions and reads the table back when the engine starts (#5278), so a
backend restart no longer erases every job. The live registry is still
``ProcessingEngine.jobs``; this is its durable copy.

Persistence is best-effort: a failed write is logged and never fails or
delays the job itself. Repository calls run off the event loop.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from core.job_models import TERMINAL_STATUSES, ProcessingJob, ProcessingStatus

logger = logging.getLogger(__name__)

# Statuses that mean "the process that owned this job is gone" when read
# back at startup: nothing will ever resume them.
_UNFINISHED = (ProcessingStatus.QUEUED.value, ProcessingStatus.PROCESSING.value)
INTERRUPTED_MESSAGE = "Interrupted: the backend stopped before this job finished"


def job_to_fields(job: ProcessingJob) -> dict[str, Any]:
    """The ProcessingJobRecord columns for ``job``."""
    return {
        "job_id": job.job_id,
        "input_path": job.input_path,
        "output_path": job.output_path,
        "mode": job.mode,
        "status": job.status.value,
        "progress": float(job.progress),
        "error_message": job.error_message,
        "settings": json.dumps(job.settings, default=str),
        "result_data": None if job.result_data is None else json.dumps(job.result_data, default=str),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }


def job_from_record(record: Any) -> ProcessingJob:
    """Rebuild a ProcessingJob from a ProcessingJobRecord."""
    job = ProcessingJob(
        job_id=record.job_id,
        input_path=record.input_path,
        output_path=record.output_path,
        settings=json.loads(record.settings or "{}"),
        mode=record.mode,
    )
    job.status = ProcessingStatus(record.status)
    job.progress = record.progress
    job.error_message = record.error_message
    job.result_data = json.loads(record.result_data) if record.result_data else None
    job.created_at = record.created_at
    job.started_at = record.started_at
    job.completed_at = record.completed_at
    return job


class JobStore:
    """Durable copy of the engine's jobs.

    ``get_repository`` returns the library's ProcessingJobRepository, or None
    when there is no library database (the store then does nothing).
    """

    def __init__(self, get_repository: Callable[[], Any | None] | None = None) -> None:
        self._get_repository = get_repository

    def _repository(self) -> Any | None:
        if self._get_repository is None:
            return None
        try:
            return self._get_repository()
        except Exception as e:
            logger.warning(f"Processing job repository unavailable: {e}")
            return None

    async def save(self, job: ProcessingJob) -> None:
        """Persist ``job``'s current state."""
        repository = self._repository()
        if repository is None:
            return
        try:
            await asyncio.to_thread(repository.save, **job_to_fields(job))
        except Exception as e:
            logger.warning(f"Could not persist processing job {job.job_id}: {e}")

    async def forget(self, job_ids: Iterable[str]) -> None:
        """Drop the records of jobs the engine has expired."""
        ids = list(job_ids)
        repository = self._repository()
        if repository is None or not ids:
            return
        try:
            await asyncio.to_thread(repository.delete, ids)
        except Exception as e:
            logger.warning(f"Could not delete {len(ids)} processing job record(s): {e}")

    async def restore(self, ttl_hours: float) -> list[ProcessingJob]:
        """Reconcile the table after a restart and return the jobs to reload.

        - A job still queued or processing was abandoned by the previous
          process: it becomes INTERRUPTED, finishing now.
        - A finished job older than ``ttl_hours`` is deleted, the same expiry
          the engine's cleanup sweep and the startup temp-file sweep apply
          (its output file is gone or about to be).
        - Everything else comes back as it was, so its status, listing and
          download keep working across the restart.
        """
        repository = self._repository()
        if repository is None:
            return []
        now = datetime.now()

        def _reconcile() -> list[ProcessingJob]:
            interrupted = repository.mark_unfinished(
                _UNFINISHED, ProcessingStatus.INTERRUPTED.value, INTERRUPTED_MESSAGE, now
            )
            if interrupted:
                logger.warning(f"Marked {interrupted} processing job(s) interrupted by the last shutdown")
            kept: list[ProcessingJob] = []
            expired: list[str] = []
            for record in repository.get_all():
                try:
                    job = job_from_record(record)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Dropping unreadable processing job record {record.job_id}: {e}")
                    expired.append(record.job_id)
                    continue
                if (
                    job.status in TERMINAL_STATUSES
                    and job.completed_at is not None
                    and (now - job.completed_at).total_seconds() > ttl_hours * 3600
                ):
                    expired.append(job.job_id)
                else:
                    kept.append(job)
            repository.delete(expired)
            return kept

        try:
            return await asyncio.to_thread(_reconcile)
        except Exception as e:
            logger.warning(f"Could not restore persisted processing jobs: {e}")
            return []


async def persist(engine: Any, job: ProcessingJob) -> None:
    """Save ``job`` through ``engine``'s store, if it has a real one.

    The lifecycle helpers call this rather than ``engine.job_store.save`` so an
    engine built without a store (tests' bare or mock engines) simply skips
    persistence.
    """
    store = getattr(engine, "job_store", None)
    if isinstance(store, JobStore):
        await store.save(job)
