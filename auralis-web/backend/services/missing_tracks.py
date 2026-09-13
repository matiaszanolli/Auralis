"""
Missing-Track Pruning

Removes library tracks whose files are gone from disk and tells clients, after
a library scan. Shared by the manual scan route and the auto-scanner (#5458):
only the auto-scanner used to prune, so a user with ``auto_scan`` off — or
anyone rescanning by hand after reorganising files — kept dead entries forever.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any

from websocket.outbound_messages import broadcast_typed

logger = logging.getLogger(__name__)


async def prune_missing_tracks(library_database: Any, connection_manager: Any | None) -> int:
    """Delete tracks whose files no longer exist and broadcast the removal.

    Best-effort, like the scan that precedes it: a failed prune is logged and
    reported as 0 removed rather than failing the scan. Callers must run this
    before ``scan_complete`` — ``useScanProgress`` only counts a
    ``library_tracks_removed`` frame that arrives during the scan.

    Returns:
        Number of tracks removed
    """
    try:
        removed = int(await asyncio.to_thread(library_database.tracks.cleanup_missing_files))
    except Exception as exc:
        logger.warning(f"cleanup_missing_files failed: {exc}")
        return 0

    if removed:
        logger.info(f"🗑️  Removed {removed} missing tracks from library")
        if connection_manager is not None:
            await broadcast_typed(
                connection_manager,
                "library_tracks_removed",
                {"count": removed},
                suppress_errors=True,
            )
    return removed
