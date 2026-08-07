"""
Regression tests for chunk-timeout seek-stream abort (#5074)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sibling of test_chunk_timeout_stream_abort_4999.py. #4999 fixed
stream_enhanced_audio's chunk loop to end the stream on a chunk TimeoutError
instead of skip-and-continuing onto a processor an orphaned thread may still
be running inside (holding its threading.RLock, so every subsequent chunk
would itself time out ~CHUNK_PROCESS_TIMEOUT later in a serial pileup).

That fix's commit (1a4372cb) touched only stream_enhanced.py. stream_seek.py
runs the structurally identical chunk loop over the same long-lived
`processor` and the same `controller._process_chunk_only`, but its
`except Exception` still swallowed TimeoutError into the pre-#4999
skip-and-continue path — every scrub, and every play_enhanced with
start_position > 0 (i.e. every WebSocket reconnect resume), routes through
this file. #5074 lifts #4999's `except TimeoutError` branch into
stream_seek.py's loop.
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
TIMEOUT_AT_CHUNK = 3
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


def _make_processor(calls: list, timeout_at: int = TIMEOUT_AT_CHUNK) -> MagicMock:
    """Mock ChunkedAudioProcessor whose process_chunk_safe times out at
    *timeout_at* and would otherwise succeed for every other chunk (including
    ones AFTER timeout_at, to prove they're never attempted)."""
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
        calls.append(chunk_idx)
        if chunk_idx == timeout_at:
            # Mirrors what a hung DSP call looks like from process_chunk_only's
            # perspective: the wrapper future never resolves before wait_for's
            # deadline.
            raise TimeoutError(f"Chunk {chunk_idx} processing timed out after 30s")
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


class TestSeekChunkTimeoutAbortsStream:
    @pytest.mark.asyncio
    async def test_timeout_stops_the_seek_stream_instead_of_continuing(self):
        """A chunk timeout on a seek stream must end the stream — subsequent
        chunks (which would race the still-possibly-running orphaned
        thread's lock) must never be attempted."""
        calls: list[int] = []
        processor = _make_processor(calls, timeout_at=TIMEOUT_AT_CHUNK)
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)

        with patch("core.stream_seek.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio_from_position(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY,
                websocket=ws, start_position=0.0,
            )

        # The look-ahead pipeline may have already kicked off chunk
        # TIMEOUT_AT_CHUNK + 1 concurrently — that's a different in-flight
        # task, not a *subsequent* call issued after the timeout was
        # observed. What must never happen is process_chunk_safe for
        # anything beyond that.
        assert max(calls) <= TIMEOUT_AT_CHUNK + 1, (
            f"process_chunk_safe was called for chunks past the timeout: {calls}"
        )

    @pytest.mark.asyncio
    async def test_timeout_sends_a_distinct_error_message(self):
        """The client must be told the seek stream stopped due to a timeout,
        not the generic recoverable per-chunk failure message (#2085)."""
        calls: list[int] = []
        processor = _make_processor(calls, timeout_at=TIMEOUT_AT_CHUNK)
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)

        with patch("core.stream_seek.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio_from_position(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY,
                websocket=ws, start_position=0.0,
            )

        error_msgs = [m for m in sent if m.get("type") == "audio_stream_error"]
        assert error_msgs, "Expected an audio_stream_error message"
        assert "timed out" in error_msgs[0]["data"]["error"].lower()

    @pytest.mark.asyncio
    async def test_seek_stream_end_reports_stopped_not_completed(self):
        """The terminal message must reflect the seek stream stopped early,
        not that it delivered the full requested range (#4659)."""
        calls: list[int] = []
        processor = _make_processor(calls, timeout_at=TIMEOUT_AT_CHUNK)
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)

        with patch("core.stream_seek.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio_from_position(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY,
                websocket=ws, start_position=0.0,
            )

        end_msgs = [m for m in sent if m.get("type") == "audio_stream_end"]
        assert end_msgs, "Expected an audio_stream_end message"
        assert end_msgs[0]["data"]["reason"] == "stopped"

    @pytest.mark.asyncio
    async def test_plain_chunk_error_still_uses_skip_and_continue(self):
        """Sibling check: a non-timeout exception on a seek stream must still
        use #3190's recovery path (skip the chunk, keep streaming) — this fix
        must not regress ordinary seek-path error recovery."""
        calls: list[int] = []
        processor = _make_processor(calls, timeout_at=-1)  # never times out

        async def process_chunk_safe(chunk_idx: int, fast_start: bool = False):
            calls.append(chunk_idx)
            if chunk_idx == TIMEOUT_AT_CHUNK:
                raise RuntimeError("simulated non-timeout processing failure")
            good_audio = np.zeros((SAMPLE_RATE * int(CHUNK_DURATION), 2), dtype=np.float32)
            return (Path(f"/tmp/chunk_{chunk_idx}.wav"), good_audio.copy())

        processor.process_chunk_safe = process_chunk_safe

        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)

        with patch("core.stream_seek.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio_from_position(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY,
                websocket=ws, start_position=0.0,
            )

        # Chunks after the failed one must still have been attempted.
        assert max(calls) >= TOTAL_CHUNKS - 1, (
            f"non-timeout failures must still skip-and-continue: {calls}"
        )
        end_msgs = [m for m in sent if m.get("type") == "audio_stream_end"]
        assert end_msgs
        end_data = end_msgs[0]["data"]
        # #4790: a stream that skip-and-continues past a failed chunk is not
        # "completed" — it delivered fewer samples than the full range.
        assert end_data["reason"] == "errored"
