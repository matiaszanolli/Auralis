#!/usr/bin/env python3

"""
Enhanced Audio Streaming
~~~~~~~~~~~~~~~~~~~~~~~~

The stream_enhanced_audio entry point: streams DSP-processed (mastered)
audio chunks to a client via WebSocket, with look-ahead processing and
per-chunk error recovery. Emitted chunks tile with no boundary crossfade (#4642).

Extracted from audio_stream_controller.py (#4071).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any
from collections.abc import Callable

from fastapi import WebSocket

from . import audio_stream_controller as _asc
from .stream_enhanced_chunks import pump_chunks, validate_processor_metadata
from .stream_enhanced_lifecycle import EnhancedStream, StreamFlavour, run_enhanced_stream
from .proactive_buffer import buffer_presets_for_track
from helpers import spawn_background_task
from security.path_security import validate_file_path

logger = logging.getLogger(__name__)

_FLAVOUR = StreamFlavour(
    stopped_log="Audio streaming stopped: client disconnected",
    failed_log="Audio streaming failed",
)


async def stream_enhanced_audio(
    controller: '_asc.AudioStreamController',
    track_id: int,
    preset: str,
    intensity: float,
    websocket: WebSocket,
    on_progress: Callable[[int, float, str], Any] | None = None
) -> None:
    """
    Stream enhanced audio chunks to client via WebSocket.

    The semaphore / cancel-event / processor / teardown skeleton is shared with the seek stream in
    stream_enhanced_lifecycle.run_enhanced_stream (#6214).

    Args:
        controller: AudioStreamController instance
        track_id: Track ID to process and stream
        preset: Processing preset (only "adaptive" exists)
        intensity: Processing intensity (0.0-1.0)
        websocket: WebSocket connection to client
        on_progress: Optional callback for progress updates

    Raises:
        ValueError: If the chunked processor class or the repository factory is unavailable
    """

    async def body(stream: EnhancedStream, validated_filepath: str) -> None:
        processor = stream.processor
        assert processor is not None
        # Ensure processor has loaded metadata (fixes #2735)
        validate_processor_metadata(processor)

        # Proactively buffer the first chunks across every preset so an early preset switch does not
        # wait the full DSP window (#3884). Each chunk is cached to the same on-disk WAV cache
        # process_chunk_safe() reads, a no-op for one already cached, so re-issuing the track is safe.
        # The handle is kept so the buffering dies with this stream, and it shares the stream's cancel
        # event so a render already inside an executor thread aborts too (#5378, #4815).
        stream.buffer_task = spawn_background_task(
            buffer_presets_for_track(
                track_id, validated_filepath, intensity, processor.total_chunks,
                cancel_event=stream.chunk_cancel_event,
            ),
            name=f"proactive_buffer:{track_id}",
        )

        # Non-blocking fingerprint check: queue one for background generation if missing and start
        # streaming at once with standard mastering.
        if await controller._check_or_queue_fingerprint(track_id=track_id, websocket=websocket):
            logger.info("🎯 Adaptive mastering will use fingerprint-optimized parameters (cached)")
        else:
            logger.info("📊 Streaming with standard adaptive mastering (fingerprint queued for background generation)")

        logger.info(
            f"Starting audio stream: track={track_id}, preset={preset}, "
            f"intensity={intensity}, chunks={processor.total_chunks}"
        )

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
        ):
            logger.info("WebSocket disconnected, cannot start stream")
            return

        # The process/send loop with look-ahead lives in stream_enhanced_chunks (#5032).
        pump = await pump_chunks(
            controller,
            websocket,
            track_id=track_id,
            processor=processor,
            on_progress=on_progress,
        )

        # Whether the loop ran to the end and how much audio reached the client (#4659, #4790).
        await controller._send_stream_completion(
            websocket,
            track_id=track_id,
            label="Audio stream",
            stopped_early=pump.stopped_early,
            failed_chunks=pump.failed_chunks,
            delivered_samples=pump.delivered_samples,
            sample_rate=processor.sample_rate,
            full_duration=processor.duration,
            log_full_duration_on_partial=True,
        )

    await run_enhanced_stream(
        controller, track_id, preset, intensity, websocket,
        flavour=_FLAVOUR, validate_file_path=validate_file_path, body=body,
    )
