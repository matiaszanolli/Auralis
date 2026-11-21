"""
Terminal scan frames shared by the manual scan route and the auto-scanner (#6574)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``routers/library_scan_events.py`` and ``services/library_auto_scanner.py`` each
carried their own copy of the ``library_updated`` decision and drifted: the
auto-scanner tested only ``files_added or removed``, so a background rescan that
only updated rows (a retagged, replaced or relocated file) never refreshed the open
library views. Both now publish through this one helper. Beside
``scan_events.scan_complete_payload``, which builds the frame it sends.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from websocket.outbound_messages import broadcast_typed

from .scan_events import scan_complete_payload


async def broadcast_scan_complete(
    connection_manager: Any, result: Any, removed: Any, *, suppress_errors: bool = False
) -> None:
    """Broadcast ``scan_complete`` and, if any track was added, updated or removed, ``library_updated``.

    ``suppress_errors`` is for the auto-scanner, whose background cycle must not die on a
    broadcast failure; the manual route lets it surface.
    """
    if not connection_manager:
        return
    await broadcast_typed(
        connection_manager, "scan_complete", scan_complete_payload(result), suppress_errors=suppress_errors
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
            suppress_errors=suppress_errors,
        )
