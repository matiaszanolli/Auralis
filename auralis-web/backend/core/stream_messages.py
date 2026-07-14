#!/usr/bin/env python3

"""
Stream Control Messages
~~~~~~~~~~~~~~~~~~~~~~~

JSON control-message senders for the audio streaming protocol:
audio_stream_start, audio_stream_end, audio_stream_error, and
fingerprint_progress. Built on top of controller._safe_send
(stream_protocol.safe_send) — see stream_protocol.py's module docstring
for why these route through the controller rather than calling
stream_protocol functions directly.

Extracted from audio_stream_controller.py (#4071).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket

from . import audio_stream_controller as _asc

if TYPE_CHECKING:
    from .audio_stream_controller import AudioStreamController

logger = logging.getLogger(__name__)


async def send_stream_start(
    controller: 'AudioStreamController',
    websocket: WebSocket,
    track_id: int,
    preset: str,
    intensity: float,
    sample_rate: int,
    channels: int,
    total_chunks: int,
    chunk_duration: float,
    total_duration: float,
    start_chunk: int | None = None,
    seek_position: float | None = None,
    seek_offset: float | None = None,
) -> bool:
    """Send audio_stream_start message to client.

    When any of ``start_chunk`` / ``seek_position`` / ``seek_offset`` is
    provided, the message is emitted with ``is_seek: True`` so the client's
    resume guard (`usePlayNormal` / `usePlayEnhanced` `handleStreamStart`)
    preserves the existing AudioContext + PCMStreamBuffer instead of
    recreating them — required for both WS reconnect resume (#3185, #3755)
    and within-track seeks (#3187).

    Returns:
        True if message was sent, False if WebSocket was disconnected.
    """
    # Reset the per-stream frame counter at every audio_stream_start so
    # `seq` is monotonic across the whole stream and restarts at 0 on a new
    # stream / seek / resume — the client rebaselines on this message too
    # (fixes #3841). A fresh cell per stream-start keeps concurrent streams
    # in different tasks isolated.
    _asc._frame_seq_var.set([0])
    # Seed the per-stream track id so send_pcm_chunk can stamp it on each
    # audio_chunk_meta (#4434).
    _asc._track_id_var.set(track_id)

    is_seek = (
        start_chunk is not None
        or seek_position is not None
        or seek_offset is not None
    )
    data: dict[str, Any] = {
        "track_id": track_id,
        "preset": preset,
        "intensity": intensity,
        "sample_rate": sample_rate,
        "channels": channels,
        "total_chunks": total_chunks,
        "chunk_duration": chunk_duration,
        "total_duration": total_duration,
        "stream_type": _asc._stream_type_var.get(),
    }
    if is_seek:
        data["is_seek"] = True
        data["start_chunk"] = start_chunk if start_chunk is not None else 0
        data["seek_position"] = (
            seek_position if seek_position is not None else 0.0
        )
        data["seek_offset"] = (
            seek_offset if seek_offset is not None else 0.0
        )
    message: dict[str, Any] = {"type": "audio_stream_start", "data": data}
    if await controller._safe_send(websocket, message):
        if is_seek:
            logger.debug(
                f"Sent stream_start (seek): chunk {data['start_chunk']}/{total_chunks}, "
                f"position={data['seek_position']}s"
            )
        else:
            logger.debug(
                f"Sent stream_start: {total_chunks} chunks, {total_duration}s duration"
            )
        return True
    return False


async def send_stream_end(
    controller: 'AudioStreamController',
    websocket: WebSocket,
    track_id: int,
    total_samples: int,
    duration: float,
) -> bool:
    """Send audio_stream_end message to client.

    Returns:
        True if message was sent, False if WebSocket was disconnected.
    """
    message: dict[str, Any] = {
        "type": "audio_stream_end",
        "data": {
            "track_id": track_id,
            "total_samples": total_samples,
            "duration": duration,
            "stream_type": _asc._stream_type_var.get(),
        },
    }
    if await controller._safe_send(websocket, message):
        logger.debug(f"Sent stream_end: {total_samples} samples, {duration}s duration")
        return True
    return False


async def send_error(
    controller: 'AudioStreamController',
    websocket: WebSocket,
    track_id: int,
    error_message: str,
    recovery_position: float | None = None,
    error_code: str = "STREAMING_ERROR",
) -> None:
    """Send audio_stream_error message to client.

    Args:
        websocket: WebSocket connection to send the error to
        track_id: ID of the track that failed
        error_message: Human-readable error description
        recovery_position: Seconds into the track from which the client may
            seek/retry (set when a specific chunk fails, issue #2085).
        error_code: Machine-readable error code for frontend recovery logic
    """
    if not controller._is_websocket_connected(websocket):
        return

    data: dict[str, Any] = {
        "track_id": track_id,
        "error": error_message,
        "code": error_code,
        "stream_type": _asc._stream_type_var.get(),
    }
    if recovery_position is not None:
        data["recovery_position"] = recovery_position
    message: dict[str, Any] = {"type": "audio_stream_error", "data": data}
    try:
        import json
        await websocket.send_text(json.dumps(message))
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")


async def send_fingerprint_progress(
    websocket: WebSocket,
    track_id: int,
    status: str,
    message: str
) -> None:
    """
    Send fingerprint_progress message to client.

    Args:
        websocket: WebSocket connection
        track_id: Track ID being analyzed
        status: Progress status (analyzing, complete, failed, error)
        message: Human-readable progress message
    """
    progress_message: dict[str, Any] = {
        "type": "fingerprint_progress",
        "data": {
            "track_id": track_id,
            "status": status,
            "message": message,
            "stream_type": _asc._stream_type_var.get(),
        },
    }
    try:
        import json
        await websocket.send_text(json.dumps(progress_message))
        logger.debug(f"Sent fingerprint_progress: track={track_id}, status={status}")
    except Exception as e:
        logger.error(f"Failed to send fingerprint_progress message: {e}")
