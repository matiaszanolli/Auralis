"""
Application Shutdown
~~~~~~~~~~~~~~~~~~~~

Tears down every long-lived component when the lifespan exits.

Split out of the former single-file config/startup.py (#5236).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any

from config.background_workers import stop_background_workers

from .rollback import (
    _clear_module_level_fingerprint_queue,
    _teardown_audio_player,
    _teardown_library_database,
    _teardown_player_state_manager,
)

logger = logging.getLogger(__name__)


async def _shutdown_components(globals_dict: dict[str, Any]) -> None:
    """Tear down every long-lived component, best-effort.

    Extracted from the lifespan body (#4569) for the same reason
    :py:func:`_rollback_partial_startup` was (#3812): it is otherwise only
    reachable by running the entire startup sequence.

    **Every step is individually guarded.** The three earliest steps used to sit
    bare inside one outer ``try``, so a single failing worker — a fingerprint
    queue that timed out, or a partially-initialised worker after a rolled-back
    startup — jumped straight to the outer handler and skipped everything after
    it, including ``LibraryDatabase.shutdown()`` and its SQLite WAL checkpoint.
    The outer ``try`` remains only as a last-resort net.
    """
    try:
        # Await any teardown a watchdog already scheduled for a worker that
        # died BEFORE this shutdown started (#4819). Ordered first: those
        # tasks cancel in-flight per-job DSP work, and every step below
        # this one assumes that work is no longer racing against teardown.
        # Fire-and-forget alone (_watch_critical_worker_task's
        # spawn_background_task call) risks the same class of bug this fix
        # closes if the process exits before the loop gives it a turn.
        pending_watchdog_teardowns = globals_dict.pop('_watchdog_teardown_tasks', None)
        if pending_watchdog_teardowns:
            try:
                await asyncio.wait(pending_watchdog_teardowns, timeout=10.0)
                logger.info(
                    f"✅ Awaited {len(pending_watchdog_teardowns)} watchdog-scheduled "
                    f"teardown task(s)"
                )
            except Exception as watchdog_err:
                logger.warning(f"⚠️  Watchdog teardown await failed: {watchdog_err}")

        # Stop the 1 Hz player-state broadcast FIRST (#4747). It was the only
        # long-lived task in the lifespan with no symmetric stop: started by
        # set_playing(True) and cancelled only by set_playing(False), so a
        # shutdown mid-playback left it broadcasting position_changed against
        # closing WebSockets until the event loop went away. Ordered ahead of
        # every other teardown so nothing below it races a broadcast.
        await _teardown_player_state_manager(globals_dict)

        # Stop the background workers (auto_scanner, ondemand + batch fingerprint
        # queues) through the shared helper so this path and the library-reset
        # endpoint can never diverge on which workers exist (#4111) *or* on how
        # they are stopped (#4569 — this loop was re-implemented inline without
        # the helper's per-worker guard). Order matches BACKGROUND_WORKER_KEYS:
        # auto_scanner first (it may be mid-scan and enqueue into the queues).
        for worker_key in await stop_background_workers(globals_dict.get):
            logger.info(f"✅ Background worker stopped: {worker_key}")
        # #4803: clear the module-global mirror too — see
        # _clear_module_level_fingerprint_queue's docstring. Inert once the
        # process is actually exiting, but keeps this path consistent with
        # _rollback_partial_startup rather than only fixing one of the two
        # places that stop this worker.
        _clear_module_level_fingerprint_queue()

        # Stop streamlined cache worker
        if globals_dict.get('streamlined_worker'):
            try:
                await globals_dict['streamlined_worker'].stop()
                logger.info("✅ Streamlined Cache Worker stopped")
            except Exception as sw_err:
                logger.warning(f"⚠️  Streamlined cache worker shutdown error: {sw_err}")

        # Stop processing engine
        if globals_dict.get('processing_engine'):
            try:
                await globals_dict['processing_engine'].stop_worker()
                logger.info("✅ Processing Engine stopped")
            except Exception as pe_err:
                logger.warning(f"⚠️  Processing engine shutdown error: {pe_err}")

        # Stop audio player and release hardware resources (#3210)
        _teardown_audio_player(globals_dict)

        # Drop every cached HybridProcessor. #3746 added this to reclaim each
        # instance's 5-thread fingerprint executor; that executor no longer
        # exists and close() releases nothing today (#4744), so what this
        # actually does now is free the cached instances themselves. The log
        # line says that rather than implying a thread-pool reclaim.
        try:
            from core.processor_factory import get_processor_factory
            get_processor_factory().clear_cache()
            logger.info("✅ Processor factory cache cleared (processors dropped)")
        except Exception as factory_err:
            logger.warning(f"⚠️  Processor factory shutdown error: {factory_err}")

        # Drain the ProcessingEngine's own ProcessorPool too (fixes #5061) —
        # a separate cache from ProcessorFactory's, previously never closed
        # on shutdown.
        if globals_dict.get('processing_engine'):
            try:
                await globals_dict['processing_engine'].close_processor_pool()
                logger.info("✅ Processing engine processor pool drained")
            except Exception as pool_err:
                logger.warning(f"⚠️  Processing engine pool shutdown error: {pool_err}")

        # Close the artwork downloader's shared aiohttp session, if one
        # was ever created (fixes #3915).
        try:
            from services.artwork_downloader import close_artwork_downloader
            await close_artwork_downloader()
            logger.info("✅ Artwork downloader session closed")
        except Exception as artwork_err:
            logger.warning(f"⚠️  Artwork downloader shutdown error: {artwork_err}")

        # Shut down the fingerprint ThreadPoolExecutor — previously only
        # reachable via atexit, which runs after this whole function (and
        # thus after the library database shutdown below), letting an
        # in-flight fingerprint computation race the WAL checkpoint /
        # engine dispose (#4756). Ordered before the database step, bounded
        # so a slow computation can't stall shutdown indefinitely.
        try:
            from analysis.fingerprint_generator import shutdown_fingerprint_executor_bounded
            await shutdown_fingerprint_executor_bounded()
            logger.info("✅ Fingerprint executor shutdown step complete")
        except Exception as fp_err:
            logger.warning(f"⚠️  Fingerprint executor shutdown error: {fp_err}")

        # Delete the idle converted temp WAVs kept for the next stream of the
        # same track (#5402); a stream released after this deletes its own.
        try:
            from core.seekable_source import converted_wavs
            await asyncio.to_thread(converted_wavs.shutdown)
        except Exception as temp_err:
            logger.warning(f"⚠️  Seekable temp WAV cleanup error: {temp_err}")

        # Shut down the library database last — WAL checkpoint + engine dispose (#3210)
        _teardown_library_database(globals_dict)

        # Thread pools last (#5086): every step above may offload work via
        # asyncio.to_thread, and the I/O pool IS the loop's default executor —
        # shutting it down earlier would make those calls raise
        # "cannot schedule new futures after shutdown" and skip the WAL
        # checkpoint. Non-blocking by design; see shutdown_executors().
        try:
            from core.executors import shutdown_executors
            shutdown_executors()
            logger.info("✅ Thread pools shut down")
        except Exception as pool_err:
            logger.warning(f"⚠️  Thread pool shutdown error: {pool_err}")

        logger.info("✅ Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
