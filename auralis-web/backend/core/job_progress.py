#!/usr/bin/env python3

"""
Progress-callback fan-out for the ProcessingEngine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Owns per-job progress subscriber lists and delivers ticks to them. Extracted
from processing_engine.py (#4250 follow-up: the mechanical pool/worker/
process_job split landed in 3b01a65e, but the engine module itself kept
growing past the 300-line convention through unrelated bugfixes — this is
the next safe slice out of it). Registration/removal/delivery semantics are
unchanged (preserves #3868, #3325).

The notifier shares the engine's `jobs` dict and `_jobs_lock` by reference
(constructor injection, same pattern ProcessorPool uses for its processor
factory) rather than owning a copy, so a progress update still sees the same
job objects create_job()/cancel_job() mutate.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from core.job_models import ProcessingJob

logger = logging.getLogger(__name__)


class ProgressNotifier:
    """Per-job list of progress-update subscribers, with safe fan-out delivery."""

    def __init__(
        self,
        jobs: dict[str, ProcessingJob],
        jobs_lock: asyncio.Lock,
    ) -> None:
        self._jobs = jobs
        self._jobs_lock = jobs_lock
        # Per job_id. A LIST, not a single callable (#3868): each WebSocket
        # that subscribes to a job registers its own closure, and a
        # single-value dict silently let the newest subscriber overwrite
        # every earlier one — so with two subscribers (multi-window
        # Electron, or one client subscribing twice) all but the last
        # stopped receiving `job_progress` events, with no error anywhere.
        self.callbacks: dict[str, list[Callable[..., Any]]] = {}

    async def register(self, job_id: str, callback: Callable[..., Any]) -> None:
        """Add a callback for job progress updates.

        Additive: every subscriber for `job_id` is retained and notified
        (#3868). Re-registering the same callable is a no-op rather than a
        double subscription, so a duplicate `subscribe_job_progress` cannot
        make the client receive each tick twice.
        """
        async with self._jobs_lock:
            callbacks = self.callbacks.setdefault(job_id, [])
            if callback not in callbacks:
                callbacks.append(callback)

    async def unregister(
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
                self.callbacks.pop(job_id, None)
                return
            callbacks = self.callbacks.get(job_id)
            if not callbacks:
                return
            # Identity/equality removal; tolerate an already-removed callback so
            # a self-unregister racing with disconnect cleanup is not an error.
            try:
                callbacks.remove(callback)
            except ValueError:
                pass
            if not callbacks:
                self.callbacks.pop(job_id, None)

    async def notify(self, job_id: str, progress: float, message: str = "") -> None:
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
            job = self._jobs.get(job_id)
            if job:
                job.progress = progress
            # Snapshot: the awaits below run outside the lock, and a callback
            # may unregister itself (or others) while we are iterating.
            callbacks = list(self.callbacks.get(job_id, ()))

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
            remaining = self.callbacks.get(job_id)
            if remaining is None:
                return
            for cb in failed:
                try:
                    remaining.remove(cb)
                except ValueError:
                    pass
            if not remaining:
                self.callbacks.pop(job_id, None)
