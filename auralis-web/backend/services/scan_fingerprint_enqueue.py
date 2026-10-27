"""
Post-scan fingerprint enqueue shared by the manual scan route
(routers/library_scan.py) and LibraryAutoScanner (services/library_auto_scanner.py).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def enqueue_scanned_for_fingerprinting(scan_result: Any) -> None:
    """Enqueue a scan's added AND updated tracks for background fingerprinting.

    Added tracks (#2382) have never been fingerprinted. Updated tracks (#5719)
    are enqueued too: a rescan that found the audio changed has just discarded
    the old fingerprint row, and one that did not leaves a current row the
    generator returns without recomputing.

    Failures are logged, never raised: fingerprinting is a follow-up, not part
    of the scan's success.
    """
    tracks = [
        *getattr(scan_result, 'added_tracks', ()),
        *getattr(scan_result, 'updated_tracks', ()),
    ]
    if not tracks:
        return
    try:
        from analysis.fingerprint_queue import get_fingerprint_queue
        fp_queue = get_fingerprint_queue()
        if fp_queue:
            # Offloaded (#4702): this is a comprehension over every
            # newly-added track, so its cost scales with scan size — a large
            # import would hold the loop for the whole sweep, stalling audio
            # streaming and the scan_complete broadcast. The whole loop is
            # offloaded rather than each enqueue, matching the batch pattern
            # in fingerprint_queue.py (#3335): one hop instead of N.
            def _enqueue_tracks() -> int:
                return sum(1 for t in tracks if fp_queue.enqueue(t.id))

            enqueued = await asyncio.to_thread(_enqueue_tracks)
            if enqueued:
                logger.info(f"Enqueued {enqueued} tracks for fingerprinting after scan")
    except Exception as fp_err:
        logger.warning(f"Fingerprint enqueue failed after scan: {fp_err}")
