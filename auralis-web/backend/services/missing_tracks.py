"""
Missing-Track Pruning

Removes library tracks whose files are gone from disk and tells clients, after
a library scan. Shared by the manual scan route and the auto-scanner (#5458):
only the auto-scanner used to prune, so a user with ``auto_scan`` off — or
anyone rescanning by hand after reorganising files — kept dead entries forever.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
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


async def prune_tracks_under_folder(
    library_database: Any, folder: str, connection_manager: Any | None
) -> int:
    """Delete tracks under a removed scan folder and broadcast the removal (#5467).

    Sibling of `prune_missing_tracks`, same best-effort/broadcast shape: a
    removed scan folder revokes path trust for its files
    (`unregister_allowed_directory`), and this keeps the library's Track
    rows in sync with that instead of leaving them visible-but-broken.

    Returns:
        Number of tracks removed
    """
    try:
        removed = int(
            await asyncio.to_thread(library_database.tracks.remove_tracks_under_folder, folder)
        )
    except Exception as exc:
        logger.warning(f"remove_tracks_under_folder failed for {folder}: {exc}")
        return 0

    if removed:
        logger.info(f"🗑️  Removed {removed} tracks under removed scan folder {folder}")
        if connection_manager is not None:
            await broadcast_typed(
                connection_manager,
                "library_tracks_removed",
                {"count": removed},
                suppress_errors=True,
            )
    return removed
