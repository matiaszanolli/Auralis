#!/usr/bin/env python3

"""
Stream Fingerprint Readiness
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Helpers used by the streaming entry points to ensure a track's fingerprint
is available (or queued) before/while adaptive mastering streams it.

Extracted from audio_stream_controller.py (#4071). Both functions take the
AudioStreamController instance as `controller` since they read
controller.fingerprint_generator / controller._get_repository_factory.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import TYPE_CHECKING

from fastapi import WebSocket

if TYPE_CHECKING:
    from .audio_stream_controller import AudioStreamController

logger = logging.getLogger(__name__)


async def ensure_fingerprint_available(
    controller: 'AudioStreamController',
    track_id: int,
    filepath: str,
    websocket: WebSocket | None = None
) -> bool:
    """
    Ensure fingerprint is available (cached or generated).

    Attempts to load or generate a fingerprint before streaming begins.
    If generation fails, proceeds gracefully without fingerprint.

    Sends progress messages to WebSocket if provided.

    Args:
        controller: AudioStreamController instance
        track_id: ID of the track
        filepath: Path to audio file
        websocket: Optional WebSocket connection for progress messages

    Returns:
        True if fingerprint was available/generated, False if not available
    """
    if not controller.fingerprint_generator:
        logger.debug(f"FingerprintGenerator not available, skipping fingerprint loading")
        return False

    try:
        logger.info(f"📊 Ensuring fingerprint available for track {track_id}...")

        # Send fingerprint_progress: analyzing message
        if websocket:
            await controller._send_fingerprint_progress(
                websocket,
                track_id=track_id,
                status="analyzing",
                message="Analyzing audio for optimal mastering..."
            )

        fingerprint_data = await controller.fingerprint_generator.get_or_generate(
            track_id=track_id,
            filepath=filepath
        )

        if fingerprint_data:
            logger.info(f"✅ Fingerprint is now available for track {track_id} (ready for adaptive mastering)")

            # Send fingerprint_progress: complete message
            if websocket:
                await controller._send_fingerprint_progress(
                    websocket,
                    track_id=track_id,
                    status="complete",
                    message="Fingerprint analysis complete"
                )

            return True
        else:
            logger.warning(f"⚠️  Fingerprint unavailable for track {track_id}, proceeding without optimization")

            # Send fingerprint_progress: failed message
            if websocket:
                await controller._send_fingerprint_progress(
                    websocket,
                    track_id=track_id,
                    status="failed",
                    message="Fingerprint generation failed, using default mastering"
                )

            return False

    except Exception as e:
        logger.warning(f"Fingerprint preparation failed for track {track_id}: {e}, proceeding without optimization")

        # Send fingerprint_progress: error message
        if websocket:
            await controller._send_fingerprint_progress(
                websocket,
                track_id=track_id,
                status="error",
                # Surface only the exception class; full detail is in the
                # server log above so file paths / ffmpeg stderr don't leak
                # to every connected WS client (fixes #3847, same pattern as
                # #3543 / #3846).
                message=f"Fingerprint error: {type(e).__name__}"
            )

        return False


async def check_or_queue_fingerprint(
    controller: 'AudioStreamController',
    track_id: int,
    filepath: str,
    websocket: WebSocket | None = None
) -> bool:
    """
    Non-blocking fingerprint check - queue generation instead of waiting.

    Phase 7.5: Don't block streaming on fingerprint generation.
    - If fingerprint exists in database: return True immediately
    - If fingerprint missing: queue for background generation, return False
    - Stream starts immediately with standard mastering either way

    Args:
        controller: AudioStreamController instance
        track_id: ID of the track
        filepath: Path to audio file
        websocket: Optional WebSocket connection for progress messages

    Returns:
        True if fingerprint is cached and ready, False if not (generation queued)
    """
    if not controller._get_repository_factory:
        logger.debug(f"RepositoryFactory not available, skipping fingerprint check")
        return False

    try:
        # Quick database check - O(1) lookup, no blocking
        factory = controller._get_repository_factory()
        fingerprint_repo = factory.fingerprints

        if fingerprint_repo.exists(track_id):
            # Fingerprint already cached - streaming will use optimized mastering
            logger.info(f"✅ Fingerprint cached for track {track_id} (instant lookup)")
            if websocket:
                await controller._send_fingerprint_progress(
                    websocket,
                    track_id=track_id,
                    status="cached",
                    message="Using cached audio analysis"
                )
            return True

        # Fingerprint not cached - queue for background generation
        logger.info(f"📋 Fingerprint not cached for track {track_id}, queuing for background generation")

        # Try to enqueue via fingerprint queue (non-blocking)
        try:
            from analysis.fingerprint_queue import get_fingerprint_queue
            queue = get_fingerprint_queue()
            if queue:
                added = queue.enqueue(track_id)
                if added:
                    logger.info(f"📋 Track {track_id} queued for background fingerprinting")
                else:
                    logger.debug(f"Track {track_id} already queued or processing")
            else:
                logger.debug(f"Fingerprint queue not available")
        except Exception as q_err:
            logger.debug(f"Could not enqueue track {track_id}: {q_err}")

        # Send progress message - using standard mastering
        if websocket:
            await controller._send_fingerprint_progress(
                websocket,
                track_id=track_id,
                status="queued",
                message="Audio analysis queued, using standard mastering"
            )

        return False

    except Exception as e:
        logger.debug(f"Fingerprint check failed for track {track_id}: {e}")
        return False
