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

A package since #5236; it was one 1,190-line module. This module keeps the
lifespan itself, thread-pool installation and the Auralis-component sequence
with its rollback boundary. The steps live in submodules:

- ``components``: library database, settings, scan folders, reference-cloud
  refresh, auto-scanner, audio player
- ``fingerprint``: fingerprint extraction and on-demand queues, similarity
- ``workers``: processing engine, streamlined cache, dead-worker watchdog
- ``tempfiles``: startup sweep of the chunk cache and leftover temp files
- ``rollback``: partial-startup rollback and the shared component teardown
- ``shutdown``: the full shutdown sequence

Every step this module calls is imported into its namespace, so patching
``config.startup.<step>`` still intercepts it. A helper called from inside a
submodule has to be patched where it is looked up, e.g.
``config.startup.tempfiles.reclaim_leftover_stream_temps``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from fastapi import FastAPI

from .components import (
    _init_audio_player,
    _init_library_database,
    _init_reference_cloud_refresh,
    _register_scan_folders,
    _seed_settings_and_enhancement,
    _start_auto_scanner,
)
from .fingerprint import (
    _init_fingerprint_extraction_queue,
    _init_ondemand_fingerprint_queue,
    _init_similarity_system,
)
from .rollback import _rollback_partial_startup
from .shutdown import _shutdown_components
from .tempfiles import _cleanup_temp_directories
from .workers import _init_processing_engine, _init_streamlined_cache

logger = logging.getLogger(__name__)


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
        await _init_similarity_system(HAS_SIMILARITY, globals_dict)
    except Exception as e:
        import traceback
        logger.error(f"❌ Failed to initialize Auralis components: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        logger.error("⚠️  Auralis library initialization failed - rolling back partial state; API will return 503")
        await _rollback_partial_startup(globals_dict)


def create_lifespan(
    deps: dict[str, Any],
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
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
