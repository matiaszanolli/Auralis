"""
Background Worker Initialization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The processing engine and the streamlined cache, each with a long-running
background task, plus the watchdog that marks a component unavailable when
its task dies after startup (#4318).

Split out of the former single-file config/startup.py (#5236).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from config.limits import UPLOAD_TEMP_DIRNAME

from .tempfiles import reclaim_stale_temp_entries

logger = logging.getLogger(__name__)


def _watch_critical_worker_task(
    task: asyncio.Task[Any],
    globals_dict: dict[str, Any],
    keys_to_clear: tuple[str, ...],
    service_name: str,
    *,
    teardown_key: str | None = None,
    teardown: Callable[[Any], Any] | None = None,
) -> None:
    """Null `globals_dict[key]` for each key if `task` dies unexpectedly.

    ProcessingEngine.start_worker() and StreamlinedCacheWorker._worker_loop()
    are long-running background tasks started once at startup. #3512 added a
    done-callback that LOGS a silently-failing task, but globals_dict stays
    truthy forever — routers gating on it keep accepting requests a dead
    worker will never service (jobs queue but never run; cache reads are
    permanent misses with no visible signal). This is a distinct failure
    mode from #3812 (a *synchronous* exception during startup, before the
    object was ever considered up) — here the task legitimately started,
    then died independently, so there's no exception to catch and roll back
    at startup time; it can only be caught when the task itself finishes
    (fixes #4318).

    Cancellation is NOT treated as a failure — it's the expected signal from
    an explicit `stop_worker()`/`worker.stop()` call during graceful
    shutdown, not an unexpected death.

    `teardown_key`/`teardown` (#4819): _shutdown_components gates calling
    the worker's own stop()/stop_worker() on `globals_dict.get(key)` being
    truthy — the EXACT key this function nulls above. An unexpected death
    therefore used to make shutdown skip real teardown entirely, leaking
    the worker's in-flight per-job asyncio.to_thread(...) DSP threads past
    LibraryDatabase.shutdown()/audio_player.cleanup() (an Electron quit that
    hangs). When both are given, the live object is snapshotted BEFORE
    nulling `globals_dict[teardown_key]` (so routers still see 503
    immediately) and `teardown(obj)` is scheduled as a background task so
    its cancellation of in-flight work still runs regardless of whether
    _shutdown_components' gate later reads a live or nulled global.
    """
    def _on_done(t: asyncio.Task[Any]) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.error(
                f"❌ {service_name} background task died unexpectedly — marking unavailable "
                f"({', '.join(keys_to_clear)} will now report 503 to routers)",
                exc_info=exc,
            )
        else:
            logger.error(
                f"❌ {service_name} background task exited without being stopped — marking "
                f"unavailable ({', '.join(keys_to_clear)} will now report 503 to routers)"
            )
        stale_obj = globals_dict.get(teardown_key) if teardown_key is not None else None
        for key in keys_to_clear:
            globals_dict[key] = None
        if stale_obj is not None and teardown is not None:
            from helpers import spawn_background_task
            logger.info(
                f"🔧 Running {service_name} teardown now so in-flight work is "
                f"cancelled even though {service_name} died before shutdown"
            )
            teardown_task = spawn_background_task(
                teardown(stale_obj), name=f"{service_name}.watchdog_teardown"
            )
            # #4819: fire-and-forget alone risks the SAME class of bug this
            # fix exists to close — if the process exits before the event
            # loop gets a turn to run it, the teardown never actually
            # happens. Tracked here so _shutdown_components can await it
            # as part of the same shutdown sequence rather than trusting it
            # completes on its own schedule.
            globals_dict.setdefault('_watchdog_teardown_tasks', []).append(teardown_task)

    task.add_done_callback(_on_done)


async def _init_processing_engine(HAS_PROCESSING: bool, globals_dict: dict[str, Any]) -> None:
    """Initialize the processing engine and its background worker."""
    if not HAS_PROCESSING:
        logger.warning("⚠️  Processing engine not available")
        return
    try:
        from core.processing_engine import ProcessingEngine

        globals_dict['processing_engine'] = ProcessingEngine(max_concurrent_jobs=2)

        # Age-sweep auralis_processing/auralis_uploads: cleanup_old_jobs()
        # is driven off the in-memory jobs registry, which is empty right
        # after a crash or restart, so leftovers from a previous run were
        # never reclaimed until now (#4762).
        _ttl = globals_dict['processing_engine'].completed_job_ttl_hours
        reclaim_stale_temp_entries(globals_dict['processing_engine'].temp_dir, _ttl)
        reclaim_stale_temp_entries(Path(tempfile.gettempdir()) / UPLOAD_TEMP_DIRNAME, _ttl)

        # Start the processing worker — retain strong reference to prevent GC,
        # and attach a done-callback so a silently-failing start_worker is
        # logged rather than disappearing (fixes #3512 / BE-NEW-54).
        from helpers import spawn_background_task
        globals_dict['_processing_worker_task'] = spawn_background_task(
            globals_dict['processing_engine'].start_worker(),
            name="processing_engine.start_worker",
        )
        # #3512's callback above only logs; also null the global so a
        # worker that dies AFTER startup returns stops accepting jobs
        # it will never run (fixes #4318).
        _watch_critical_worker_task(
            globals_dict['_processing_worker_task'],
            globals_dict,
            ('processing_engine',),
            "ProcessingEngine",
            teardown_key='processing_engine',
            teardown=lambda engine: engine.stop_worker(),
        )
        logger.info("✅ Processing Engine initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Processing Engine: {e}")
        # #3898: a failure anywhere after `globals_dict['processing_engine']`
        # is assigned above (e.g. reclaim_stale_temp_entries, spawn_background_task)
        # used to leave it truthy with no worker actually running.
        # processing_api's routes gate on `is None` -> 503; a stale truthy
        # entry made them accept jobs (202) that would queue forever, since
        # nothing dequeues them. Distinct from the #4318 case
        # _watch_critical_worker_task handles (a worker that started fine
        # then died later) -- this is the worker never having started at all.
        globals_dict.pop('processing_engine', None)
        globals_dict.pop('_processing_worker_task', None)


async def _init_streamlined_cache(HAS_STREAMLINED_CACHE: bool, globals_dict: dict[str, Any]) -> None:
    """Initialize the streamlined cache manager and its background worker (Beta.9)."""
    if not (HAS_STREAMLINED_CACHE and globals_dict.get('library_database')):
        if not HAS_STREAMLINED_CACHE:
            logger.warning("⚠️  Streamlined cache not available")
        elif not globals_dict.get('library_database'):
            logger.warning("⚠️  Library manager not available - streamlined cache disabled")
        return
    try:
        from cache import streamlined_cache_manager
        from core.streamlined_worker import StreamlinedCacheWorker

        # Use global singleton instance
        globals_dict['streamlined_cache'] = streamlined_cache_manager
        from cache.models import TIER1_MAX_SIZE_MB
        logger.info(f"✅ Streamlined Cache Manager initialized ({TIER1_MAX_SIZE_MB:.1f} MB Tier 1)")

        # Create and start worker
        globals_dict['streamlined_worker'] = StreamlinedCacheWorker(
            cache_manager=globals_dict['streamlined_cache'],
            library_database=globals_dict['library_database']
        )

        # Start the worker
        await globals_dict['streamlined_worker'].start()
        logger.info("✅ Streamlined Cache Worker started")

        # Null both the worker AND the cache manager if the worker's
        # background loop dies after startup returns — without a
        # populator the cache never fills, so routers should treat it
        # as unavailable (503) rather than serve permanent misses
        # silently (fixes #4318).
        worker_task = globals_dict['streamlined_worker'].worker_task
        if worker_task is not None:
            _watch_critical_worker_task(
                worker_task,
                globals_dict,
                ('streamlined_cache', 'streamlined_worker'),
                "StreamlinedCacheWorker",
                teardown_key='streamlined_worker',
                teardown=lambda worker: worker.stop(),
            )

    except Exception as e:
        logger.error(f"❌ Failed to initialize streamlined cache: {e}")
        # #3898 (sibling of the processing-engine case above): a failure
        # anywhere after `globals_dict['streamlined_cache']` is assigned
        # (e.g. StreamlinedCacheWorker construction, worker.start()) used to
        # leave it truthy with no worker actually draining it, so every
        # chunk request silently took the slow uncached path forever instead
        # of the router-level 503 a genuinely-unavailable cache should give.
        globals_dict.pop('streamlined_cache', None)
        globals_dict.pop('streamlined_worker', None)
