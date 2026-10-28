#!/usr/bin/env python3

"""
Stream Notification Messages
~~~~~~~~~~~~~~~~~~~~~~

The notifications half of the stream_messages split (#6269):
audio_stream_error and fingerprint_progress — messages about a stream,
sent outside its start/end/completion lifecycle.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket

from . import audio_stream_controller as _asc

if TYPE_CHECKING:
    from .audio_stream_controller import AudioStreamController

logger = logging.getLogger(__name__)


async def send_error(
    controller: 'AudioStreamController',
    websocket: WebSocket,
    track_id: int,
    error_message: str,
    recovery_position: float | None = None,
    error_code: str = "STREAMING_ERROR",
    stream_continues: bool = False,
) -> None:
    """Send audio_stream_error message to client.

    ``recovery_position`` is where the client may seek/retry after a chunk
    failure (#2085); ``error_code`` is the machine-readable code for frontend
    recovery logic; ``stream_continues`` says the pump skips the failed chunk
    and keeps sending (#3190), so the client keeps its engine (#5867).
    """
    if not controller._is_websocket_connected(websocket):
        return

    data: dict[str, Any] = {
        "track_id": track_id,
        "error": error_message,
        "code": error_code,
        "stream_type": _asc._stream_type_var.get(),
        # #5861: same rationale as send_stream_end — a late error from a
        # superseded stream must not tear down the live one.
        "stream_epoch": _asc._stream_epoch_var.get(),
    }
    if recovery_position is not None:
        data["recovery_position"] = recovery_position
    if stream_continues:
        data["continues"] = True
    message: dict[str, Any] = {"type": "audio_stream_error", "data": data}
    # safe_send classifies the outcome by connection state (#5273): a client
    # disconnect racing the send logs at debug, a genuine failure at warning —
    # never at ERROR, which triaged as a server-side fault.
    await controller._safe_send(websocket, message)


async def send_fingerprint_progress(
    controller: 'AudioStreamController',
    websocket: WebSocket,
    track_id: int,
    status: str,
    message: str
) -> None:
    """Send fingerprint_progress to the client via ``controller._safe_send``, so
    a benign disconnect racing the update logs at debug, not ERROR (#5273)."""
    progress_message: dict[str, Any] = {
        "type": "fingerprint_progress",
        "data": {
            "track_id": track_id,
            "status": status,
            "message": message,
            "stream_type": _asc._stream_type_var.get(),
        },
    }
    if await controller._safe_send(websocket, progress_message):
        logger.debug(f"Sent fingerprint_progress: track={track_id}, status={status}")
