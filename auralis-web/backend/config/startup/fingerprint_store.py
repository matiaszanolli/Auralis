"""Startup sweep of the central ``.25d`` fingerprint store (#6004).

Re-tags, touches, moves and deleted tracks strand entries whose key can never be produced again,
and nothing removed them: one real library held 3213 files of which only 383 were reachable. The
sweep runs off the event loop and only deletes entries nothing can load
(``FingerprintStorage.sweep_orphans``); live analysis is untouched.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging

from auralis.analysis.fingerprint.fingerprint_storage import FingerprintStorage

logger = logging.getLogger(__name__)


async def sweep_fingerprint_store() -> int:
    """Remove dead ``.25d`` entries; a failure is logged, never fatal to startup."""
    try:
        return await asyncio.to_thread(FingerprintStorage.sweep_orphans)
    except Exception as e:  # noqa: BLE001 - housekeeping must not block the app starting
        logger.warning(f"Fingerprint store sweep failed: {type(e).__name__}")
        return 0
