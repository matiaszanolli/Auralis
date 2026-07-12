#!/usr/bin/env python3

"""
Stream Protocol (Wire Layer)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Low-level WebSocket send primitives and the binary PCM chunk framing
protocol.

Extracted from audio_stream_controller.py (#4071). See stream_messages.py
for the higher-level JSON control-message helpers (stream_start,
stream_end, error, fingerprint_progress) built on top of safe_send here.

is_websocket_connected is a pure function of the websocket. safe_send,
safe_send_bytes, and send_pcm_chunk take `controller` and route their
internal cross-calls through controller._is_websocket_connected /
controller._safe_send / controller._safe_send_bytes (not the free
functions in this module directly) so that tests patching those bound
methods (`patch.object(controller, "_safe_send_bytes", ...)`) still
intercept calls made from inside send_pcm_chunk, mirroring the original
`self.`-based call graph exactly.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .env_config import get_int_env

if TYPE_CHECKING:
    from .audio_stream_controller import AudioStreamController

logger = logging.getLogger(__name__)

# Maximum number of encoded frames queued ahead of the WebSocket sender.
# Limits Python-heap memory when the client is slower than the encoder.
# Override via AURALIS_SEND_QUEUE_MAXSIZE (#3917) — see
# auralis-web/backend/CONFIG.md.
_SEND_QUEUE_MAXSIZE: int = get_int_env("AURALIS_SEND_QUEUE_MAXSIZE", 4)


def is_websocket_connected(websocket: WebSocket) -> bool:
    """
    Check if WebSocket is still connected and can receive messages.

    Returns:
        True if WebSocket is connected, False if disconnected or closing.
    """
    try:
        return websocket.client_state.name == "CONNECTED"
    except Exception:
        return False


async def safe_send(controller: 'AudioStreamController', websocket: WebSocket, message: dict[str, Any]) -> bool:
    """
    Safely send a message to WebSocket, handling disconnection gracefully.

    Args:
        controller: AudioStreamController instance
        websocket: WebSocket connection
        message: Message dict to send as JSON

    Returns:
        True if message was sent, False if WebSocket was disconnected.
    """
    if not controller._is_websocket_connected(websocket):
        logger.debug("WebSocket disconnected, skipping send")
        return False
    try:
        await websocket.send_text(json.dumps(message))
        return True
    except RuntimeError as e:
        # Classify by connection state, not by Starlette's error wording
        # (#3850 — sibling of #3511). A send-after-close leaves client_state
        # != CONNECTED, so a disconnect logs at debug; anything else is a
        # genuine error worth a warning.
        if not controller._is_websocket_connected(websocket):
            logger.debug(f"WebSocket closed during send: {e}")
        else:
            logger.warning(f"WebSocket send failed: {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error sending WebSocket message: {e}")
        return False


async def safe_send_bytes(controller: 'AudioStreamController', websocket: WebSocket, data: bytes) -> bool:
    """Safely send binary data to WebSocket, handling disconnection gracefully."""
    if not controller._is_websocket_connected(websocket):
        logger.debug("WebSocket disconnected, skipping binary send")
        return False
    try:
        await websocket.send_bytes(data)
        return True
    except RuntimeError as e:
        # Classify by connection state, not by Starlette's error wording
        # (#3850 — sibling of #3511).
        if not controller._is_websocket_connected(websocket):
            logger.debug(f"WebSocket closed during binary send: {e}")
        else:
            logger.warning(f"WebSocket binary send failed: {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error sending WebSocket binary: {e}")
        return False


async def send_pcm_chunk(
    controller: 'AudioStreamController',
    websocket: WebSocket,
    pcm_samples: np.ndarray,
    chunk_index: int,
    total_chunks: int,
    crossfade_samples: int,
) -> None:
    """
    Send PCM samples to client as binary WebSocket frames.

    Each frame is preceded by a JSON metadata message (audio_chunk_meta)
    followed by the raw PCM bytes as a binary frame. This avoids the 33%
    overhead of base64 encoding while keeping metadata structured.

    Splits large PCM data into multiple frame pairs to stay below the
    WebSocket 1MB frame limit (~300KB raw per frame).

    Args:
        controller: AudioStreamController instance
        websocket: WebSocket connection
        pcm_samples: NumPy array of PCM samples (mono or stereo)
        chunk_index: Index of this chunk
        total_chunks: Total number of chunks
        crossfade_samples: Number of overlap samples at chunk boundary
    """
    # Ensure native float32 for the wire format. astype(copy=False) returns
    # the array untouched when it is already native float32 — the case for
    # every current caller (chunked_processor emits float32; the normal-path
    # SoundFile read uses dtype='float32') — so the common path allocates
    # nothing, instead of the dead `dtype != float32` branch that used to
    # gate (and on a miss, fully copy) the cast. A float64 or big-endian
    # source is still converted defensively rather than emitting a corrupt
    # little-endian PCM frame downstream (#3875, sibling of #3556).
    pcm_samples = pcm_samples.astype(np.float32, copy=False)

    # Split into smaller frames to avoid WebSocket 1MB frame limit.
    # Each float32 sample = 4 bytes. Target ~300KB raw per binary frame.
    #
    # Flatten to 1D first so that len() and slicing always operate on
    # individual float32 values rather than rows (fixes #2257: for stereo
    # 2D arrays len() returned frame-count, producing ~800KB frames).
    TARGET_FRAME_BYTES: int = 300 * 1024  # 300 KB raw (was 400KB base64)
    BYTES_PER_SAMPLE: int = 4  # float32
    pcm_flat: np.ndarray = pcm_samples.reshape(-1)
    samples_per_frame: int = TARGET_FRAME_BYTES // BYTES_PER_SAMPLE

    total_samples: int = len(pcm_flat)
    num_frames: int = (total_samples + samples_per_frame - 1) // samples_per_frame

    stream_type = _asc._stream_type_var.get()

    # Bounded producer/consumer: limits Python-heap accumulation when the
    # client is slower than the sender (backpressure for issue #2122).
    # Each item is a (metadata_dict, pcm_bytes) tuple; the consumer sends
    # the JSON metadata first, then the binary frame. On disconnect it
    # signals the producer to stop.
    queue: asyncio.Queue[tuple[dict[str, Any], bytes] | None] = asyncio.Queue(
        maxsize=_SEND_QUEUE_MAXSIZE
    )
    abort_event: asyncio.Event = asyncio.Event()

    # Monotonic sequence counter for text+binary frame pairing, kept in a
    # per-stream ContextVar cell so it stays monotonic ACROSS chunk
    # boundaries for the whole stream — clients use it to detect dropped or
    # reordered frames (fixes #3189, #3841). send_stream_start seeds the
    # cell to [0]; the lazy fallback below only fires if a chunk is somehow
    # sent without a preceding stream_start (keeps seq at least chunk-local).
    seq_cell = _asc._frame_seq_var.get()
    if seq_cell is None:
        seq_cell = [0]
        _asc._frame_seq_var.set(seq_cell)

    async def _producer() -> None:
        try:
            for frame_idx in range(num_frames):
                if abort_event.is_set():
                    break
                start_idx: int = frame_idx * samples_per_frame
                end_idx: int = min(start_idx + samples_per_frame, total_samples)
                frame_samples: np.ndarray = pcm_flat[start_idx:end_idx]

                metadata: dict[str, Any] = {
                    "type": "audio_chunk_meta",
                    "data": {
                        "seq": seq_cell[0],
                        "chunk_index": chunk_index,
                        "chunk_count": total_chunks,
                        "frame_index": frame_idx,
                        "frame_count": num_frames,
                        "sample_count": frame_samples.size,
                        "crossfade_samples": crossfade_samples,
                        "stream_type": stream_type,
                    },
                }
                seq_cell[0] += 1
                # frame_samples is a slice of pcm_flat which was cast
                # to np.float32 above; on x86/ARM/Apple Silicon that's
                # already little-endian, so a prior `astype('<f4')` was
                # a no-op copy of ~300 KB per frame × 9 frames × every
                # chunk. Pass-through-to-bytes is zero-copy when the
                # array is already contiguous little-endian float32
                # (fixes #3556 / BE-NEW-98).
                if frame_samples.dtype.byteorder in ('<', '=') and frame_samples.flags['C_CONTIGUOUS']:
                    pcm_bytes: bytes = frame_samples.tobytes()
                else:
                    pcm_bytes = frame_samples.astype('<f4').tobytes()
                await queue.put((metadata, pcm_bytes))
        finally:
            await queue.put(None)  # sentinel

    async def _consumer() -> None:
        while True:
            item = await queue.get()
            if item is None:
                break
            metadata, pcm_bytes = item
            # Send JSON metadata first, then raw binary PCM
            sent: bool = await controller._safe_send(websocket, metadata)
            if not sent:
                abort_event.set()
                while not queue.empty():
                    queue.get_nowait()
                break
            sent = await controller._safe_send_bytes(websocket, pcm_bytes)
            if not sent:
                abort_event.set()
                while not queue.empty():
                    queue.get_nowait()
                break
            frame_idx = metadata["data"]["frame_index"]
            logger.debug(
                f"Streamed chunk {chunk_index} frame {frame_idx}/{num_frames}: "
                f"{metadata['data']['sample_count']} samples ({len(pcm_bytes)} bytes)"
            )

    await asyncio.gather(_producer(), _consumer())
