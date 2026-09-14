"""
Startup Rollback and Component Teardown
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rolls back a partially-initialised startup, plus the per-component teardown
helpers that rollback shares with shutdown (``config.startup.shutdown``).

Split out of the former single-file config/startup.py (#5236).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

from config.background_workers import BACKGROUND_WORKER_KEYS, WORKER_STOP_KWARGS

logger = logging.getLogger(__name__)


# Background services that may already be running (spawned their own workers
# / tasks) by the time a later startup step fails. Rollback must await each
# one's .stop() before nulling it out, not just drop the reference — an
# already-running fingerprint queue or auto-scanner would otherwise keep
# calling into a library_database that's about to be rolled back to None
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
    'library_database', 'repository_factory', 'settings_repository',
    'audio_player', 'player_state_manager',
    'streamlined_cache', 'similarity_system', 'graph_builder',
)


async def _rollback_partial_startup(globals_dict: dict[str, Any]) -> None:
    """Roll back partially-initialised globals after a startup failure.

    So downstream routers see a coherent 'not ready' state instead of
    'library_database truthy but everything else None' (#3540 / BE-NEW-82).
    Router dependencies that gate on library_database truthy will then return
    503 rather than AttributeError -> 500.

    Extracted as a standalone function (#3812) so this behavior — especially
    awaiting .stop() on already-running background services before nulling
    them — is directly unit-testable without needing to mock the entire
    Auralis startup import chain.

    Three components get a real teardown call, not just a bare null-out
    (#4764): player_state_manager (stop the 1 Hz broadcast task, #4747),
    audio_player (release the hardware device, #3210), and library_database
    (WAL checkpoint + engine dispose, #3210). Without this, a startup
    failure after these were constructed left the SQLite engine, the audio
    device, and (if playback had started) a background task unreachable for
    the rest of the process lifetime — _shutdown_components' guard on
    globals_dict.get(...) never fires once rollback has already nulled the
    reference. The three teardown helpers are shared with
    _shutdown_components so the two paths cannot silently diverge again.
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

    await _teardown_player_state_manager(globals_dict)
    _teardown_audio_player(globals_dict)
    _teardown_library_database(globals_dict)

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


async def _teardown_player_state_manager(globals_dict: dict[str, Any]) -> None:
    """Stop the 1 Hz player-state broadcast task (#4747), best-effort.

    Shared by _shutdown_components and _rollback_partial_startup (#4764) —
    the orphaned-background-task risk #4747 fixed for shutdown applies
    equally to a startup failure after PlayerStateManager was constructed
    and playback had already started.
    """
    manager = globals_dict.get('player_state_manager')
    if not manager:
        return
    try:
        await manager.shutdown()
        logger.info("✅ Player state manager stopped")
    except Exception as psm_err:
        logger.warning(f"⚠️  Player state manager shutdown error: {psm_err}")


def _teardown_audio_player(globals_dict: dict[str, Any]) -> None:
    """Stop and release the audio player's hardware resources (#3210), best-effort.

    Shared by _shutdown_components and _rollback_partial_startup (#4764) so
    the two teardown paths cannot silently diverge on how — or whether — the
    audio player is released.
    """
    player = globals_dict.get('audio_player')
    if not player:
        return
    try:
        if hasattr(player, 'stop'):
            player.stop()
        if hasattr(player, 'cleanup'):
            player.cleanup()
        logger.info("✅ Audio Player stopped")
    except Exception as player_err:
        logger.warning(f"⚠️  Audio player shutdown error: {player_err}")


def _teardown_library_database(globals_dict: dict[str, Any]) -> None:
    """Shut down the library database — WAL checkpoint + engine dispose (#3210), best-effort.

    Shared by _shutdown_components and _rollback_partial_startup (#4764).
    """
    manager = globals_dict.get('library_database')
    if not manager:
        return
    try:
        manager.shutdown()
        logger.info("✅ Library database shut down (WAL checkpointed)")
    except Exception as lm_err:
        logger.warning(f"⚠️  Library database shutdown error: {lm_err}")


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
