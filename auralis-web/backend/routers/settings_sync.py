"""
Settings router side effects after a save (split from settings.py, #5832):
auto-scanner reload and the enhancement runtime re-seed + broadcast.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

from helpers import seed_enhancement_settings

from websocket.outbound_messages import broadcast_typed

from .settings_deps import _SettingsDeps

logger = logging.getLogger(__name__)


async def _notify_scanner(deps: _SettingsDeps) -> None:
    """Tell the auto-scanner to reload its config immediately."""
    if deps.get_auto_scanner is None:
        return
    scanner = deps.get_auto_scanner()
    if scanner and hasattr(scanner, 'reload_config'):
        try:
            await scanner.reload_config()
        except Exception as exc:
            logger.warning(f"Failed to notify auto-scanner of settings change: {exc}")


async def _sync_enhancement_settings(deps: _SettingsDeps, settings: Any) -> None:
    """Re-seed the live runtime dict from just-persisted settings and
    broadcast (#4587) — the DB-to-runtime half of keeping the Settings
    dialog and the Enhancement Panel in sync. Mirrors
    config/startup.py's one-time seed at process start, using the exact
    same `seed_enhancement_settings` helper so the two can never drift
    onto different mapping/validation logic.

    `enhancement_settings` is mutated in place (seed_enhancement_settings's
    own contract) — every router holding a reference to it (system,
    enhancement) observes the new values without re-fetching anything.
    """
    if deps.get_enhancement_settings is None:
        return
    live_settings = deps.get_enhancement_settings()
    seed_enhancement_settings(live_settings, settings)
    if deps.connection_manager is None:
        return
    try:
        await broadcast_typed(
            deps.connection_manager,
            "enhancement_settings_changed",
            {
                "enabled": live_settings["enabled"],
                "preset": live_settings["preset"],
                "intensity": live_settings["intensity"],
            },
        )
    except Exception as exc:
        logger.warning(f"Failed to broadcast enhancement_settings_changed: {exc}")
