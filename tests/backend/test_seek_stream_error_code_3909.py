"""
Regression tests: seek-stream error frames carry error_code="SEEK_ERROR" (#3909)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Only the seek-path's 30s processor-init timeout passed error_code="SEEK_ERROR"
to _send_error; every other failure in the seek stream (the outer catch-all,
the intra-loop chunk-processing error, the chunk-DSP-timeout, and the
chunk-delivery-failure branches) omitted it and silently defaulted to
"STREAMING_ERROR" — so frontend recovery logic keyed on code === "SEEK_ERROR"
only ever fired for the least common of the five failure modes.

Reuses the harness from test_chunk_timeout_seek_stream_abort_5074.py.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController

CHUNK_DURATION = 30.0
CHUNK_INTERVAL = 10.0
TOTAL_CHUNKS = 10
TRACK_ID = 42
PRESET = "adaptive"
INTENSITY = 1.0
SAMPLE_RATE = 44100


def _make_websocket(sent_messages: list) -> MagicMock:
    ws = MagicMock()
    ws.client_state = MagicMock()
    ws.client_state.name = "CONNECTED"

    async def fake_send_text(text: str) -> None:
        sent_messages.append(json.loads(text))

    ws.send_text = AsyncMock(side_effect=fake_send_text)
    ws.send_bytes = AsyncMock()
    return ws


def _make_processor(*, raise_at: int | None = None, exc: Exception | None = None) -> MagicMock:
    """Mock ChunkedAudioProcessor. If raise_at is set, process_chunk_safe
    raises `exc` for that chunk index and succeeds otherwise."""
    proc = MagicMock()
    proc.track_id = TRACK_ID
    proc.preset = PRESET
    proc.intensity = INTENSITY
    proc.sample_rate = SAMPLE_RATE
    proc.channels = 2
    proc.total_chunks = TOTAL_CHUNKS
    proc.chunk_duration = CHUNK_DURATION
    proc.chunk_interval = CHUNK_INTERVAL
    proc.duration = TOTAL_CHUNKS * CHUNK_DURATION

    good_audio = np.zeros((SAMPLE_RATE * int(CHUNK_DURATION), 2), dtype=np.float32)

    async def process_chunk_safe(chunk_idx: int, fast_start: bool = False):
        del fast_start
        if raise_at is not None and chunk_idx == raise_at:
            assert exc is not None
            raise exc
        return (Path(f"/tmp/chunk_{chunk_idx}.wav"), good_audio.copy())

    proc.process_chunk_safe = process_chunk_safe
    return proc


def _wire_controller(processor: MagicMock, ws_sent: list) -> tuple[AudioStreamController, MagicMock]:
    ws = _make_websocket(ws_sent)
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


async def _run_seek_stream(controller: AudioStreamController, ws: MagicMock) -> None:
    with patch("core.stream_seek.Path.exists", return_value=True), \
         patch.object(controller, "_check_or_queue_fingerprint",
                      new=AsyncMock(return_value=False)):
        await controller.stream_enhanced_audio_from_position(
            track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY,
            websocket=ws, start_position=0.0,
        )


def _error_frames(sent: list[dict]) -> list[dict]:
    return [m for m in sent if m.get("type") == "audio_stream_error"]


class TestSeekStreamErrorCode:
    @pytest.mark.asyncio
    async def test_chunk_dsp_timeout_carries_seek_error_code(self):
        processor = _make_processor(raise_at=3, exc=TimeoutError("chunk 3 timed out"))
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)

        await _run_seek_stream(controller, ws)

        errors = _error_frames(sent)
        assert errors, "Expected an audio_stream_error message"
        assert errors[0]["data"]["code"] == "SEEK_ERROR"

    @pytest.mark.asyncio
    async def test_plain_chunk_processing_error_carries_seek_error_code(self):
        processor = _make_processor(raise_at=2, exc=ValueError("bad chunk"))
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)

        await _run_seek_stream(controller, ws)

        errors = _error_frames(sent)
        assert errors, "Expected an audio_stream_error message"
        assert errors[0]["data"]["code"] == "SEEK_ERROR"

    @pytest.mark.asyncio
    async def test_chunk_delivery_failure_carries_seek_error_code(self):
        processor = _make_processor()
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)
        controller._stream_processed_chunk = AsyncMock(side_effect=[False])

        await _run_seek_stream(controller, ws)

        errors = _error_frames(sent)
        assert errors, "Expected an audio_stream_error message"
        assert errors[0]["data"]["code"] == "SEEK_ERROR"
        assert "Failed to send audio chunk" in errors[0]["data"]["error"]

    @pytest.mark.asyncio
    async def test_outer_catch_all_carries_seek_error_code(self):
        """A failure BEFORE the chunk loop (missing processor metadata) hits
        stream_seek.py's own outer `except Exception` handler — the original
        site cited by #3909. (Track resolution itself is a helper shared with
        stream_normal.py/stream_enhanced.py that sends its own error before
        control ever reaches this function's try/except, so it can't be used
        to exercise this particular handler.)"""
        processor = _make_processor()
        processor.total_chunks = None  # triggers the metadata-missing raise
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)

        await _run_seek_stream(controller, ws)

        errors = _error_frames(sent)
        assert errors, "Expected an audio_stream_error message"
        assert errors[0]["data"]["code"] == "SEEK_ERROR"

    @pytest.mark.asyncio
    async def test_server_busy_capacity_error_stays_generic(self):
        """Sibling check: the "too many active streams" rejection is shared
        capacity-limit logic identical across normal/enhanced/seek streams —
        it must NOT be tagged SEEK_ERROR, which would misdirect seek-specific
        frontend recovery at a condition unrelated to seeking."""
        processor = _make_processor()
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)
        controller._stream_semaphore.acquire = AsyncMock(
            side_effect=__import__("asyncio").TimeoutError()
        )

        await _run_seek_stream(controller, ws)

        errors = _error_frames(sent)
        assert errors, "Expected an audio_stream_error message"
        assert errors[0]["data"]["code"] != "SEEK_ERROR"
