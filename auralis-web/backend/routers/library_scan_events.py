"""
Terminal library-scan WebSocket frames for the manual scan route
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

What ``scan_library`` used to inline (split from library_scan.py, #5831). The
progress bridge, fingerprint enqueue and ``scan_complete`` payload it shares
with the auto-scanner live in ``services/scan_events.py`` (#5912). The frame
payload policy (#4651: redact only what the user did not supply) is unchanged.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

from services.missing_tracks import prune_missing_tracks
from services.scan_events import scan_complete_payload
from services.scan_fingerprint_enqueue import enqueue_scanned_for_fingerprinting
from websocket.outbound_messages import broadcast_typed

logger = logging.getLogger(__name__)


async def publish_scan_result(connection_manager: Any, library_database: Any, result: Any) -> None:
    """Everything after a finished, non-rejected scan, in the order it must run.

    A scan that aborted (``result.error``, #5877) gets ``library_scan_error``
    instead of a ``scan_complete`` that read as "nothing new". #5458 prunes
    tracks whose files are gone, as the auto-scanner does, before
    ``scan_complete`` (useScanProgress counts a removal frame only while the
    scan is in progress); the count feeds the library_updated condition
    (#5515). Not when a folder could not be read: its files look missing
    (an unplugged drive, a permission-denied album) and would be deleted.
    """
    if result.error:
        await broadcast_scan_error(connection_manager, result.error)
        return
    await enqueue_scanned_for_fingerprinting(result)
    removed = 0
    if result.walk_complete:
        removed = await prune_missing_tracks(library_database, connection_manager)
    else:
        logger.warning("Scan could not read every folder; skipping missing-track pruning")
    await broadcast_scan_complete(connection_manager, result, removed)


async def broadcast_scan_complete(
    connection_manager: Any, result: Any, removed: Any
) -> None:
    """Broadcast ``scan_complete`` and, if anything changed, ``library_updated``."""
    if not connection_manager:
        return
    await broadcast_typed(
        connection_manager,
        "scan_complete",
        scan_complete_payload(result),
    )
    if result.files_added or result.files_updated or removed:
        await broadcast_typed(
            connection_manager,
            "library_updated",
            # Fields here must match LibraryUpdatedMessage in
            # frontend/src/types/ws/library.ts.
            {
                "action": "scan",
                "track_count": result.files_added,
            },
        )


async def broadcast_scan_error(connection_manager: Any, message: str) -> None:
    """Terminal ``library_scan_error`` frame, so a ``library_scan_started``-driven
    UI leaves the scanning state (#4413). Callers pass messages that name no
    server paths (#3543, #4651)."""
    if connection_manager:
        await broadcast_typed(connection_manager, "library_scan_error", {"error": message})
