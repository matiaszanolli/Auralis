"""
Application Startup and Shutdown Event Handlers

Manages component initialization on application startup:
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
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_startup_handlers(app: FastAPI, deps: Dict[str, Any]) -> None:
    """
    Register startup and shutdown event handlers with FastAPI app.

    Args:
        app: FastAPI application instance
        deps: Dictionary of dependencies (globals dict to populate):
            - HAS_AURALIS: bool
            - HAS_PROCESSING: bool
            - HAS_STREAMLINED_CACHE: bool
            - HAS_SIMILARITY: bool
            - manager: ConnectionManager
            - globals: Dict to populate with component instances
    """

    # Extract dependencies
    HAS_AURALIS: bool = deps.get('HAS_AURALIS', False)
    HAS_PROCESSING: bool = deps.get('HAS_PROCESSING', False)
    HAS_STREAMLINED_CACHE: bool = deps.get('HAS_STREAMLINED_CACHE', False)
    HAS_SIMILARITY: bool = deps.get('HAS_SIMILARITY', False)
    manager: Any = deps.get('manager')
    globals_dict: Dict[str, Any] = deps.get('globals', {})

    @app.on_event("startup")
    async def startup_event() -> None:
        """Initialize Auralis components on startup"""

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
                from auralis.library import LibraryManager
                from auralis.library.scanner import LibraryScanner
                from auralis.library.repositories.settings_repository import SettingsRepository
                from auralis.player.enhanced_audio_player import EnhancedAudioPlayer
                from auralis.player.config import PlayerConfig
                from state_manager import PlayerStateManager

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
                    globals_dict['library_manager'].SessionLocal
                )
                logger.info("✅ Repository Factory initialized (Phase 2 support)")

                # Initialize CPU-based fingerprinting system (36x speedup via parallel workers)
                # Note: GPU batch processing was causing memory exhaustion crashes.
                # CPU parallelization provides better stability and consistent performance.
                try:
                    from auralis.library.fingerprint_extractor import FingerprintExtractor
                    from auralis.library.fingerprint_queue import FingerprintExtractionQueue

                    # Create fingerprint extractor with library manager's fingerprint repository
                    fingerprint_extractor = FingerprintExtractor(
                        fingerprint_repository=globals_dict['library_manager'].fingerprints
                    )
                    logger.info("✅ Fingerprint Extractor initialized")

                    # Create CPU-based fingerprint queue (24+ workers, 36x speedup)
                    fingerprint_queue = FingerprintExtractionQueue(
                        fingerprint_extractor=fingerprint_extractor,
                        get_repository_factory=lambda: globals_dict.get('repository_factory'),
                        num_workers=None,  # Auto-detect CPU cores
                        max_queue_size=None  # Auto-size based on system
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

                # Auto-scan default music directory on startup
                try:
                    music_source_dir = Path.home() / "Music"
                    if music_source_dir.exists() and music_source_dir != music_dir:
                        logger.info(f"🔍 Starting auto-scan of {music_source_dir}...")
                        scanner = LibraryScanner(
                            globals_dict['library_manager'],
                            fingerprint_queue=globals_dict.get('fingerprint_queue')
                        )
                        scan_result = scanner.scan_directories(
                            [str(music_source_dir)],
                            recursive=True,
                            skip_existing=True
                        )
                        if scan_result and scan_result.files_added > 0:
                            logger.info(f"✅ Auto-scanned ~/Music: {scan_result.files_added} files added")
                        elif scan_result:
                            logger.info(f"✅ ~/Music already scanned: {scan_result.files_found} total files")
                        else:
                            logger.info("ℹ️  No new files to scan in ~/Music")
                except Exception as scan_e:
                    logger.warning(f"⚠️  Failed to auto-scan ~/Music: {scan_e}")

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

                # Initialize similarity system
                if HAS_SIMILARITY:
                    try:
                        from auralis.analysis.fingerprint import FingerprintSimilarity, KNNGraphBuilder

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
                from processing_engine import ProcessingEngine
                from processing_api import set_processing_engine

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
                from streamlined_worker import StreamlinedCacheWorker

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

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        """Clean up resources on shutdown"""
        try:
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
