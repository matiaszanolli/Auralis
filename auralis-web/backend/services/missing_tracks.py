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
import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from auralis.library.scan_paths import reservation_key
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
        logger.error(f"cleanup_missing_files failed: {exc}")
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
    library_database: Any,
    folder: str,
    connection_manager: Any | None,
    keep_folders: Sequence[str] = (),
) -> int:
    """Delete tracks under a removed scan folder and broadcast the removal (#5467).

    Sibling of `prune_missing_tracks`, same best-effort/broadcast shape: a
    removed scan folder revokes path trust for its files
    (`unregister_allowed_directory`), and this keeps the library's Track
    rows in sync with that instead of leaving them visible-but-broken. Tracks
    under a scan folder that is still configured (``keep_folders``) are kept,
    so removing a parent does not delete a nested folder's library (#5941).

    Returns:
        Number of tracks removed
    """
    try:
        removed = int(
            await asyncio.to_thread(
                library_database.tracks.remove_tracks_under_folder, folder, keep_folders=keep_folders
            )
        )
    except Exception as exc:
        logger.error(f"remove_tracks_under_folder failed for {Path(folder).name}: {exc}")
        logger.debug(f"remove_tracks_under_folder failed for full path {folder}")
        return 0

    if removed:
        logger.info(f"🗑️  Removed {removed} tracks under removed scan folder {Path(folder).name}")
        logger.debug(f"Removed scan folder path: {folder}")
        if connection_manager is not None:
            await broadcast_typed(
                connection_manager,
                "library_tracks_removed",
                {"count": removed},
                suppress_errors=True,
            )
            # #5515: library_tracks_removed alone only feeds the scan-result
            # counter (useScanProgress); the library view refetches on
            # library_updated, so folder removal must announce it too or the
            # just-deleted rows stay visible until a manual reload.
            await broadcast_typed(
                connection_manager,
                "library_updated",
                {"action": "update", "track_count": 0},
                suppress_errors=True,
            )
    return removed


def parse_scan_folders(settings: Any) -> list[str]:
    """The settings row's scan_folders as a list; [] when unset or unparseable."""
    return _scan_folders_or_none(settings) or []


def _scan_folders_or_none(settings: Any) -> list[str] | None:
    """scan_folders as a list, [] when unset, None when the value cannot be parsed."""
    if not settings or not settings.scan_folders:
        return []
    raw = settings.scan_folders
    try:
        folders = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return None
    return [str(f) for f in folders if f] if isinstance(folders, list) else None


async def current_scan_folders(library_database: Any) -> list[str] | None:
    """The configured scan folders now; None when settings cannot be read or parsed.

    None, not []: an unreadable list is not an empty one, and the caller would
    prune every folder in it as removed.
    """
    try:
        folders = _scan_folders_or_none(await asyncio.to_thread(library_database.settings.get_settings))
    except Exception as exc:
        logger.error(f"Could not read the scan folders: {exc}")
        return None
    if folders is None:
        logger.error("Could not parse the configured scan folders")
    return folders


async def prune_folders_removed_during_scan(
    library_database: Any, folders_at_start: Sequence[str], connection_manager: Any | None
) -> int:
    """Prune again under scan folders removed while a scan was walking them (#6556).

    Removing a folder prunes its rows once, but a scan already walking it went
    on adding them back (and its files may no longer be trusted, so they were
    visible-but-broken). Run after the scan thread is done: a removal saved
    before the settings read here is pruned again now; one saved after it
    prunes on its own, with every row of this scan already written.
    """
    current = await current_scan_folders(library_database) if folders_at_start else None
    if current is None:
        return 0
    kept = {reservation_key(folder) for folder in current}
    removed = 0
    for folder in folders_at_start:
        if reservation_key(folder) not in kept:
            removed += await prune_tracks_under_folder(library_database, folder, connection_manager, current)
    return removed
