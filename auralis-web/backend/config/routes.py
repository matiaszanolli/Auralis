"""
Router Configuration and Registration

Imports all router factories and registers them with the FastAPI application.
Handles dependency injection for each router via lambdas.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from fastapi import FastAPI, APIRouter
from typing import Dict, Any, Callable, Optional

# Import router factories
from routers.system import create_system_router
from routers.files import create_files_router
from routers.enhancement import create_enhancement_router
from routers.artwork import create_artwork_router
from routers.playlists import create_playlists_router
from routers.library import create_library_router
from routers.metadata import create_metadata_router
from routers.albums import create_albums_router
from routers.artists import create_artists_router
from routers.player import create_player_router
from routers.similarity import create_similarity_router
from routers.cache_streamlined import create_streamlined_cache_router

logger = logging.getLogger(__name__)


def setup_routers(app: FastAPI, deps: Dict[str, Any]) -> None:
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
            - processing_cache: dict
            - chunked_audio_processor_class: class
            - create_track_info_fn: callable
            - buffer_presets_fn: callable
            - globals: Dict with component instances
    """

    HAS_PROCESSING: bool = deps.get('HAS_PROCESSING', False)
    HAS_STREAMLINED_CACHE: bool = deps.get('HAS_STREAMLINED_CACHE', False)
    HAS_SIMILARITY: bool = deps.get('HAS_SIMILARITY', False)
    manager: Any = deps.get('manager')
    enhancement_settings: Dict[str, Any] = deps.get('enhancement_settings', {})
    processing_cache: Dict[str, Any] = deps.get('processing_cache', {})
    chunked_audio_processor_class: Any = deps.get('chunked_audio_processor_class')
    create_track_info_fn: Any = deps.get('create_track_info_fn')
    buffer_presets_fn: Any = deps.get('buffer_presets_fn')
    globals_dict: Dict[str, Any] = deps.get('globals', {})

    # Helper to safely get global components
    def get_component(key: str) -> Callable[[], Any]:
        return lambda: globals_dict.get(key)

    # Include processing API routes (if available)
    if HAS_PROCESSING:
        try:
            from processing_api import router as processing_router
            app.include_router(processing_router)
            logger.debug("✅ Processing API router included")
        except ImportError:
            logger.warning("⚠️  Processing API router not available")

    # Create and include system router (health, version, WebSocket)
    system_router: APIRouter = create_system_router(
        manager=manager,
        get_library_manager=get_component('library_manager'),
        get_processing_engine=get_component('processing_engine'),
        HAS_AURALIS=deps.get('HAS_AURALIS', False)
    )
    app.include_router(system_router)
    logger.debug("✅ System router registered")

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
        get_processing_cache=lambda: processing_cache,
        get_multi_tier_buffer=lambda: globals_dict.get('streamlined_cache') if HAS_STREAMLINED_CACHE else None,
        get_player_state_manager=get_component('player_state_manager'),
        get_processing_engine=lambda: globals_dict.get('processing_engine') if HAS_PROCESSING else None
    )
    app.include_router(enhancement_router)
    logger.debug("✅ Enhancement router registered")

    # Create and include artwork router (with Phase 2 RepositoryFactory support)
    artwork_router: APIRouter = create_artwork_router(
        get_library_manager=get_component('library_manager'),
        connection_manager=manager,
        get_repository_factory=get_component('repository_factory')
    )
    app.include_router(artwork_router)
    logger.debug("✅ Artwork router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include playlists router (with Phase 2 RepositoryFactory support)
    playlists_router: APIRouter = create_playlists_router(
        get_library_manager=get_component('library_manager'),
        connection_manager=manager,
        get_repository_factory=get_component('repository_factory')
    )
    app.include_router(playlists_router)
    logger.debug("✅ Playlists router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include library router (with Phase 2 RepositoryFactory support)
    library_router: APIRouter = create_library_router(
        get_library_manager=get_component('library_manager'),
        connection_manager=manager,
        get_repository_factory=get_component('repository_factory')
    )
    app.include_router(library_router)
    logger.debug("✅ Library router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include metadata router (with Phase 2 RepositoryFactory support)
    metadata_router: APIRouter = create_metadata_router(
        get_library_manager=get_component('library_manager'),
        broadcast_manager=manager,
        get_repository_factory=get_component('repository_factory')
    )
    app.include_router(metadata_router)
    logger.debug("✅ Metadata router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include albums router (with Phase 2 RepositoryFactory support)
    albums_router: APIRouter = create_albums_router(
        get_library_manager=get_component('library_manager'),
        get_repository_factory=get_component('repository_factory')
    )
    app.include_router(albums_router)
    logger.debug("✅ Albums router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include artists router (with Phase 2 RepositoryFactory support)
    artists_router: APIRouter = create_artists_router(
        get_library_manager=get_component('library_manager'),
        get_repository_factory=get_component('repository_factory')
    )
    app.include_router(artists_router)
    logger.debug("✅ Artists router registered (Phase 2 RepositoryFactory enabled)")

    # Create and include player router
    player_router: APIRouter = create_player_router(
        get_library_manager=get_component('library_manager'),
        get_audio_player=get_component('audio_player'),
        get_player_state_manager=get_component('player_state_manager'),
        get_processing_cache=lambda: processing_cache,
        connection_manager=manager,
        chunked_audio_processor_class=chunked_audio_processor_class,
        create_track_info_fn=create_track_info_fn,
        buffer_presets_fn=buffer_presets_fn,
        get_multi_tier_buffer=lambda: globals_dict.get('streamlined_cache') if HAS_STREAMLINED_CACHE else None,
        get_enhancement_settings=lambda: enhancement_settings
    )
    app.include_router(player_router)
    logger.debug("✅ Player router registered")

    # Include cache management router (if available)
    if HAS_STREAMLINED_CACHE and globals_dict.get('streamlined_cache'):
        try:
            cache_router: APIRouter = create_streamlined_cache_router(
                cache_manager=globals_dict['streamlined_cache'],
                broadcast_manager=manager
            )
            app.include_router(cache_router)
            logger.info("✅ Streamlined cache router registered")
        except Exception as e:
            logger.warning(f"⚠️  Failed to register streamlined cache router: {e}")

    # Create and include similarity router (if available)
    if HAS_SIMILARITY:
        try:
            similarity_router: APIRouter = create_similarity_router(
                get_library_manager=get_component('library_manager'),
                get_similarity_system=get_component('similarity_system'),
                get_graph_builder=get_component('graph_builder'),
                connection_manager=manager
            )
            app.include_router(similarity_router)
            logger.info("✅ Similarity router registered")
        except Exception as e:
            logger.warning(f"⚠️  Failed to register similarity router: {e}")

    logger.info("✅ All routers configured and registered")
