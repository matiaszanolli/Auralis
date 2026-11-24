#!/usr/bin/env python3

"""
Stream Fingerprint Readiness
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Helper used by the streaming entry points to check that a track's fingerprint
is available (or queued) before/while adaptive mastering streams it.

Extracted from audio_stream_controller.py (#4071). It takes the
AudioStreamController instance as `controller` since it reads
controller._get_repository_factory.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import WebSocket

if TYPE_CHECKING:
    from .audio_stream_controller import AudioStreamController

logger = logging.getLogger(__name__)


async def _enqueue(track_id: int) -> bool:
    """Queue background fingerprinting; True when the track is actually waiting for it (#5919)."""
    try:
        from analysis.fingerprint_queue import get_fingerprint_queue
        queue = get_fingerprint_queue()
        if not queue:
            logger.debug("Fingerprint queue not available")
            return False
        added = await asyncio.to_thread(queue.enqueue, track_id)
        pending: bool = added or await asyncio.to_thread(queue.is_pending, track_id)
        if added:
            logger.info(f"📋 Track {track_id} queued for background fingerprinting")
        elif pending:
            logger.debug(f"Track {track_id} already queued or processing")
        else:
            logger.warning(f"Fingerprint queue rejected track {track_id} (full)")
        return pending
    except Exception as q_err:
        logger.warning(f"Could not enqueue track {track_id}: {q_err}")
        return False


async def check_or_queue_fingerprint(
    controller: 'AudioStreamController',
    track_id: int,
    websocket: WebSocket | None = None,
    *,
    in_use: bool | None = None,
) -> bool:
    """Report the fingerprint status of a stream, and queue background generation when missing.

    ``in_use``: whether the stream's processor holds a fingerprint. True (a DB row, a ``.25d``
    sidecar, or the whole-track extraction it ran at construction): the stream is fingerprint-
    mastered whatever the database says, so it is reported as such (#6507); a missing DB row is
    still queued, quietly, to persist it. False: the processor tried that extraction and it failed
    for this track, so the client is told so and that each chunk is mastered on its own (#6492);
    a background retry is still queued. None (no processor information): a missing fingerprint is
    queued and the stream reported as standard mastering. Never blocks the stream on generation.

    Returns:
        True when the stream is fingerprint-mastered, False when it is not.
    """
    if not controller._get_repository_factory:
        logger.debug("RepositoryFactory not available, skipping fingerprint check")
        return False
    try:
        # Offloaded (#4566): a full session + SELECT COUNT at every stream start, and a locked DB
        # (concurrent scan or fingerprint write) used to block the whole event loop on it.
        fingerprint_repo = controller._get_repository_factory().fingerprints
        in_db = await asyncio.to_thread(fingerprint_repo.exists, track_id)
        if in_db or in_use:
            if not in_db:
                await _enqueue(track_id)  # only to persist the analysis the stream already uses
            logger.info(f"✅ Track {track_id} streams with its fingerprint ({'database' if in_db else 'extracted'})")
            if websocket:
                await controller._send_fingerprint_progress(
                    websocket, track_id=track_id, status="cached", message="Using cached audio analysis"
                )
            return True

        if in_use is False:
            logger.warning(f"Whole-track analysis failed for track {track_id}; mastering each chunk on its own")
            await _enqueue(track_id)  # a background retry, which may succeed where this one failed
            if websocket:
                await controller._send_fingerprint_progress(
                    websocket, track_id=track_id, status="failed",
                    message="Audio analysis failed for this track, mastering each chunk on its own",
                )
            return False

        logger.info(f"📋 Fingerprint not cached for track {track_id}, queuing for background generation")
        pending = await _enqueue(track_id)
        if websocket:
            await controller._send_fingerprint_progress(
                websocket,
                track_id=track_id,
                status="queued" if pending else "failed",
                message=(
                    "Audio analysis queued, using standard mastering"
                    if pending
                    else "Audio analysis unavailable, using standard mastering"
                ),
            )
        return False
    except Exception as e:
        logger.debug(f"Fingerprint check failed for track {track_id}: {e}")
        return False
