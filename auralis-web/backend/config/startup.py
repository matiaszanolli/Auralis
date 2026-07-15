"""
Application Lifespan Manager

Manages component initialization and cleanup via FastAPI lifespan context manager:
- LibraryManager setup
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
import shutil
import tempfile
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

logger = logging.getLogger(__name__)


# Background services that may already be running (spawned their own workers
# / tasks) by the time a later startup step fails. Rollback must await each
# one's .stop() before nulling it out, not just drop the reference — an
# already-running fingerprint queue or auto-scanner would otherwise keep
# calling into a library_manager that's about to be rolled back to None
# (#3812 / BE-MW-3, regression of #3540 / BE-NEW-82).
_ROLLBACK_SERVICES_TO_STOP: tuple[tuple[str, dict[str, Any]], ...] = (
    ('auto_scanner', {}),
    ('ondemand_fingerprint_queue', {}),
    ('fingerprint_queue', {'timeout': 30.0}),
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


def reclaim_leftover_stream_temps(temp_root: Path) -> int:
    """Remove temp WAV dirs orphaned by interrupted compressed-format streams.

    stream_normal_audio writes a temp WAV under ``auralis_stream_*`` and cleans
    it in its finally block, but a crash or a locked file (Windows AV /
    cloud-sync) can leave one behind (#3877). Sweep them on startup so any leak
    surfaces in the log and stays bounded.

    Returns the number of leftover directories successfully reclaimed.
    """
    reclaimed = 0
    for leftover in temp_root.glob("auralis_stream_*"):
        try:
            shutil.rmtree(leftover)
            reclaimed += 1
        except Exception as e:
            logger.warning(f"Failed to remove leftover temp stream dir {leftover}: {e}")
    if reclaimed:
        logger.info(f"🧹 Reclaimed {reclaimed} leftover temp stream dir(s)")
    return reclaimed


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

        # Clear chunk files from disk to avoid serving stale chunks with old presets
        chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"
        if chunk_dir.exists():
            try:
                shutil.rmtree(chunk_dir)
                chunk_dir.mkdir(exist_ok=True)
                logger.info(f"🧹 Cleared chunk directory: {chunk_dir}")
            except Exception as e:
                logger.warning(f"Failed to clear chunk directory: {e}")

        # Sweep temp WAVs orphaned by interrupted compressed-format streams (#3877).
        reclaim_leftover_stream_temps(Path(tempfile.gettempdir()))

        if HAS_AURALIS:
            try:
                # Import Auralis components here to support optional dependency
                from core.state_manager import PlayerStateManager

                from auralis.library import LibraryManager
                from auralis.library.repositories.settings_repository import (
                    SettingsRepository,
                )
                from auralis.library.scanner import LibraryScanner
                from auralis.player.config import PlayerConfig
                from auralis.player import AudioPlayer

                # Ensure database directory exists before initializing LibraryManager
                music_dir = Path.home() / "Music" / "Auralis"
                music_dir.mkdir(parents=True, exist_ok=True)
                # Absolute home/database paths are sensitive and persist to the
                # on-disk electron-log, so they log at DEBUG — consistent with the
                # #3844 demotion of the sibling path-validation logs (#4376).
                logger.debug(f"📁 Database directory ready: {music_dir}")

                # Initialize LibraryManager
                globals_dict['library_manager'] = LibraryManager()
                logger.info("✅ Auralis LibraryManager initialized")
                logger.debug(f"📊 Database location: {globals_dict['library_manager'].database_path}")

                # Initialize RepositoryFactory for dependency injection
                # This enables gradual migration from LibraryManager to repositories
                from auralis.library.repositories import RepositoryFactory
                globals_dict['repository_factory'] = RepositoryFactory(
                    globals_dict['library_manager'].SessionLocal,
                )
                logger.info("✅ Repository Factory initialized (Phase 2 support)")

                # Initialize CPU-based fingerprinting system (36x speedup via parallel workers)
                # Note: GPU batch processing was causing memory exhaustion crashes.
                # CPU parallelization provides better stability and consistent performance.
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
                    fingerprint_queue = None

                # Initialize settings repository
                globals_dict['settings_repository'] = SettingsRepository(
                    globals_dict['library_manager'].SessionLocal
                )
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

                # Register user-configured scan folders as allowed directories
                # so validate_file_path accepts files from custom locations.
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

                # #3479: shared refresh closure for the reference cloud,
                # invoked by scanner end-of-run and fingerprint-queue drain
                # hooks (and the REST refresh endpoint). The seeder is
                # idempotent and reads existing fingerprint rows — no audio
                # I/O — so calling it from multiple producers is safe.
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
                # closure available (queue itself was started above).
                _fpq = globals_dict.get('fingerprint_queue')
                if _fpq is not None:
                    _fpq.set_drained_callback(_refresh_reference_cloud)

                # Start the library auto-scanner service.
                # Replaces the old one-shot ~/Music scan with a proper service that:
                # - reads scan_folders from user settings (not hardcoded)
                # - uses watchdog for real-time detection + periodic polling fallback
                # - removes stale tracks (cleanup_missing_files) after each cycle
                # - handles crashes gracefully with 30s back-off
                try:
                    from services.library_auto_scanner import LibraryAutoScanner
                    auto_scanner = LibraryAutoScanner(
                        settings_repo=globals_dict['settings_repository'],
                        library_manager=globals_dict['library_manager'],
                        fingerprint_queue=globals_dict.get('fingerprint_queue'),
                        connection_manager=manager,
                        on_scan_complete=_refresh_reference_cloud,
                    )
                    await auto_scanner.start()
                    globals_dict['auto_scanner'] = auto_scanner
                except Exception as as_e:
                    logger.warning(f"⚠️  Failed to start LibraryAutoScanner: {as_e}")

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
                    library_manager=globals_dict['library_manager'],
                    get_repository_factory=lambda: globals_dict.get('repository_factory')
                )
                logger.info("✅ Enhanced Audio Player initialized (Phase 4 RepositoryFactory support enabled)")

                # Initialize state manager (must be after library_manager is created)
                globals_dict['player_state_manager'] = PlayerStateManager(manager)
                logger.info("✅ Player State Manager initialized")

                # Initialize on-demand fingerprint queue (Phase 7.4)
                # This handles 404s during similarity lookup - queues tracks for background processing
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
                            pass
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

                # Initialize similarity system
                if HAS_SIMILARITY:
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

            except Exception as e:
                import traceback
                logger.error(f"❌ Failed to initialize Auralis components: {e}")
                logger.error(f"Traceback:\n{traceback.format_exc()}")
                logger.error("⚠️  Auralis library initialization failed - rolling back partial state; API will return 503")
                await _rollback_partial_startup(globals_dict)
        else:
            logger.warning("⚠️  Auralis not available - running in demo mode")

        # Initialize processing engine
        if HAS_PROCESSING:
            try:
                from core.processing_engine import ProcessingEngine

                globals_dict['processing_engine'] = ProcessingEngine(max_concurrent_jobs=2)
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
        else:
            logger.warning("⚠️  Processing engine not available")

        # Initialize streamlined cache system (Beta.9)
        if HAS_STREAMLINED_CACHE and globals_dict.get('library_manager'):
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
                worker_task = globals_dict['streamlined_worker']._worker_task
                if worker_task is not None:
                    _watch_critical_worker_task(
                        worker_task,
                        globals_dict,
                        ('streamlined_cache', 'streamlined_worker'),
                        "StreamlinedCacheWorker",
                    )

            except Exception as e:
                logger.error(f"❌ Failed to initialize streamlined cache: {e}")
        else:
            if not HAS_STREAMLINED_CACHE:
                logger.warning("⚠️  Streamlined cache not available")
            elif not globals_dict.get('library_manager'):
                logger.warning("⚠️  Library manager not available - streamlined cache disabled")

        yield

        # === Shutdown ===
        try:
            # Stop the background workers (auto_scanner, ondemand + batch
            # fingerprint queues) using the shared BACKGROUND_WORKER_KEYS set so
            # this path and the library-reset endpoint can never diverge on which
            # workers exist (#4111). Order matches the tuple: auto_scanner first
            # (it may be mid-scan and enqueue into the queues).
            from config.background_workers import BACKGROUND_WORKER_KEYS
            _worker_stop_kwargs = {'fingerprint_queue': {'timeout': 30.0}}
            for _worker_key in BACKGROUND_WORKER_KEYS:
                worker = globals_dict.get(_worker_key)
                if worker:
                    await worker.stop(**_worker_stop_kwargs.get(_worker_key, {}))
                    logger.info(f"✅ Background worker stopped: {_worker_key}")

            # Stop streamlined cache worker
            if 'streamlined_worker' in globals_dict and globals_dict['streamlined_worker']:
                await globals_dict['streamlined_worker'].stop()
                logger.info("✅ Streamlined Cache Worker stopped")

            # Stop processing engine
            if 'processing_engine' in globals_dict and globals_dict['processing_engine']:
                await globals_dict['processing_engine'].stop_worker()
                logger.info("✅ Processing Engine stopped")

            # Stop audio player and release hardware resources (#3210)
            if 'audio_player' in globals_dict and globals_dict['audio_player']:
                try:
                    player = globals_dict['audio_player']
                    if hasattr(player, 'stop'):
                        player.stop()
                    if hasattr(player, 'cleanup'):
                        player.cleanup()
                    logger.info("✅ Audio Player stopped")
                except Exception as player_err:
                    logger.warning(f"⚠️  Audio player shutdown error: {player_err}")

            # Release cached HybridProcessor thread pools (fixes #3746 — each
            # cached processor's fingerprint_analyzer owns a 5-thread executor
            # that outlives the processor unless explicitly closed).
            try:
                from core.processor_factory import get_processor_factory
                get_processor_factory().clear_cache()
                logger.info("✅ Processor factory cache cleared")
            except Exception as factory_err:
                logger.warning(f"⚠️  Processor factory shutdown error: {factory_err}")

            # Close the artwork downloader's shared aiohttp session, if one
            # was ever created (fixes #3915).
            try:
                from services.artwork_downloader import close_artwork_downloader
                await close_artwork_downloader()
                logger.info("✅ Artwork downloader session closed")
            except Exception as artwork_err:
                logger.warning(f"⚠️  Artwork downloader shutdown error: {artwork_err}")

            # Shut down LibraryManager last — WAL checkpoint + engine dispose (#3210)
            if 'library_manager' in globals_dict and globals_dict['library_manager']:
                try:
                    globals_dict['library_manager'].shutdown()
                    logger.info("✅ Library Manager shut down (WAL checkpointed)")
                except Exception as lm_err:
                    logger.warning(f"⚠️  Library manager shutdown error: {lm_err}")

            logger.info("✅ Application shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    return lifespan
