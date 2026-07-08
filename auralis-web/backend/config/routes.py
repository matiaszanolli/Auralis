"""
Router Configuration and Registration

Imports all router factories and registers them with the FastAPI application.
Handles dependency injection for each router via lambdas.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, FastAPI
from routers.albums import create_albums_router
from routers.artists import create_artists_router
from routers.artwork import create_artwork_router
from routers.cache_streamlined import create_streamlined_cache_router
from routers.enhancement import create_enhancement_router
from routers.files import create_files_router
from routers.library import create_library_router
from routers.tracks import create_tracks_router
from routers.library_scan import create_library_scan_router
from routers.fingerprint_status import create_fingerprint_status_router
from routers.metadata import create_metadata_router
from routers.player import create_player_router
from routers.playlists import create_playlists_router
from routers.settings import create_settings_router
from routers.similarity import create_similarity_router
from routers.wav_streaming import create_wav_streaming_router

# Import router factories
from routers.system import create_system_router
from routers.health import create_health_router

logger = logging.getLogger(__name__)


def setup_routers(app: FastAPI, deps: dict[str, Any]) -> None:
    """
    Register all routers with FastAPI application.

    Args:
        app: FastAPI application instance
        deps: Dictionary of dependencies:
            - HAS_AURALIS: bool
            - HAS_PROCESSING: bool
            - HAS_STREAMLINED_CACHE: bool
            - HAS_SIMILARITY: bool
            - manager: ConnectionManager
            - enhancement_settings: dict
            - chunked_audio_processor_class: class
            - create_track_info_fn: callable
            - buffer_presets_fn: callable
            - globals: Dict with component instances
    """

    HAS_PROCESSING: bool = deps.get('HAS_PROCESSING', False)
    HAS_STREAMLINED_CACHE: bool = deps.get('HAS_STREAMLINED_CACHE', False)
    HAS_SIMILARITY: bool = deps.get('HAS_SIMILARITY', False)
    manager: Any = deps.get('manager')
    enhancement_settings: dict[str, Any] = deps.get('enhancement_settings', {})
    chunked_audio_processor_class: Any = deps.get('chunked_audio_processor_class')
    create_track_info_fn: Any = deps.get('create_track_info_fn')
    buffer_presets_fn: Any = deps.get('buffer_presets_fn')
    globals_dict: dict[str, Any] = deps.get('globals', {})

    # Helper to safely get global components
    def get_component(key: str) -> Callable[[], Any]:
        return lambda: globals_dict.get(key)

    # Include processing API routes (if available)
    if HAS_PROCESSING:
        try:
            from routers.processing_api import create_processing_router
            processing_router = create_processing_router(
                get_component('processing_engine')
            )
            app.include_router(processing_router)
            logger.debug("✅ Processing API router included")
        except Exception as e:
            # Catch all exceptions (not just ImportError) so syntax errors or
            # missing transitive deps degrade gracefully rather than crashing
            # startup (fixes #2324).
            logger.warning(f"⚠️  Processing API router not available: {e}", exc_info=True)

    # Health and version routes (extracted from system router in #4074)
    health_router: APIRouter = create_health_router(
        HAS_AURALIS=deps.get('HAS_AURALIS', False),
    )
    app.include_router(health_router)
    logger.debug("✅ Health router registered")

    # WebSocket system router
    # Issue #2740: Pass get_state_manager so reconnecting WebSocket clients
    # receive a full player state snapshot immediately on connect.
    system_router: APIRouter = create_system_router(
        manager=manager,
        get_processing_engine=get_component('processing_engine'),
        HAS_AURALIS=deps.get('HAS_AURALIS', False),
        get_repository_factory=get_component('repository_factory'),
        get_enhancement_settings=lambda: enhancement_settings,
        get_state_manager=get_component('player_state_manager'),
        # Pass the process-wide StreamlinedCacheManager so AudioStreamController
        # reuses the shared chunk cache across requests (fixes #3855).
        get_cache_manager=get_component('streamlined_cache'),
    )
    app.include_router(system_router)
    logger.debug("✅ System router registered")

    # Create and include settings router (GET/PUT /api/settings, scan-folders management)
    settings_router: APIRouter = create_settings_router(
        get_settings_repo=get_component('settings_repository'),
        get_auto_scanner=get_component('auto_scanner'),
    )
    app.include_router(settings_router)
    logger.debug("✅ Settings router registered")

    # Create and include files router (scan, upload, formats)
    files_router: APIRouter = create_files_router(
        get_library_manager=get_component('library_manager'),
        connection_manager=manager,
        get_repository_factory=get_component('repository_factory')
    )
    app.include_router(files_router)
    logger.debug("✅ Files router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include enhancement router
    enhancement_router: APIRouter = create_enhancement_router(
        get_enhancement_settings=lambda: enhancement_settings,
        connection_manager=manager,
        get_multi_tier_buffer=lambda: globals_dict.get('streamlined_cache') if HAS_STREAMLINED_CACHE else None,
        get_player_state_manager=get_component('player_state_manager'),
        get_processing_engine=lambda: globals_dict.get('processing_engine') if HAS_PROCESSING else None,
        get_repository_factory=get_component('repository_factory'),
    )
    app.include_router(enhancement_router)
    logger.debug("✅ Enhancement router registered")

    # Create and include artwork router (with Phase 6B RepositoryFactory refactoring)
    artwork_router: APIRouter = create_artwork_router(
        connection_manager=manager,
        get_repository_factory=get_component('repository_factory')
    )
    app.include_router(artwork_router)
    logger.debug("✅ Artwork router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include playlists router (with Phase 2 RepositoryFactory support)
    playlists_router: APIRouter = create_playlists_router(
        get_repository_factory=get_component('repository_factory'),
        connection_manager=manager
    )
    app.include_router(playlists_router)
    logger.debug("✅ Playlists router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include library router (stats, browse, reset — Phase 6B)
    library_router: APIRouter = create_library_router(
        get_repository_factory=get_component('repository_factory'),
        # Reset pauses/restarts all background workers (#4111) and invalidates
        # the LibraryManager cache (#3770). resolve_worker looks workers up by
        # the shared BACKGROUND_WORKER_KEYS in the component registry.
        resolve_worker=lambda key: globals_dict.get(key),
        get_library_manager=get_component('library_manager'),
    )
    app.include_router(library_router)
    logger.debug("✅ Library router registered (stats/browse/reset)")

    # Track-domain routes (listing, favorites, lyrics)
    tracks_router: APIRouter = create_tracks_router(
        get_repository_factory=get_component('repository_factory'),
    )
    app.include_router(tracks_router)
    logger.debug("✅ Tracks router registered")

    # Scan route with async progress broadcast
    library_scan_router: APIRouter = create_library_scan_router(
        get_library_manager=get_component('library_manager'),
        connection_manager=manager,
    )
    app.include_router(library_scan_router)
    logger.debug("✅ Library scan router registered")

    # Fingerprint status routes
    fingerprint_status_router: APIRouter = create_fingerprint_status_router(
        get_repository_factory=get_component('repository_factory'),
    )
    app.include_router(fingerprint_status_router)
    logger.debug("✅ Fingerprint status router registered")

    # Create and include metadata router (with Phase 6B RepositoryFactory refactoring)
    metadata_router: APIRouter = create_metadata_router(
        get_repository_factory=get_component('repository_factory'),
        broadcast_manager=manager
    )
    app.include_router(metadata_router)
    logger.debug("✅ Metadata router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include albums router (with Phase 6B RepositoryFactory refactoring)
    albums_router: APIRouter = create_albums_router(
        get_repository_factory=get_component('repository_factory')
    )
    app.include_router(albums_router)
    logger.debug("✅ Albums router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include artists router (with Phase 6B RepositoryFactory refactoring)
    artists_router: APIRouter = create_artists_router(
        get_repository_factory=get_component('repository_factory')
    )
    app.include_router(artists_router)
    logger.debug("✅ Artists router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include player router
    player_router: APIRouter = create_player_router(
        get_library_manager=get_component('library_manager'),
        get_audio_player=get_component('audio_player'),
        get_player_state_manager=get_component('player_state_manager'),
        connection_manager=manager,
        chunked_audio_processor_class=chunked_audio_processor_class,
        create_track_info_fn=create_track_info_fn,
        buffer_presets_fn=buffer_presets_fn,
        get_multi_tier_buffer=lambda: globals_dict.get('streamlined_cache') if HAS_STREAMLINED_CACHE else None,
        get_enhancement_settings=lambda: enhancement_settings
    )
    app.include_router(player_router)
    logger.debug("✅ Player router registered")

    # Include cache management router (if available).
    # Register unconditionally when the module is importable; handlers
    # return 503 until the cache manager is initialised during lifespan
    # (fixes #2756 — router was never registered because globals_dict
    # was still empty at setup_routers() time).
    if HAS_STREAMLINED_CACHE:
        try:
            cache_router: APIRouter = create_streamlined_cache_router(
                get_cache_manager=lambda: globals_dict.get('streamlined_cache'),
                broadcast_manager=manager
            )
            app.include_router(cache_router)
            logger.info("✅ Streamlined cache router registered")
        except Exception as e:
            logger.warning(f"⚠️  Failed to register streamlined cache router: {e}", exc_info=True)

    # Create and include similarity router (if available)
    if HAS_SIMILARITY:
        try:
            similarity_router: APIRouter = create_similarity_router(
                get_similarity_system=get_component('similarity_system'),
                get_graph_builder=get_component('graph_builder'),
                get_repository_factory=get_component('repository_factory')
            )
            app.include_router(similarity_router)
            logger.info("✅ Similarity router registered")
        except Exception as e:
            logger.warning(f"⚠️  Failed to register similarity router: {e}", exc_info=True)

    # Create and include WAV streaming router
    try:
        streaming_router: APIRouter = create_wav_streaming_router(
            get_multi_tier_buffer=lambda: globals_dict.get('streamlined_cache') if HAS_STREAMLINED_CACHE else None,
            chunked_audio_processor_class=chunked_audio_processor_class,
            get_repository_factory=get_component('repository_factory'),
        )
        app.include_router(streaming_router)
        logger.info("✅ WAV streaming router registered")
    except Exception as e:
        # WAV streaming is the production audio delivery path; promote to
        # ERROR with exc_info so a silent failure here surfaces as a CI /
        # log-monitor signal rather than a soft warning amongst the
        # genuinely-optional cache/similarity router warnings (#3538 /
        # BE-NEW-80).
        logger.error(
            f"❌ Failed to register WAV streaming router (audio delivery WILL be broken): {e}",
            exc_info=True,
        )

    logger.info("✅ All routers configured and registered")
