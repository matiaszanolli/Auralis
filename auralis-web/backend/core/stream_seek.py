#!/usr/bin/env python3

"""
Enhanced Audio Streaming From Position (Seek)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The stream_enhanced_audio_from_position entry point: like stream_enhanced,
but starts from an arbitrary mid-track position with precise sample-level
trim of the first chunk.

Extracted from audio_stream_controller.py (#4071).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any
from collections.abc import Callable

from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .chunk_boundaries import (
    SEEK_MIN_CHUNK_REMAINDER,
    chunk_for_position,
)
from .stream_enhanced_chunks import pump_chunks, validate_processor_metadata
from .stream_enhanced_lifecycle import EnhancedStream, StreamFlavour, run_enhanced_stream
from security.path_security import validate_file_path

logger = logging.getLogger(__name__)

_FLAVOUR = StreamFlavour(
    stopped_log="Seek streaming stopped: client disconnected",
    failed_log="Seek streaming failed",
    init_timeout_log_suffix=" during seek",
    init_timeout_message=(
        "Audio processor initialization timed out during seek. File may be corrupt or on slow storage."
    ),
    error_code="SEEK_ERROR",
)


async def stream_enhanced_audio_from_position(
    controller: '_asc.AudioStreamController',
    track_id: int,
    preset: str,
    intensity: float,
    websocket: WebSocket,
    start_position: float,
    on_progress: Callable[[int, float, str], Any] | None = None
) -> None:
    """
    Stream enhanced audio chunks starting from a specific position (seek).

    It starts streaming from the chunk containing the target position, with an offset applied for
    precise seeking. The lifecycle skeleton is shared with stream_enhanced_audio (#6214).

    Args:
        controller: AudioStreamController instance
        track_id: Track ID to process and stream
        preset: Processing preset (only "adaptive" exists)
        intensity: Processing intensity (0.0-1.0)
        websocket: WebSocket connection to client
        start_position: Position in seconds to start streaming from
        on_progress: Optional callback for progress updates

    Raises:
        ValueError: If the chunked processor class or the repository factory is unavailable
    """

    async def body(stream: EnhancedStream, _validated_filepath: str) -> None:
        processor = stream.processor
        assert processor is not None
        # Ensure processor has loaded metadata (fixes #2735)
        meta = validate_processor_metadata(processor)

        # Map the requested position onto the chunk that actually EMITS it
        # (#4557). `int(start_position / chunk_interval)` mapped onto the chunk *core* timeline, but
        # extract_chunk_segment had already skipped OVERLAP_DURATION from the trimmed buffer, so every
        # seek to >= 10s landed 5s past the requested point for the rest of the stream.
        #
        # chunk_for_position derives both values from the same constants the
        # extraction uses, and may advance to the next chunk when the requested
        # point falls within a sliver of its chunk's end — hence
        # effective_position, which is what the client must be told.
        start_chunk_idx, seek_offset, effective_position = chunk_for_position(
            start_position,
            meta.total_chunks,
            total_duration=meta.duration,
        )

        if start_position >= meta.duration:
            logger.info(
                f"Seek: requested {start_position:.2f}s is at/past the "
                f"{meta.duration:.2f}s track end; clamping to "
                f"{effective_position:.2f}s so audible audio is delivered"
            )
        elif effective_position != start_position:
            logger.info(
                f"Seek: requested {start_position:.2f}s falls within "
                f"{SEEK_MIN_CHUNK_REMAINDER}s of chunk {start_chunk_idx - 1}'s end; "
                f"advancing to chunk {start_chunk_idx} at {effective_position:.2f}s"
            )

        logger.info(
            f"Seek: position={effective_position}s → chunk {start_chunk_idx}/{processor.total_chunks}, "
            f"offset={seek_offset:.2f}s"
        )

        if not controller._is_websocket_connected(websocket):
            logger.info("WebSocket disconnected, aborting seek stream")
            return
        # The same fingerprint status play reports, from what this processor masters with (#6507).
        await controller._check_or_queue_fingerprint(track_id, websocket, in_use=bool(processor.fingerprint))

        # Send stream start message with seek info
        if not await controller._send_stream_start(
            websocket,
            track_id=track_id,
            preset=preset,
            intensity=intensity,
            sample_rate=processor.sample_rate,
            channels=processor.channels,
            total_chunks=processor.total_chunks,
            chunk_duration=processor.chunk_duration,
            total_duration=processor.duration,
            start_chunk=start_chunk_idx,
            # #4557: the source time of the first sample we will actually
            # deliver, which is what the client sets its position counter from
            # (useEnhancedStreamStart.ts). Reporting the raw request here is
            # what let the readout drift away from the audio.
            seek_position=effective_position,
            seek_offset=seek_offset,
        ):
            logger.info("WebSocket disconnected, cannot start seek stream")
            return

        # The process/send loop with look-ahead lives in stream_enhanced_chunks (#5032).
        pump = await pump_chunks(
            controller,
            websocket,
            track_id=track_id,
            processor=processor,
            start_chunk_idx=start_chunk_idx,
            seek_offset=seek_offset,
            effective_position=effective_position,
            error_code="SEEK_ERROR",
            label="seek stream",
            on_progress=on_progress,
        )

        # Distinguish a truncated seek stream from a completed one (#4659, #4790).
        await controller._send_stream_completion(
            websocket,
            track_id=track_id,
            label="Seek stream",
            stopped_early=pump.stopped_early,
            failed_chunks=pump.failed_chunks,
            delivered_samples=pump.delivered_samples,
            sample_rate=processor.sample_rate,
            full_duration=processor.duration,
        )

    await run_enhanced_stream(
        controller, track_id, preset, intensity, websocket,
        flavour=_FLAVOUR, validate_file_path=validate_file_path, body=body,
    )
