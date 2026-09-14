"""
Core Auralis Component Initialization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Library database, settings, scan folders, the reference-cloud refresh hook,
the library auto-scanner and the audio player — the core steps
``_init_auralis_components`` runs under one rollback boundary.

Split out of the former single-file config/startup.py (#5236).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
    # session factory, scan slots and shutdown; once it did, the facade
    # had no callers left and #4915 deleted it. The globals key went on
    # naming it for a month after that, until #5162.
    globals_dict['library_database'] = LibraryDatabase()
    logger.info("✅ Auralis library database initialized")
    logger.debug(f"📊 Database location: {globals_dict['library_database'].database_path}")

    # Repository factory for dependency injection. It is owned by
    # LibraryDatabase so every consumer — routers via this key and
    # components handed the database object — shares one instance
    # instead of building a second factory over the same sessions.
    globals_dict['repository_factory'] = globals_dict['library_database'].repositories
    logger.info("✅ Repository Factory initialized (Phase 2 support)")


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
            library_database=globals_dict['library_database'],
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

    # Initialize state manager (must be after library_database is created)
    globals_dict['player_state_manager'] = PlayerStateManager(manager)
    logger.info("✅ Player State Manager initialized")
