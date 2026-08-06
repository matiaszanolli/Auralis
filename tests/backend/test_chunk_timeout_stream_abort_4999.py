"""
Regression tests for chunk-timeout stream abort (#4999)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sibling of #4727's orphaned-thread hazard. stream_chunk_ops.process_chunk_only
wraps `processor.process_chunk_safe(chunk_index)` in `asyncio.wait_for`
(#3852) — on timeout it raises TimeoutError, but the underlying OS thread may
still be running inside `process_chunk_safe`, holding the ChunkedAudioProcessor's
`_processor_lock` (a threading.RLock) for however long the hung DSP call takes.

Before this fix, stream_enhanced_audio's per-chunk error handler treated a
TimeoutError the same as any other chunk failure (#3190's skip-and-continue):
it evicted the cache entry, sent a recoverable error, and `continue`d to the
next chunk on the SAME processor instance. The next chunk's
process_chunk_safe() call would then block trying to acquire the
still-held _processor_lock, itself time out ~CHUNK_PROCESS_TIMEOUT later, and
so on — cascading every remaining chunk into a serial pileup of timeouts
instead of one clean failure.

The fix: a chunk TimeoutError now ends the stream immediately rather than
continuing to reuse the (possibly still-running-in-the-background) processor.
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
            # deadline. Sleeping past the loop's patience is enough to trigger
            # the same TimeoutError stream_chunk_ops.process_chunk_only raises.
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


class TestChunkTimeoutAbortsStream:
    @pytest.mark.asyncio
    async def test_timeout_stops_the_stream_instead_of_continuing(self):
        """A chunk timeout must end the stream — subsequent chunks (which
        would race the still-possibly-running orphaned thread's lock) must
        never be attempted."""
        calls: list[int] = []
        processor = _make_processor(calls, timeout_at=TIMEOUT_AT_CHUNK)
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
            )

        # The look-ahead pipeline may have already kicked off chunk
        # TIMEOUT_AT_CHUNK + 1 concurrently with chunk TIMEOUT_AT_CHUNK's
        # streaming — that's fine (it's a different in-flight task, not a
        # *subsequent* call issued after the timeout was observed). What must
        # never happen is calling process_chunk_safe for anything beyond that.
        assert max(calls) <= TIMEOUT_AT_CHUNK + 1, (
            f"process_chunk_safe was called for chunks past the timeout: {calls}"
        )

    @pytest.mark.asyncio
    async def test_timeout_sends_a_distinct_error_message(self):
        """The client must be told the stream stopped due to a timeout, not
        the generic recoverable per-chunk failure message (#2085)."""
        calls: list[int] = []
        processor = _make_processor(calls, timeout_at=TIMEOUT_AT_CHUNK)
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
            )

        error_msgs = [m for m in sent if m.get("type") == "audio_stream_error"]
        assert error_msgs, "Expected an audio_stream_error message"
        assert "timed out" in error_msgs[0]["data"]["error"].lower()

    @pytest.mark.asyncio
    async def test_stream_end_reports_stopped_not_completed(self):
        """The terminal message must reflect the stream stopped early, not
        that it delivered the full track (#4659)."""
        calls: list[int] = []
        processor = _make_processor(calls, timeout_at=TIMEOUT_AT_CHUNK)
        sent: list[dict] = []
        controller, ws = _wire_controller(processor, sent)

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
            )

        end_msgs = [m for m in sent if m.get("type") == "audio_stream_end"]
        assert end_msgs, "Expected an audio_stream_end message"
        assert end_msgs[0]["data"]["reason"] == "stopped"

    @pytest.mark.asyncio
    async def test_plain_chunk_error_still_uses_skip_and_continue(self):
        """Sibling check: a non-timeout exception must still use #3190's
        recovery path (skip the chunk, keep streaming) — this fix must not
        regress ordinary error recovery."""
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

        with patch("core.stream_enhanced.Path.exists", return_value=True), \
             patch.object(controller, "_check_or_queue_fingerprint",
                          new=AsyncMock(return_value=False)):
            await controller.stream_enhanced_audio(
                track_id=TRACK_ID, preset=PRESET, intensity=INTENSITY, websocket=ws,
            )

        # Chunks after the failed one must still have been attempted.
        assert max(calls) >= TOTAL_CHUNKS - 1, (
            f"non-timeout failures must still skip-and-continue: {calls}"
        )
        end_msgs = [m for m in sent if m.get("type") == "audio_stream_end"]
        assert end_msgs
        # #4790: a stream that skip-and-continues past a failed chunk is not
        # "completed" — only TOTAL_CHUNKS - 1 chunks were actually delivered
        # (chunk TIMEOUT_AT_CHUNK failed), so the terminal message must say
        # so and report only what was delivered, not the full track.
        end_data = end_msgs[0]["data"]
        assert end_data["reason"] == "errored"
        assert end_data["total_samples"] == (TOTAL_CHUNKS - 1) * SAMPLE_RATE * int(CHUNK_DURATION)
