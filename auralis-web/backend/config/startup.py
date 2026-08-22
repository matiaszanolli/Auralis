"""
Application Lifespan Manager

Manages component initialization and cleanup via FastAPI lifespan context manager:
- Library database setup
- Settings repository initialization
- Audio player creation
- State manager initialization
- Similarity system setup
- Processing engine setup
- Cache system setup

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import logging
import os
import shutil
import tempfile
import threading
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from config.background_workers import (
    BACKGROUND_WORKER_KEYS,
    WORKER_STOP_KWARGS,
    stop_background_workers,
)
from config.limits import (
    CHUNK_TEMP_DIRNAME,
    CHUNK_TEMP_OWNER_FILENAME,
    STREAM_TEMP_PREFIX,
    UPLOAD_TEMP_DIRNAME,
    owning_pid_from_stream_temp_name,
)

logger = logging.getLogger(__name__)


# Background services that may already be running (spawned their own workers
# / tasks) by the time a later startup step fails. Rollback must await each
# one's .stop() before nulling it out, not just drop the reference — an
# already-running fingerprint queue or auto-scanner would otherwise keep
# calling into a library_manager that's about to be rolled back to None
# (#3812 / BE-MW-3, regression of #3540 / BE-NEW-82).
# Derived from the canonical set (#4569) rather than re-listed, so a worker
# added to BACKGROUND_WORKER_KEYS is automatically covered by rollback and
# cannot be stopped with different kwargs here than during shutdown.
_ROLLBACK_SERVICES_TO_STOP: tuple[tuple[str, dict[str, Any]], ...] = tuple(
    (_key, WORKER_STOP_KWARGS.get(_key, {})) for _key in BACKGROUND_WORKER_KEYS
)

# Components that only need to be nulled on rollback (never started an async
# task of their own, or are handled by _ROLLBACK_SERVICES_TO_STOP above).
_ROLLBACK_COMPONENTS_TO_NULL: tuple[str, ...] = (
    'library_manager', 'repository_factory', 'settings_repository',
    'audio_player', 'player_state_manager',
    'streamlined_cache', 'similarity_system', 'graph_builder',
)


async def _rollback_partial_startup(globals_dict: dict[str, Any]) -> None:
    """Roll back partially-initialised globals after a startup failure.

    So downstream routers see a coherent 'not ready' state instead of
    'library_manager truthy but everything else None' (#3540 / BE-NEW-82).
    Router dependencies that gate on library_manager truthy will then return
    503 rather than AttributeError -> 500.

    Extracted as a standalone function (#3812) so this behavior — especially
    awaiting .stop() on already-running background services before nulling
    them — is directly unit-testable without needing to mock the entire
    Auralis startup import chain.
    """
    for _svc_key, _stop_kwargs in _ROLLBACK_SERVICES_TO_STOP:
        _svc = globals_dict.get(_svc_key)
        if _svc is not None:
            try:
                await _svc.stop(**_stop_kwargs)
            except Exception as _stop_exc:
                logger.warning(f"⚠️  Error stopping {_svc_key} during rollback: {_stop_exc}")
            finally:
                globals_dict[_svc_key] = None
    for _component in _ROLLBACK_COMPONENTS_TO_NULL:
        globals_dict[_component] = None

    # #4803: the on-demand fingerprint queue is installed in two places —
    # this registry (nulled by the loop above) and a module-level global via
    # set_fingerprint_queue(), which all 8 real consumers actually read
    # through get_fingerprint_queue(). Rollback only knew about the registry
    # entry, so the module global kept returning the same (now-stopped)
    # FingerprintQueue object post-rollback and consumers silently enqueued
    # work onto a queue that will never run instead of taking their
    # unavailable branch.
    _clear_module_level_fingerprint_queue()


def _clear_module_level_fingerprint_queue() -> None:
    """Null analysis.fingerprint_queue's module-global singleton (#4803).

    Deferred import mirrors the try/except-wrapped import used where the
    queue is created (startup may run with HAS_AURALIS False / the analysis
    package unavailable, e.g. demo mode) — this must never itself raise and
    abort the rollback/shutdown sequence it's called from.
    """
    try:
        from analysis.fingerprint_queue import set_fingerprint_queue
        set_fingerprint_queue(None)
    except Exception as _fq_exc:
        logger.warning(f"⚠️  Error clearing module-level fingerprint queue: {_fq_exc}")


def _install_thread_pools() -> None:
    """Install the explicit streaming + I/O thread pools (#5086/#4810).

    Guarded like every other startup step: the app is fully functional
    without the split (every `to_thread` simply falls back to CPython's
    default pool, the pre-#5086 behaviour), so a failure here must degrade
    rather than abort startup.
    """
    try:
        from core.executors import install_executors
        install_executors()
        logger.info("✅ Thread pools installed (streaming + I/O)")
    except Exception as pool_err:
        logger.warning(
            f"⚠️  Thread pool installation failed, falling back to the default "
            f"executor for all offloaded work: {pool_err}"
        )


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
        # Stop the 1 Hz player-state broadcast FIRST (#4747). It was the only
        # long-lived task in the lifespan with no symmetric stop: started by
        # set_playing(True) and cancelled only by set_playing(False), so a
        # shutdown mid-playback left it broadcasting position_changed against
        # closing WebSockets until the event loop went away. Ordered ahead of
        # every other teardown so nothing below it races a broadcast.
        if globals_dict.get('player_state_manager'):
            try:
                await globals_dict['player_state_manager'].shutdown()
                logger.info("✅ Player state manager stopped")
            except Exception as psm_err:
                logger.warning(f"⚠️  Player state manager shutdown error: {psm_err}")

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
        if globals_dict.get('audio_player'):
            try:
                player = globals_dict['audio_player']
                if hasattr(player, 'stop'):
                    player.stop()
                if hasattr(player, 'cleanup'):
                    player.cleanup()
                logger.info("✅ Audio Player stopped")
            except Exception as player_err:
                logger.warning(f"⚠️  Audio player shutdown error: {player_err}")

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

        # Shut down the library database last — WAL checkpoint + engine dispose (#3210)
        if globals_dict.get('library_manager'):
            try:
                globals_dict['library_manager'].shutdown()
                logger.info("✅ Library database shut down (WAL checkpointed)")
            except Exception as lm_err:
                logger.warning(f"⚠️  Library database shutdown error: {lm_err}")

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


def _watch_critical_worker_task(
    task: asyncio.Task[Any],
    globals_dict: dict[str, Any],
    keys_to_clear: tuple[str, ...],
    service_name: str,
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
        for key in keys_to_clear:
            globals_dict[key] = None

    task.add_done_callback(_on_done)


def pid_is_alive(pid: int) -> bool:
    """True if a process with `pid` currently exists.

    Via psutil (already a hard dependency) rather than ``os.kill(pid, 0)``:
    on Windows CPython implements ``os.kill`` for non-CTRL signals by opening
    the process and calling ``TerminateProcess`` — a liveness *probe* written
    that way would kill the process it is asking about.

    A dead PID can be recycled, so a True answer is not proof the process is
    still *ours*. Callers must treat this as "do not touch", never as "this is
    definitely an Auralis instance".
    """
    try:
        import psutil
        return bool(psutil.pid_exists(pid))
    except Exception as e:  # psutil missing or platform refusal — fail safe
        logger.debug(f"PID liveness check unavailable for {pid}: {e}")
        return True


def reclaim_leftover_stream_temps(temp_root: Path, max_age_hours: float = 1.0) -> int:
    """Remove temp WAV dirs orphaned by interrupted compressed-format streams.

    stream_normal_audio writes a temp WAV under ``auralis_stream_<pid>_*`` and
    cleans it in its finally block, but a crash or a locked file (Windows AV /
    cloud-sync) can leave one behind (#3877). Sweep them on startup so any leak
    surfaces in the log and stays bounded.

    #4713: this used to ``rmtree`` **every** match with no ownership or age
    check, so a second backend — a dev running ``main.py --dev`` on an alternate
    port while the packaged app is open, or a test pointed at the real temp root
    — deleted the *live* temp WAVs of the running instance, producing
    file-not-found errors mid-playback in the other process.

    Two guards, in order:

    - **PID tag (exact).** Directories written by #4713 or later carry the
      owning PID. A directory whose PID is still alive is skipped outright, no
      matter how old — a long audiobook or DJ set can legitimately hold one open
      for hours.
    - **Age (fallback).** A directory with no PID tag predates the tagging (or
      came from something else), so ownership is unknowable; anything modified
      within `max_age_hours` is left alone on the assumption it may be live.

    Args:
        temp_root: Directory to sweep (the system temp root in production).
        max_age_hours: Age below which an *untagged* directory is left alone.

    Returns the number of leftover directories successfully reclaimed — skipped
    directories are excluded from the count, which is what the log line reports.
    """
    reclaimed = 0
    skipped = 0
    cutoff = time.time() - (max_age_hours * 3600)

    for leftover in temp_root.glob(f"{STREAM_TEMP_PREFIX}*"):
        owner_pid = owning_pid_from_stream_temp_name(leftover.name)

        if owner_pid is not None:
            if pid_is_alive(owner_pid):
                skipped += 1
                continue
        else:
            # Untagged: no ownership information, so fall back to age.
            try:
                if leftover.stat().st_mtime >= cutoff:
                    skipped += 1
                    continue
            except OSError:
                # Vanished between glob and stat — nothing to reclaim.
                continue

        try:
            shutil.rmtree(leftover)
            reclaimed += 1
        except Exception as e:
            logger.warning(f"Failed to remove leftover temp stream dir {leftover}: {e}")

    if reclaimed:
        logger.info(
            f"🧹 Reclaimed {reclaimed} leftover temp stream dir(s) from dead/aged owners"
        )
    if skipped:
        logger.debug(f"Left {skipped} in-use temp stream dir(s) alone (#4713)")
    return reclaimed


def claim_chunk_cache(chunk_dir: Path, owner_marker: Path) -> bool:
    """Decide whether this process may wipe the shared chunk cache, and claim it.

    #4713: the wipe was unconditional, so a second backend starting up deleted
    the cached chunks a running instance was still serving from.

    Deliberately an *ownership* check rather than the age heuristic used for
    stream temps. Making the wipe age-conditional would change the blast radius
    of #4666 (the on-disk chunk cache is not keyed on mastering targets) from
    intra-session to cross-session, because the start-of-run wipe is what
    currently keeps stale un-targeted chunks from outliving a restart. Keying on
    ownership instead preserves that exactly: a lone instance — every packaged
    Electron run — still finds no live foreign owner and still wipes on every
    start. Only the concurrent-instance case, which is the actual defect here,
    takes the new path.

    Returns True when the caller should wipe. Always (re)claims the marker so
    the *next* start sees this process as the owner.
    """
    may_wipe = True
    try:
        if owner_marker.exists():
            recorded = owner_marker.read_text().strip()
            if recorded.isdigit():
                other_pid = int(recorded)
                if other_pid != os.getpid() and pid_is_alive(other_pid):
                    logger.info(
                        f"🔒 Chunk cache is claimed by live PID {other_pid}; "
                        f"leaving {chunk_dir.name} alone (#4713)"
                    )
                    may_wipe = False
    except OSError as e:
        logger.debug(f"Could not read chunk-cache owner marker: {e}")

    try:
        owner_marker.parent.mkdir(parents=True, exist_ok=True)
        owner_marker.write_text(str(os.getpid()))
    except OSError as e:
        logger.debug(f"Could not claim chunk-cache owner marker: {e}")

    return may_wipe


def reclaim_stale_temp_entries(dir_path: Path, max_age_hours: float) -> int:
    """Age-sweep stale files/dirs directly under ``dir_path``.

    ``auralis_processing`` (rendered job outputs) and ``auralis_uploads``
    (uploaded inputs, up to 500MB each) are otherwise only reclaimed by
    ``ProcessingEngine.cleanup_old_jobs()``, which is driven off the
    in-memory ``self.jobs`` registry — empty after any crash or restart, so
    anything left on disk at that point becomes permanently unreferenced
    (#4762). Sweeping by mtime age instead of registry membership catches
    those too.

    Returns the number of entries successfully reclaimed.
    """
    if not dir_path.exists():
        return 0
    reclaimed = 0
    cutoff = time.time() - (max_age_hours * 3600)
    for entry in dir_path.iterdir():
        try:
            if entry.stat().st_mtime >= cutoff:
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            reclaimed += 1
        except Exception as e:
            logger.warning(f"Failed to remove stale temp entry {entry}: {e}")
    if reclaimed:
        logger.info(f"🧹 Reclaimed {reclaimed} stale entr{'y' if reclaimed == 1 else 'ies'} from {dir_path.name}")
    return reclaimed


async def _cleanup_temp_directories() -> None:
    """Clear stale chunk cache and orphaned stream temp files on startup.

    Offloaded via asyncio.to_thread (#4754) — up to 512 MB of cached WAVs,
    previously removed directly on the event loop during lifespan startup.
    """
    temp_root = Path(tempfile.gettempdir())
    chunk_dir = temp_root / CHUNK_TEMP_DIRNAME
    owner_marker = temp_root / CHUNK_TEMP_OWNER_FILENAME

    # #4713: only wipe when no *live* foreign backend has claimed the shared
    # cache. A lone instance (every packaged run) still wipes on every start,
    # so #4666's stale-chunk blast radius stays intra-session.
    if await asyncio.to_thread(claim_chunk_cache, chunk_dir, owner_marker):
        if chunk_dir.exists():
            try:
                await asyncio.to_thread(shutil.rmtree, chunk_dir)
                chunk_dir.mkdir(exist_ok=True)
                logger.info(f"🧹 Cleared chunk directory: {chunk_dir.name}")
            except Exception as e:
                logger.warning(f"Failed to clear chunk directory: {e}")

    # Sweep temp WAVs orphaned by interrupted compressed-format streams (#3877),
    # skipping any a live process still owns (#4713).
    await asyncio.to_thread(reclaim_leftover_stream_temps, temp_root)


def _init_library_database(globals_dict: dict[str, Any]) -> None:
    """Open the library database and repository factory.

    No try/except of its own — a failure here must propagate to the
    caller so the outer Auralis-init rollback (#3812) reverts the whole
    component set, matching the original inline behavior exactly.
    """
    from auralis.library import LibraryDatabase

    # Ensure database directory exists before opening the library DB
    music_dir = Path.home() / "Music" / "Auralis"
    music_dir.mkdir(parents=True, exist_ok=True)
    # Absolute home/database paths are sensitive and persist to the
    # on-disk electron-log, so they log at DEBUG — consistent with the
    # #3844 demotion of the sibling path-validation logs (#4376).
    logger.debug(f"📁 Database directory ready: {music_dir}")

    # Open the library database. #4619: this used to construct the
    # deprecated LibraryManager, so every boot fired the
    # DeprecationWarning that its own message says precedes removal
    # in v2.0.0 — a promise that could not be kept while the class
    # was load-bearing. LibraryDatabase owns the migration, engine,
    # session factory, scan slots and shutdown; LibraryManager is
    # now only the legacy query facade over it.
    globals_dict['library_manager'] = LibraryDatabase()
    logger.info("✅ Auralis library database initialized")
    logger.debug(f"📊 Database location: {globals_dict['library_manager'].database_path}")

    # Repository factory for dependency injection. It is owned by
    # LibraryDatabase so every consumer — routers via this key and
    # components handed the database object — shares one instance
    # instead of building a second factory over the same sessions.
    globals_dict['repository_factory'] = globals_dict['library_manager'].repositories
    logger.info("✅ Repository Factory initialized (Phase 2 support)")


async def _init_fingerprint_extraction_queue(globals_dict: dict[str, Any]) -> None:
    """Start the CPU-based fingerprint extraction queue (36x speedup).

    Note: GPU batch processing was causing memory exhaustion crashes.
    CPU parallelization provides better stability and consistent
    performance. Own try/except: a failure here must not abort the rest
    of Auralis component initialization (matches original inline
    behavior).
    """
    try:
        from auralis.services.fingerprint_extractor import (
            FingerprintExtractor,
        )
        from auralis.services.fingerprint_queue import (
            FingerprintExtractionQueue,
        )

        # Create fingerprint extractor with library manager's fingerprint repository
        fingerprint_extractor = FingerprintExtractor(
            fingerprint_repository=globals_dict['library_manager'].fingerprints,
            track_repository=globals_dict['library_manager'].tracks,
        )
        logger.info("✅ Fingerprint Extractor initialized")

        # Create CPU-based fingerprint queue (24+ workers, 36x speedup)
        fingerprint_queue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor,
            get_repository_factory=lambda: globals_dict.get('repository_factory'),  # type: ignore[arg-type, return-value]
            num_workers=None,  # Auto-detect CPU cores
            max_workers=None  # Auto-size based on system
        )

        # Start background workers
        await fingerprint_queue.start()
        logger.info(f"✅ Fingerprint extraction queue started ({fingerprint_queue.num_workers} workers, 36x CPU speedup)")

        # Store for later reference
        globals_dict['fingerprint_queue'] = fingerprint_queue
        globals_dict['gpu_processor'] = None  # GPU disabled

    except Exception as fp_e:
        logger.warning(f"⚠️  Failed to initialize fingerprinting system: {fp_e}")


def _seed_settings_and_enhancement(globals_dict: dict[str, Any]) -> None:
    """Wire the settings repository and seed runtime enhancement settings.

    Settings-repository assignment has no try/except of its own
    (propagates to the outer rollback, matching original behavior);
    seeding enhancement settings from persisted user settings is
    best-effort and independently caught, as it was originally.
    """
    # Settings repository — taken from the shared factory rather
    # than constructed again over the same session factory (#4619).
    globals_dict['settings_repository'] = globals_dict['repository_factory'].settings
    logger.info("✅ Settings Repository initialized")

    # Seed the runtime enhancement settings from persisted user
    # settings so a saved default preset / intensity / auto-enhance
    # actually affects playback (#4409). Without this the dict stays
    # hardcoded adaptive/1.0/enabled. seed_enhancement_settings mutates
    # in place — routers captured this exact dict object via
    # deps['enhancement_settings'].
    try:
        from helpers import seed_enhancement_settings
        _user_settings = globals_dict['settings_repository'].get_settings()
        seed_enhancement_settings(globals_dict['enhancement_settings'], _user_settings)
        logger.info(
            f"✅ Enhancement settings seeded from user settings: "
            f"{globals_dict['enhancement_settings']}"
        )
    except Exception as e:
        logger.warning(f"⚠️  Failed to seed enhancement settings: {e}")


def _register_scan_folders(globals_dict: dict[str, Any]) -> None:
    """Register user-configured scan folders as allowed directories so
    validate_file_path accepts files from custom locations."""
    try:
        import json
        from security.path_security import register_allowed_directory
        settings = globals_dict['settings_repository'].get_settings()
        if settings and settings.scan_folders:
            folders = json.loads(settings.scan_folders) if isinstance(settings.scan_folders, str) else settings.scan_folders
            for folder in folders:
                register_allowed_directory(Path(folder))
            logger.info(f"✅ Registered {len(folders)} scan folder(s) as allowed directories")
    except Exception as e:
        logger.warning(f"⚠️  Failed to register scan folders: {e}")


def _init_reference_cloud_refresh(globals_dict: dict[str, Any]) -> Callable[..., None]:
    """Create and wire the shared reference-cloud refresh closure (#3479).

    Invoked by scanner end-of-run and fingerprint-queue drain hooks (and
    the REST refresh endpoint). The seeder is idempotent and reads
    existing fingerprint rows — no audio I/O — so calling it from
    multiple producers is safe. Returns the closure so the caller can
    also hand it to the auto-scanner as its on_scan_complete callback.
    """
    def _refresh_reference_cloud(*_args: Any, **_kwargs: Any) -> None:
        try:
            from auralis.learning.reference_seeder import refresh_cloud
            factory = globals_dict.get('repository_factory')
            if factory is None:
                return
            cleared, selected = refresh_cloud(factory.fingerprints)
            logger.info(
                f"🎯 Reference cloud refreshed: cleared {cleared}, "
                f"selected {selected}"
            )
        except Exception as rc_exc:
            logger.warning(f"Reference cloud refresh failed: {rc_exc}")

    globals_dict['refresh_reference_cloud'] = _refresh_reference_cloud

    # Wire the fingerprint queue drain hook now that we have the
    # closure available (queue itself was started earlier).
    _fpq = globals_dict.get('fingerprint_queue')
    if _fpq is not None:
        _fpq.set_drained_callback(_refresh_reference_cloud)

    return _refresh_reference_cloud


async def _start_auto_scanner(
    manager: Any,
    globals_dict: dict[str, Any],
    on_scan_complete: Callable[..., None],
) -> None:
    """Start the library auto-scanner service.

    Replaces the old one-shot ~/Music scan with a proper service that:
    - reads scan_folders from user settings (not hardcoded)
    - uses watchdog for real-time detection + periodic polling fallback
    - removes stale tracks (cleanup_missing_files) after each cycle
    - handles crashes gracefully with 30s back-off
    """
    try:
        from services.library_auto_scanner import LibraryAutoScanner
        auto_scanner = LibraryAutoScanner(
            settings_repo=globals_dict['settings_repository'],
            library_manager=globals_dict['library_manager'],
            fingerprint_queue=globals_dict.get('fingerprint_queue'),
            connection_manager=manager,
            on_scan_complete=on_scan_complete,
        )
        await auto_scanner.start()
        globals_dict['auto_scanner'] = auto_scanner
    except Exception as as_e:
        logger.warning(f"⚠️  Failed to start LibraryAutoScanner: {as_e}")


def _init_audio_player(manager: Any, globals_dict: dict[str, Any]) -> None:
    """Initialize the enhanced audio player and player state manager.

    No try/except of its own — propagates to the outer Auralis-init
    rollback, matching original inline behavior.
    """
    from auralis.player.config import PlayerConfig
    from auralis.player import AudioPlayer
    from core.state_manager import PlayerStateManager

    # Initialize enhanced audio player with optimized config
    player_config = PlayerConfig(
        buffer_size=1024,
        sample_rate=44100,
        enable_level_matching=True,
        enable_frequency_matching=False,
        enable_stereo_width=False,
        enable_auto_mastering=False,
        enable_advanced_smoothing=True,
        max_db_change_per_second=2.0
    )
    globals_dict['audio_player'] = AudioPlayer(
        player_config,
        get_repository_factory=lambda: globals_dict.get('repository_factory')
    )
    logger.info("✅ Enhanced Audio Player initialized (Phase 4 RepositoryFactory support enabled)")

    # Initialize state manager (must be after library_manager is created)
    globals_dict['player_state_manager'] = PlayerStateManager(manager)
    logger.info("✅ Player State Manager initialized")


async def _init_ondemand_fingerprint_queue(globals_dict: dict[str, Any]) -> None:
    """Initialize on-demand fingerprint queue (Phase 7.4).

    Handles 404s during similarity lookup - queues tracks for
    background processing.
    """
    try:
        from analysis.fingerprint_generator import FingerprintGenerator
        from analysis.fingerprint_queue import (
            FingerprintQueue,
            set_fingerprint_queue,
        )

        # Create FingerprintGenerator for the queue
        fp_generator = FingerprintGenerator(
            session_factory=globals_dict['library_manager'].SessionLocal,
            get_repository_factory=lambda: globals_dict.get('repository_factory')
        )

        # Helper to get track filepath
        def get_track_filepath(track_id: int) -> str | None:
            try:
                factory = globals_dict.get('repository_factory')
                if factory:
                    track = factory.tracks.get_by_id(track_id)
                    if track and track.filepath:
                        return str(track.filepath)
            except Exception:
                # Best-effort lookup (#4368 — was a bare pass,
                # hiding genuine repository failures from debugging).
                logger.debug(f"Track filepath lookup failed for {track_id}", exc_info=True)
            return None

        # Create and start on-demand fingerprint queue
        ondemand_queue = FingerprintQueue(
            fingerprint_generator=fp_generator,
            get_track_filepath=get_track_filepath
        )
        await ondemand_queue.start()
        set_fingerprint_queue(ondemand_queue)
        globals_dict['ondemand_fingerprint_queue'] = ondemand_queue
        logger.info("✅ On-demand fingerprint queue started (background processing for 404s)")

    except Exception as odq_e:
        logger.warning(f"⚠️  Failed to initialize on-demand fingerprint queue: {odq_e}")


def _init_similarity_system(HAS_SIMILARITY: bool, globals_dict: dict[str, Any]) -> None:
    """Initialize the fingerprint similarity system and K-NN graph builder."""
    if not HAS_SIMILARITY:
        return
    try:
        from auralis.analysis.fingerprint import (
            FingerprintSimilarity,
            KNNGraphBuilder,
        )

        globals_dict['similarity_system'] = FingerprintSimilarity(
            globals_dict['library_manager'].fingerprints
        )
        logger.info("✅ Fingerprint Similarity System initialized")

        # #4139: auto-fit in the background so an existing
        # library gets working recommendations without a manual
        # /api/similarity/fit call. fit() is a no-op (returns
        # False) below min_samples (fresh install / library
        # reset), leaving the system unfitted — the similarity
        # router then surfaces a clear 503 rather than silently
        # empty results. Runs off the startup path because
        # normalizer.fit() streams every fingerprint in batches.
        globals_dict['graph_builder'] = None

        def _auto_fit_similarity(
            sim_system=globals_dict['similarity_system'],
            lib_mgr=globals_dict['library_manager'],
            gd=globals_dict,
            builder_cls=KNNGraphBuilder,
        ):
            try:
                if sim_system.fit():
                    # get_component reads globals fresh per
                    # request, so this late assignment is picked up.
                    gd['graph_builder'] = builder_cls(
                        similarity_system=sim_system,
                        session_factory=lib_mgr.SessionLocal,
                    )
                    logger.info("✅ Similarity auto-fitted; K-NN Graph Builder ready")
                else:
                    logger.info("ℹ️  Similarity auto-fit skipped (not enough fingerprints yet)")
            except Exception as fit_e:
                logger.warning(f"⚠️  Similarity auto-fit failed: {fit_e}")

        threading.Thread(
            target=_auto_fit_similarity,
            name="similarity-autofit",
            daemon=True,
        ).start()
    except Exception as sim_e:
        logger.warning(f"⚠️  Failed to initialize Similarity System: {sim_e}")
        globals_dict['similarity_system'] = None
        globals_dict['graph_builder'] = None


async def _init_auralis_components(
    HAS_AURALIS: bool,
    HAS_SIMILARITY: bool,
    manager: Any,
    globals_dict: dict[str, Any],
) -> None:
    """Initialize the full Auralis component set: library DB,
    fingerprinting, settings, player, similarity (#4671).

    All sub-steps run under one rollback boundary (#3812): a failure
    anywhere in this sequence rolls back every already-initialized
    component to a coherent 'not ready' state (_rollback_partial_startup)
    rather than leaving some components truthy and others None, so
    downstream routers gate correctly. Individual sub-steps that already
    tolerated their own failure before this extraction (fingerprint
    queue, settings seeding, scan folders, auto-scanner, on-demand
    queue, similarity) still catch internally and do not trigger this
    rollback; sub-steps with no internal try/except before this
    extraction (library DB, audio player/state manager) still propagate
    to it — this preserves the exact original failure semantics, not
    just the original code layout.
    """
    if not HAS_AURALIS:
        logger.warning("⚠️  Auralis not available - running in demo mode")
        return

    try:
        _init_library_database(globals_dict)
        await _init_fingerprint_extraction_queue(globals_dict)
        _seed_settings_and_enhancement(globals_dict)
        _register_scan_folders(globals_dict)
        refresh_reference_cloud = _init_reference_cloud_refresh(globals_dict)
        await _start_auto_scanner(manager, globals_dict, refresh_reference_cloud)
        _init_audio_player(manager, globals_dict)
        await _init_ondemand_fingerprint_queue(globals_dict)
        _init_similarity_system(HAS_SIMILARITY, globals_dict)
    except Exception as e:
        import traceback
        logger.error(f"❌ Failed to initialize Auralis components: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        logger.error("⚠️  Auralis library initialization failed - rolling back partial state; API will return 503")
        await _rollback_partial_startup(globals_dict)


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
        )
        logger.info("✅ Processing Engine initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Processing Engine: {e}")


async def _init_streamlined_cache(HAS_STREAMLINED_CACHE: bool, globals_dict: dict[str, Any]) -> None:
    """Initialize the streamlined cache manager and its background worker (Beta.9)."""
    if not (HAS_STREAMLINED_CACHE and globals_dict.get('library_manager')):
        if not HAS_STREAMLINED_CACHE:
            logger.warning("⚠️  Streamlined cache not available")
        elif not globals_dict.get('library_manager'):
            logger.warning("⚠️  Library manager not available - streamlined cache disabled")
        return
    try:
        from cache import streamlined_cache_manager
        from core.streamlined_worker import StreamlinedCacheWorker

        # Use global singleton instance
        globals_dict['streamlined_cache'] = streamlined_cache_manager
        from cache.manager import TIER1_MAX_SIZE_MB
        logger.info(f"✅ Streamlined Cache Manager initialized ({TIER1_MAX_SIZE_MB:.1f} MB Tier 1)")

        # Create and start worker
        globals_dict['streamlined_worker'] = StreamlinedCacheWorker(
            cache_manager=globals_dict['streamlined_cache'],
            library_manager=globals_dict['library_manager']
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
            )

    except Exception as e:
        logger.error(f"❌ Failed to initialize streamlined cache: {e}")


def create_lifespan(deps: dict[str, Any]):
    """
    Create a lifespan context manager for FastAPI application.

    Args:
        deps: Dictionary of dependencies (globals dict to populate):
            - HAS_AURALIS: bool
            - HAS_PROCESSING: bool
            - HAS_STREAMLINED_CACHE: bool
            - HAS_SIMILARITY: bool
            - manager: ConnectionManager
            - globals: Dict to populate with component instances

    Returns:
        An async context manager suitable for FastAPI's lifespan parameter
    """

    # Extract dependencies
    HAS_AURALIS: bool = deps.get('HAS_AURALIS', False)
    HAS_PROCESSING: bool = deps.get('HAS_PROCESSING', False)
    HAS_STREAMLINED_CACHE: bool = deps.get('HAS_STREAMLINED_CACHE', False)
    HAS_SIMILARITY: bool = deps.get('HAS_SIMILARITY', False)
    manager: Any = deps.get('manager')
    globals_dict: dict[str, Any] = deps.get('globals', {})

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # === Startup ===
        # Order is load-bearing (#4671): library DB before anything that
        # reads it, settings before scan-folder registration and player
        # init, fingerprint queue before its drain hook is wired.
        # Processing engine and streamlined cache are independent of the
        # Auralis component set and of each other.
        # Thread pools first: this replaces the loop's default executor, so
        # it must happen before anything issues an asyncio.to_thread call
        # (#5086/#4810). Installing it later would leave early startup work
        # on CPython's implicit pool and, worse, hand out futures against a
        # pool that is about to stop being the default.
        _install_thread_pools()

        await _cleanup_temp_directories()
        await _init_auralis_components(HAS_AURALIS, HAS_SIMILARITY, manager, globals_dict)
        await _init_processing_engine(HAS_PROCESSING, globals_dict)
        await _init_streamlined_cache(HAS_STREAMLINED_CACHE, globals_dict)

        # #4801: try/finally so a BaseException thrown into this generator at
        # the yield (e.g. CancelledError from a forced/second-SIGINT exit
        # tearing down the lifespan task rather than sending a clean
        # lifespan.shutdown message) still runs shutdown. Without this, the
        # code after a bare `yield` is simply never reached and the SQLite
        # WAL checkpoint, aiohttp session close, and worker/thread-pool
        # teardown in _shutdown_components all get skipped. Safe to run
        # unconditionally here because #4569 already hardened every step
        # inside _shutdown_components against a single failing step aborting
        # the rest.
        try:
            yield
        finally:
            # === Shutdown ===
            await _shutdown_components(globals_dict)

    return lifespan
