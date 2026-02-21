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
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def _background_auto_scan(
    music_source_dir: Path,
    library_manager: Any,
    fingerprint_queue: Any | None,
    connection_manager: Any
) -> None:
    """
    Run library scan in background without blocking server startup.

    Broadcasts progress updates via WebSocket to all connected clients.

    Args:
        music_source_dir: Directory to scan
        library_manager: LibraryManager instance
        fingerprint_queue: Optional fingerprint extraction queue
        connection_manager: WebSocket ConnectionManager for progress updates
    """
    try:
        from auralis.library.scanner import LibraryScanner

        logger.info(f"🔍 Starting background auto-scan of {music_source_dir}...")

        # Broadcast scan start notification
        await connection_manager.broadcast({
            "type": "library_scan_started",
            "directory": str(music_source_dir)
        })

        # Create scanner with progress callback
        scanner = LibraryScanner(
            library_manager,
            fingerprint_queue=fingerprint_queue
        )

        # Set up progress callback to broadcast updates
        async def progress_callback(progress_data: dict[str, Any]) -> None:
            """Broadcast scan progress to all connected clients"""
            total = progress_data.get('total_found', 0) or progress_data.get('processed', 0)
            processed = progress_data.get('processed', 0)
            progress_frac = progress_data.get('progress', 0)
            percentage = round(progress_frac * 100) if progress_frac else (
                round(processed / total * 100) if total > 0 else 0
            )
            await connection_manager.broadcast({
                "type": "scan_progress",
                "data": {
                    "current": processed,
                    "total": total,
                    "percentage": percentage,
                    # Prefer filename keys; fall back to directory only as last resort.
                    # Mirrors the fix applied to routers/library.py (fixes #2484 / #2384).
                    "current_file": progress_data.get('current_file') or progress_data.get('file') or progress_data.get('directory'),
                }
            })

        # Capture the event loop before entering the thread pool.
        # asyncio.create_task() cannot be called from a background thread
        # (raises RuntimeError: no running event loop).  Use call_soon_threadsafe()
        # to schedule the coroutine creation back on the event loop (fixes #2189).
        loop = asyncio.get_running_loop()

        def sync_progress_callback(progress_data: dict[str, Any]) -> None:
            """Synchronous wrapper that schedules async broadcast from worker thread."""
            loop.call_soon_threadsafe(
                loop.create_task, progress_callback(progress_data)
            )

        scanner.set_progress_callback(sync_progress_callback)

        # Run scan in thread pool to avoid blocking event loop
        scan_result = await asyncio.to_thread(
            scanner.scan_directories,
            [str(music_source_dir)],
            recursive=True,
            skip_existing=True
        )

        # Log and broadcast results
        if scan_result and scan_result.files_added > 0:
            logger.info(f"✅ Background auto-scan complete: {scan_result.files_added} files added")
        elif scan_result:
            logger.info(f"✅ ~/Music already scanned: {scan_result.files_found} total files")
        else:
            logger.info("ℹ️  No new files to scan in ~/Music")

        await connection_manager.broadcast({
            "type": "scan_complete",
            "data": {
                "files_processed": scan_result.files_processed if scan_result else 0,
                "tracks_added": scan_result.files_added if scan_result else 0,
                "duration": scan_result.scan_time if scan_result else 0,
            }
        })

    except Exception as scan_e:
        logger.warning(f"⚠️  Background auto-scan failed: {scan_e}", exc_info=True)
        await connection_manager.broadcast({
            "type": "library_scan_error",
            "error": str(scan_e)
        })


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

        # Clear processing cache on startup to avoid serving stale processed audio
        if 'processing_cache' in globals_dict:
            globals_dict['processing_cache'].clear()
        logger.info("🧹 Processing cache cleared on startup")

        # Clear chunk files from disk to avoid serving stale chunks with old presets
        chunk_dir = Path(tempfile.gettempdir()) / "auralis_chunks"
        if chunk_dir.exists():
            try:
                shutil.rmtree(chunk_dir)
                chunk_dir.mkdir(exist_ok=True)
                logger.info(f"🧹 Cleared chunk directory: {chunk_dir}")
            except Exception as e:
                logger.warning(f"Failed to clear chunk directory: {e}")

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
                from auralis.player.enhanced_audio_player import EnhancedAudioPlayer

                # Ensure database directory exists before initializing LibraryManager
                music_dir = Path.home() / "Music" / "Auralis"
                music_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"📁 Database directory ready: {music_dir}")

                # Initialize LibraryManager
                globals_dict['library_manager'] = LibraryManager()
                logger.info("✅ Auralis LibraryManager initialized")
                logger.info(f"📊 Database location: {globals_dict['library_manager'].database_path}")

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

                # Schedule auto-scan as background task (non-blocking)
                music_source_dir = Path.home() / "Music"
                if music_source_dir.exists() and music_source_dir != music_dir:
                    logger.info(f"🔍 Scheduling background auto-scan of {music_source_dir}...")
                    asyncio.create_task(_background_auto_scan(
                        music_source_dir=music_source_dir,
                        library_manager=globals_dict['library_manager'],
                        fingerprint_queue=globals_dict.get('fingerprint_queue'),
                        connection_manager=manager
                    ))
                else:
                    logger.info("ℹ️  No music directory to auto-scan")

                # Initialize settings repository
                globals_dict['settings_repository'] = SettingsRepository(
                    globals_dict['library_manager'].SessionLocal
                )
                logger.info("✅ Settings Repository initialized")

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
                globals_dict['audio_player'] = EnhancedAudioPlayer(
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

                        # Only create graph_builder if system is already fitted
                        # (will be created on-demand via /api/similarity/fit endpoint)
                        if globals_dict['similarity_system'].is_fitted():
                            globals_dict['graph_builder'] = KNNGraphBuilder(
                                similarity_system=globals_dict['similarity_system'],
                                session_factory=globals_dict['library_manager'].SessionLocal
                            )
                            logger.info("✅ K-NN Graph Builder initialized (system is fitted)")
                        else:
                            globals_dict['graph_builder'] = None
                            logger.info("ℹ️  K-NN Graph Builder not initialized (system not fitted yet)")
                    except Exception as sim_e:
                        logger.warning(f"⚠️  Failed to initialize Similarity System: {sim_e}")
                        globals_dict['similarity_system'] = None
                        globals_dict['graph_builder'] = None

            except Exception as e:
                import traceback
                logger.error(f"❌ Failed to initialize Auralis components: {e}")
                logger.error(f"Traceback:\n{traceback.format_exc()}")
                logger.error("⚠️  Auralis library initialization failed - API will return 503 errors")
        else:
            logger.warning("⚠️  Auralis not available - running in demo mode")

        # Initialize processing engine
        if HAS_PROCESSING:
            try:
                from routers.processing_api import set_processing_engine
                from core.processing_engine import ProcessingEngine

                globals_dict['processing_engine'] = ProcessingEngine(max_concurrent_jobs=2)
                set_processing_engine(globals_dict['processing_engine'])
                # Start the processing worker
                asyncio.create_task(globals_dict['processing_engine'].start_worker())
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
                logger.info("✅ Streamlined Cache Manager initialized (12 MB Tier 1)")

                # Create and start worker
                globals_dict['streamlined_worker'] = StreamlinedCacheWorker(
                    cache_manager=globals_dict['streamlined_cache'],
                    library_manager=globals_dict['library_manager']
                )

                # Start the worker
                await globals_dict['streamlined_worker'].start()
                logger.info("✅ Streamlined Cache Worker started")

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
            # Stop on-demand fingerprint queue (Phase 7.4)
            if 'ondemand_fingerprint_queue' in globals_dict and globals_dict['ondemand_fingerprint_queue']:
                await globals_dict['ondemand_fingerprint_queue'].stop()
                logger.info("✅ On-demand fingerprint queue stopped")

            # Stop fingerprint extraction queue
            if 'fingerprint_queue' in globals_dict and globals_dict['fingerprint_queue']:
                await globals_dict['fingerprint_queue'].stop(timeout=30.0)
                logger.info("✅ Fingerprint extraction queue stopped")

            # Stop streamlined cache worker
            if 'streamlined_worker' in globals_dict and globals_dict['streamlined_worker']:
                await globals_dict['streamlined_worker'].stop()
                logger.info("✅ Streamlined Cache Worker stopped")

            # Stop processing engine
            if 'processing_engine' in globals_dict and globals_dict['processing_engine']:
                if hasattr(globals_dict['processing_engine'], 'stop_worker'):
                    await globals_dict['processing_engine'].stop_worker()
                logger.info("✅ Processing Engine stopped")

            logger.info("✅ Application shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    return lifespan
