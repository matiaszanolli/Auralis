#!/usr/bin/env python3

"""
process_job() orchestration for ProcessingEngine (#4250 follow-up)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`process_job()` was the last ~100-line chunk of `processing_engine.py`'s job
lifecycle: the try/except/finally orchestration that calls
`_prepare_job()` / `_execute_job()` / `_finalize_job()` (job_execution.py /
job_finalize.py) and handles every exit path — success, DSP timeout,
cooperative cancellation, and the catch-all failure branch — with a single
`finally` that reclaims the processor it owns exactly once (#4567) and always
clears the job's cancellation-token registry entry (#4496/#4759).

`ProcessingEngine.process_job()` stays a thin delegating method of the same
name so `patch.object(engine, "process_job", ...)` in
`tests/backend/test_cancel_job_stops_processing.py` and the plain
`await engine.process_job(job)` call sites across
`tests/backend/test_processing_engine.py`,
`tests/backend/test_process_job_nonblocking.py`,
`tests/backend/test_processor_return_on_failure.py`,
`tests/backend/test_cancel_job_stops_processing.py`, and
`core/job_worker.py`'s dispatch loop all keep working unmodified: those call
sites replace or invoke the bound method on the instance, which only works
while it's an attribute directly on `ProcessingEngine`.

`process_job()` takes the owning `ProcessingEngine` as its first argument
rather than duplicating its collaborators — it calls back into the engine's
own delegating methods (`engine._prepare_job`, `engine._execute_job`,
`engine._finalize_job`, `engine._notify_progress`, `engine._cleanup_processor`)
and its `_cancel_events` registry / `processing_timeout` attribute, so a test
that patches those engine-level names still intercepts calls made from here —
same pattern as `job_execution.py`'s `prepare_job()` / `execute_job()`.

`tests/backend/test_processor_return_on_failure.py::TestSingleReturnSite`
used `inspect.getsource(ProcessingEngine.process_job)` to assert the single
`_cleanup_processor()` call site lives inside a `finally:` block (#4567
regression guard). That assertion now targets
`inspect.getsource(job_lifecycle.process_job)` instead, since the delegating
method on `ProcessingEngine` no longer contains that source text — the same
category of patch-target rewrite the prior pass applied to
`load_audio`/`save` (now `core.job_execution.load_audio`/`.save`).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from core.job_error_mapping import _safe_error_message
from core.job_models import ProcessingJob, ProcessingStatus

if TYPE_CHECKING:
    from core.processing_engine import ProcessingEngine

__all__ = ["process_job"]

logger = logging.getLogger(__name__)


async def process_job(engine: "ProcessingEngine", job: ProcessingJob) -> None:
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
        audio, sample_rate, config, processor = await engine._prepare_job(job)
        audio_data = await engine._execute_job(job, audio, sample_rate, processor)
        engine._finalize_job(job, audio_data, sample_rate, processor)

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
            f"Processing timed out after {engine.processing_timeout:.0f}s"
        )
        job.completed_at = datetime.now()

        await engine._notify_progress(
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

        await engine._notify_progress(
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
                    engine._cleanup_processor(
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
            engine._cancel_events.pop(job.job_id, None)
