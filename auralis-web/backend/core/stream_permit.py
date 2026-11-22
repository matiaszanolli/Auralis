#!/usr/bin/env python3

"""
Stream Permit and Failure Reply
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The two pieces of stream skeleton the normal entry point (stream_normal.py) and the enhanced/seek one
(stream_enhanced_lifecycle.py) share (#6626): taking a concurrent-stream slot, and reporting a stream
that raised. Each was a hand-kept copy in both, with the fix history (#2185, #4329, #5488) restated.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .job_error_mapping import _safe_error_message

if TYPE_CHECKING:
    from .audio_stream_controller import AudioStreamController

logger = logging.getLogger(__name__)


async def acquire_stream_permit(
    controller: 'AudioStreamController', track_id: int, websocket: WebSocket
) -> bool:
    """Take one of the ``MAX_CONCURRENT_STREAMS`` slots, or tell the client the server is busy.

    The limit keeps memory bounded (#2185). On False nothing was acquired and the caller returns. On
    True the caller owns the permit and releases it exactly once, in a finally that also covers the
    track lookup: a CancelledError during that await must not leak it (#4329).
    """
    try:
        await asyncio.wait_for(
            controller._stream_semaphore.acquire(),
            timeout=_asc.STREAM_ACQUIRE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning(
            f"Stream limit ({_asc.MAX_CONCURRENT_STREAMS}) reached, rejecting track {track_id}"
        )
        await controller._send_error(websocket, track_id, "Server busy - too many active streams")
        return False
    return True


async def report_stream_failure(
    controller: 'AudioStreamController',
    websocket: WebSocket,
    track_id: int,
    exc: Exception,
    *,
    failed_log: str,
    **error_kwargs: Any,
) -> None:
    """Log a stream that raised and, while the socket is still up, send the client its category.

    The message is the specific category from ``_safe_error_message``, not a blanket string (#5488).
    ``error_kwargs`` carries the enhanced/seek ``error_code``; the normal stream sends none.
    """
    logger.error(f"{failed_log}: {exc}", exc_info=exc)
    if controller._is_websocket_connected(websocket):
        await controller._send_error(
            websocket, track_id, _safe_error_message(exc, default="Audio streaming failed"), **error_kwargs
        )
