"""
Regression tests for the per-seek/per-play temp-WAV leak (#5253)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SeekableSource.resolve() (core/seekable_source.py, #4737) converts a
non-natively-seekable format (m4a/aac/wma) to a temp WAV exactly once per
ChunkedAudioProcessor instance. ChunkedAudioProcessor.close() already
correctly releases it (delegates to SeekableSource.close()) — but neither
stream_enhanced.py's nor stream_seek.py's `finally` block ever called
processor.close() at all, so every seek or play of one of those formats
leaked its temp WAV for the process lifetime, with no startup sweep able to
reclaim it (see test_startup_temp_sweep_ownership.py's
TestSeekableTempSweep for that half of the fix).

This file is the sibling harness of test_chunk_timeout_stream_abort_4999.py
and test_chunk_timeout_seek_stream_abort_5074.py (SIBLING: same
mocked-processor/controller/websocket wiring), used here to prove
processor.close() runs on stream teardown — both on a clean completion and
on the early-exit path where processor is never even constructed (the
UnboundLocalError hazard the fix's `processor: ... | None = None`
declaration guards against).
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController

CHUNK_DURATION = 15.0
TRACK_ID = 42
PRESET = "adaptive"
INTENSITY = 1.0
SAMPLE_RATE = 44100


def _make_websocket() -> MagicMock:
    ws = MagicMock()
    ws.client_state = MagicMock()
    ws.client_state.name = "CONNECTED"

    async def fake_send_text(text: str) -> None:
        json.loads(text)  # just prove it's well-formed; content isn't asserted here

    ws.send_text = AsyncMock(side_effect=fake_send_text)
    ws.send_bytes = AsyncMock()
    return ws


def _make_single_chunk_processor() -> MagicMock:
    """A processor for a one-chunk track, so the stream completes (and its
    `finally` runs) in one iteration — close() must have been called by the
    time the coroutine returns."""
    proc = MagicMock()
    proc.track_id = TRACK_ID
    proc.preset = PRESET
    proc.intensity = INTENSITY
    proc.sample_rate = SAMPLE_RATE
    proc.channels = 2
    proc.total_chunks = 1
    proc.chunk_duration = CHUNK_DURATION
    proc.chunk_interval = CHUNK_DURATION
    proc.duration = CHUNK_DURATION

    good_audio = np.zeros((SAMPLE_RATE * int(CHUNK_DURATION), 2), dtype=np.float32)

    async def process_chunk_safe(chunk_idx: int, fast_start: bool = False):
        return (Path(f"/tmp/chunk_{chunk_idx}.wav"), good_audio.copy())

    proc.process_chunk_safe = process_chunk_safe
    # Real ChunkedAudioProcessor.close() is sync (delegates to
    # SeekableSource.close(), itself sync) — .close is a plain MagicMock
    # attribute here, called via `await asyncio.to_thread(processor.close)`.
    proc.close = MagicMock()
    return proc


def _wire_controller(processor: MagicMock) -> tuple[AudioStreamController, MagicMock]:
    ws = _make_websocket()
    controller = AudioStreamController(
        chunked_processor_class=MagicMock(return_value=processor),
    )
    controller._send_stream_start = AsyncMock(return_value=True)
    controller.chunked_processor_class = MagicMock(return_value=processor)

    mock_track = MagicMock()
    mock_track.filepath = "/tmp/fake.wav"
    factory = MagicMock()
    factory.tracks.get_by_id.return_value = mock_track
    factory.fingerprints.exists.return_value = False
    controller._get_repository_factory = MagicMock(return_value=factory)
    return controller, ws


class TestProcessorClosedOnCleanCompletion:
    """The common case: a track streams to completion. Nothing in the
    ordinary success path used to call .close() at all."""

    @pytest.mark.asyncio
    async def test_stream_enhanced_audio_closes_the_processor(self):
        processor = _make_single_chunk_processor()
        controller, ws = _wire_controller(processor)

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
            )

        processor.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_enhanced_audio_from_position_closes_the_processor(self):
        processor = _make_single_chunk_processor()
        controller, ws = _wire_controller(processor)

        with patch("core.stream_seek.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio_from_position(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY,
                websocket=ws, start_position=0.0,
            )

        processor.close.assert_called_once()


class TestProcessorClosedOnChunkFailure:
    """A per-chunk failure ends the stream early (#3190/#4790/#4999) — the
    processor these entry points constructed must still be released."""

    @pytest.mark.asyncio
    async def test_stream_enhanced_audio_closes_processor_after_chunk_error(self):
        processor = _make_single_chunk_processor()

        async def _raise(chunk_idx, fast_start=False):
            raise RuntimeError("DSP exploded")

        processor.process_chunk_safe = _raise
        controller, ws = _wire_controller(processor)

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
            )

        processor.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_enhanced_audio_from_position_closes_processor_after_chunk_error(self):
        processor = _make_single_chunk_processor()

        async def _raise(chunk_idx, fast_start=False):
            raise RuntimeError("DSP exploded")

        processor.process_chunk_safe = _raise
        controller, ws = _wire_controller(processor)

        with patch("core.stream_seek.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio_from_position(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY,
                websocket=ws, start_position=0.0,
            )

        processor.close.assert_called_once()


class TestNoCrashWhenProcessorNeverConstructed:
    """If the track lookup fails before a processor is ever constructed, the
    `finally` block's `if processor is not None:` guard must not raise
    UnboundLocalError — the exact hazard of declaring `processor` only
    inside the try block."""

    @pytest.mark.asyncio
    async def test_stream_enhanced_audio_survives_track_not_found(self):
        processor = _make_single_chunk_processor()
        controller, ws = _wire_controller(processor)
        controller._get_repository_factory().tracks.get_by_id.return_value = None

        # Must not raise (UnboundLocalError or otherwise) — a clean early
        # return with an error sent to the client.
        await controller.stream_enhanced_audio(
            track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
        )

        processor.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_stream_enhanced_audio_from_position_survives_track_not_found(self):
        processor = _make_single_chunk_processor()
        controller, ws = _wire_controller(processor)
        controller._get_repository_factory().tracks.get_by_id.return_value = None

        await controller.stream_enhanced_audio_from_position(
            track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY,
            websocket=ws, start_position=0.0,
        )

        processor.close.assert_not_called()
