"""
Terminal library-scan WebSocket frames for the manual scan route
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

What ``scan_library`` used to inline (split from library_scan.py, #5831). The
progress bridge, fingerprint enqueue and ``scan_complete`` payload it shares
with the auto-scanner live in ``services/scan_events.py`` (#5912), and the terminal
``scan_complete`` / ``library_updated`` pair in ``services/scan_complete_broadcast.py``
(#6574). The frame
payload policy (#4651: redact only what the user did not supply) is unchanged.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections.abc import Sequence
from typing import Any

from services.missing_tracks import prune_folders_removed_during_scan, prune_missing_tracks
from services.scan_complete_broadcast import broadcast_scan_complete
from services.scan_fingerprint_enqueue import enqueue_scanned_for_fingerprinting
from websocket.outbound_messages import broadcast_typed

logger = logging.getLogger(__name__)


async def publish_scan_result(
    connection_manager: Any, library_database: Any, result: Any, folders_at_start: Sequence[str] = ()
) -> None:
    """Everything after a finished, non-rejected scan, in the order it must run.

    A scan that aborted (``result.error``, #5877) gets ``library_scan_error``
    instead of a ``scan_complete`` that read as "nothing new". #5458 prunes
    tracks whose files are gone, as the auto-scanner does, before
    ``scan_complete`` (useScanProgress counts a removal frame only while the
    scan is in progress); the count feeds the library_updated condition
    (#5515). Not when a folder could not be read: its files look missing
    (an unplugged drive, a permission-denied album) and would be deleted, nor
    when a moved-file check failed (#6569): that track's old row looks missing too.
    Scan folders removed while the scan ran are pruned again first (#6556).
    """
    await prune_folders_removed_during_scan(library_database, folders_at_start, connection_manager)
    if result.error:
        await broadcast_scan_error(connection_manager, result.error)
        return
    await enqueue_scanned_for_fingerprinting(result)
    removed = 0
    if result.prune_safe:
        removed = await prune_missing_tracks(library_database, connection_manager)
    else:
        logger.warning("Scan could not read every folder or check every moved file; skipping missing-track pruning")
    await broadcast_scan_complete(connection_manager, result, removed)


async def broadcast_scan_error(connection_manager: Any, message: str) -> None:
    """Terminal ``library_scan_error`` frame, so a ``library_scan_started``-driven
    UI leaves the scanning state (#4413). Callers pass messages that name no
    server paths (#3543, #4651)."""
    if connection_manager:
        await broadcast_typed(connection_manager, "library_scan_error", {"error": message})
