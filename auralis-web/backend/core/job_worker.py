#!/usr/bin/env python3

"""
Job worker loop for the ProcessingEngine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Owns the job queue, concurrency semaphore, per-job task registry, and the
dispatch loop. Extracted from processing_engine.py (#4250); the slot lifecycle,
fire-and-forget dispatch, and cancellation/stop semantics are unchanged
(preserves #2332, #2299, #2459, #3531/BE-NEW-73, #2217, #3512/BE-NEW-54, #2746).

The worker holds a back-reference to the engine only to reach the job-lifecycle
surface it must drive: process_job(), cleanup_old_jobs(), the jobs registry, and
the completed-job TTL. The engine exposes the worker's queue/semaphore/task
state via thin properties so its public methods (submit_job, cancel_job,
get_queue_status) keep working unchanged.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from core.job_models import ProcessingJob, ProcessingStatus

if TYPE_CHECKING:
    from core.processing_engine import ProcessingEngine

logger = logging.getLogger(__name__)


class JobWorker:
    """Dispatches queued jobs as concurrent tasks bounded by a semaphore."""

    # Upper bound on how long stop() waits for cancelled job tasks to unwind
    # before logging and proceeding (#4543).
    STOP_DRAIN_TIMEOUT_SECONDS: float = 5.0

    def __init__(
        self,
        engine: "ProcessingEngine",
        max_concurrent_jobs: int,
        max_queue_size: int,
    ) -> None:
        self._engine = engine
        self.job_queue: asyncio.Queue[ProcessingJob] = asyncio.Queue(maxsize=max_queue_size)

        # Semaphore is the single source of truth for concurrency limiting.
        # Replaces the busy-wait loop (fixes #2332) and the unsynchronised
        # active_jobs counter (fixes #2299).
        self._concurrency_semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent_jobs)

        # Public counter incremented after semaphore.acquire() and decremented
        # in the finally block of _run_job. Replaces the fragile
        # `semaphore._value` CPython implementation detail (#2459).
        self.active_job_count: int = 0

        # Per-job asyncio Tasks so cancel_job() can stop them (fixes #2217)
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._stopping: bool = False
        self._worker_task: asyncio.Task[None] | None = None

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
            self.active_job_count += 1

            task = asyncio.current_task()
            if task is not None:
                self._tasks[job.job_id] = task

            try:
                await self._engine.process_job(job)
            except asyncio.CancelledError:
                if job.status != ProcessingStatus.CANCELLED:
                    raise
        finally:
            self._tasks.pop(job.job_id, None)
            if acquired:
                self.active_job_count = max(0, self.active_job_count - 1)
                self._concurrency_semaphore.release()

            # #4543: an `await` in a finally on an already-cancelled task
            # re-raises CancelledError at the await point, so this TTL sweep
            # never ran for any cancelled job. asyncio.shield keeps the inner
            # coroutine running when that happens; the CancelledError raised
            # *here* is swallowed so it does not mask the original cancellation,
            # which resumes propagating once this finally completes.
            #
            # stop() additionally runs one final sweep after gathering, so the
            # shutdown path is covered even if the shielded task is still in
            # flight when the loop tears down.
            try:
                await asyncio.shield(
                    self._engine.cleanup_old_jobs(self._engine.completed_job_ttl_hours)
                )
            except asyncio.CancelledError:
                pass

    async def stop(self) -> None:
        """Stop the worker loop and cancel all in-progress jobs.

        Cancels all running tasks, drains the queue, and signals the
        run loop to exit via the _stopping flag.
        """
        self._stopping = True
        logger.info("Stopping processing engine worker...")

        # Cancel all in-progress tasks
        cancelled: list[asyncio.Task[None]] = []
        for job_id, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
                cancelled.append(task)
                job = self._engine.jobs.get(job_id)
                if job and job.status == ProcessingStatus.PROCESSING:
                    job.status = ProcessingStatus.CANCELLED
                    job.completed_at = datetime.now()

        # #4543: wait for the cancelled tasks to actually unwind. Previously
        # stop() cancelled and returned immediately, logging "worker stopped"
        # while jobs were still mid-unwind — a job parked in
        # asyncio.to_thread(processor.process, ...) kept a worker thread and a
        # HybridProcessor alive past the point the lifespan tore down the
        # library manager. The worker-task cancel below already did this
        # correctly; only the per-job tasks were fire-and-forget.
        #
        # Bounded so a task that refuses to unwind cannot hang shutdown. On
        # timeout we log and proceed: blocking teardown forever is worse than
        # a noisy exit, and silently swallowing it would recreate the bug.
        #
        # asyncio.wait — NOT wait_for(gather(...)). On timeout wait_for cancels
        # the inner future and then *awaits* it, so a task that swallows
        # CancelledError (a bare `except CancelledError: pass` around its work)
        # would hang stop() forever — the very failure this fix exists to
        # prevent. asyncio.wait leaves stragglers pending and returns.
        if cancelled:
            _, still_pending = await asyncio.wait(
                cancelled, timeout=self.STOP_DRAIN_TIMEOUT_SECONDS
            )
            if still_pending:
                logger.warning(
                    f"{len(still_pending)} job task(s) did not unwind within "
                    f"{self.STOP_DRAIN_TIMEOUT_SECONDS}s; proceeding with shutdown"
                )

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

        # Drop the finished task so a later `if worker._worker_task:` check
        # can't read a stopped worker as running (#4577).
        self._worker_task = None

        # #4543: one awaited sweep after everything has unwound, so the TTL
        # cleanup is guaranteed to have run for jobs cancelled during shutdown
        # rather than depending on a shielded task that may still be in flight.
        try:
            await self._engine.cleanup_old_jobs(self._engine.completed_job_ttl_hours)
        except Exception:
            logger.exception("Final cleanup_old_jobs sweep failed during stop()")

        logger.info("Processing engine worker stopped")

    async def start(self) -> None:
        """Start the job processing worker.

        Jobs are dispatched as concurrent tasks up to max_concurrent_jobs.
        The semaphore inside _run_job governs how many execute simultaneously;
        the loop itself never blocks on a running job (#2746).
        """
        self._stopping = False
        self._worker_task = asyncio.current_task()
        from helpers import spawn_background_task

        while not self._stopping:
            try:
                job = await self.job_queue.get()
                # Fire-and-forget: _run_job acquires a semaphore slot and
                # cleans up after itself.  The loop immediately returns to
                # dequeue the next job.  spawn_background_task attaches a
                # done-callback so an unhandled exception inside _run_job is
                # logged rather than silently swallowed (fixes #3512 / BE-NEW-54).
                spawn_background_task(
                    self._run_job(job), name=f"_run_job:{job.job_id}"
                )
            except Exception as e:
                logger.exception(f"Worker error: {e}")
                await asyncio.sleep(1)

    def cancel_task(self, job_id: str) -> None:
        """Cancel the in-flight task for a job, if any.

        **Must be called from the event-loop thread** (#4575). Both the
        ``self._tasks`` lookup and ``Task.cancel()`` are loop-affine: the dict
        is mutated from ``_run_job`` without synchronisation, and ``cancel()``
        is only safe on the loop that owns the task. From a worker thread
        (``asyncio.to_thread``, ``threading.Thread``) schedule the whole call
        via ``loop.call_soon_threadsafe`` instead. Every current caller —
        ``ProcessingEngine.cancel_job()`` — already runs on the loop.

        Silently does nothing when ``job_id`` is unknown or its task already
        finished.
        """
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
