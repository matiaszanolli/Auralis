"""
Tests for chunk emission on the WebSocket audio stream
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This file used to test `_apply_boundary_crossfade` and the `_chunk_tails`
storage that fed it. Both are gone (#4642).

History, so the removal is not re-litigated: #2183 added a server-side
boundary crossfade; #3186 removed the tail *mix* to avoid pre-echo, leaving a
bare 200 ms fade-in that produced an audible periodic volume dip; #3514 made
`apply_boundary_crossfade` a no-op because `ChunkOperations` already renders
each chunk with 5 s of context and trims it to a non-overlapping
`CHUNK_INTERVAL` segment — DSP state is continuous across the boundary and
adjacent chunks share no samples, so there is nothing to blend. #4642 deleted
the no-op, its tail storage and lock, and the `crossfade_samples` wire field
(always 0, and the client's `PCMStreamBuffer.applyCrossfade` was therefore
unreachable).

What is asserted here now:
- A processed chunk reaches the wire byte-identical — no blending, no fade.
- The `audio_chunk_meta` payload no longer carries `crossfade_samples`.
- `_send_pcm_chunk`'s bounded-queue backpressure (#2122) still holds.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock
import numpy as np
import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from core.audio_stream_controller import AudioStreamController


def _capturing_websocket() -> tuple[AsyncMock, list[dict], list[bytes]]:
    """A connected mock websocket that records JSON messages and binary frames."""
    metas: list[dict] = []
    binaries: list[bytes] = []

    async def capture_text(text):
        metas.append(json.loads(text))

    async def capture_bytes(data):
        binaries.append(bytes(data))

    ws = AsyncMock()
    ws.client_state.name = "CONNECTED"
    ws.send_text = AsyncMock(side_effect=capture_text)
    ws.send_bytes = AsyncMock(side_effect=capture_bytes)
    return ws, metas, binaries


class TestChunkEmittedVerbatim:
    """Chunks reach the wire unmodified — the cleanup changed no audio."""

    @pytest.mark.asyncio
    async def test_pcm_is_bit_identical_on_the_wire(self):
        controller = AudioStreamController()
        controller._stream_type = "enhanced"

        original = np.random.randn(44100 * 2, 2).astype(np.float32)
        ws, _metas, binaries = _capturing_websocket()

        await controller._send_pcm_chunk(
            ws, pcm_samples=original.copy(), chunk_index=0, total_chunks=3
        )

        received = np.frombuffer(b"".join(binaries), dtype="<f4")
        np.testing.assert_array_equal(received, original.reshape(-1))

    @pytest.mark.asyncio
    async def test_later_chunks_are_not_blended_with_earlier_ones(self):
        """
        The historical bug: chunk N>0 got its first 200 ms attenuated. Streaming
        several constant-amplitude chunks in sequence would expose any residual
        fade — every sample must survive untouched.
        """
        controller = AudioStreamController()
        controller._stream_type = "enhanced"

        for chunk_index in range(3):
            amplitude = np.float32(0.5 + 0.1 * chunk_index)
            chunk = np.full((44100, 2), amplitude, dtype=np.float32)
            ws, _metas, binaries = _capturing_websocket()

            await controller._send_pcm_chunk(
                ws, pcm_samples=chunk, chunk_index=chunk_index, total_chunks=3
            )

            received = np.frombuffer(b"".join(binaries), dtype="<f4")
            assert np.all(received == amplitude), (
                f"chunk {chunk_index} was modified in flight"
            )

    @pytest.mark.asyncio
    async def test_stream_processed_chunk_does_not_copy_or_fade(self):
        """The whole stream_processed_chunk path is a pass-through."""
        controller = AudioStreamController()
        controller._stream_type = "enhanced"

        original = np.random.randn(44100, 2).astype(np.float32)

        processor = Mock()
        processor.track_id = 123
        processor.total_chunks = 3
        processor.sample_rate = 44100
        processor.preset = "balanced"
        processor.intensity = 0.5

        ws, _metas, binaries = _capturing_websocket()

        await controller._stream_processed_chunk(original.copy(), 1, processor, ws)

        received = np.frombuffer(b"".join(binaries), dtype="<f4")
        np.testing.assert_array_equal(received, original.reshape(-1))


class TestWireContract:
    """`crossfade_samples` is gone from the protocol (#4642)."""

    @pytest.mark.asyncio
    async def test_meta_payload_has_no_crossfade_field(self):
        controller = AudioStreamController()
        controller._stream_type = "enhanced"

        ws, metas, _binaries = _capturing_websocket()
        await controller._send_pcm_chunk(
            ws,
            pcm_samples=np.zeros((1024, 2), dtype=np.float32),
            chunk_index=0,
            total_chunks=1,
        )

        chunk_metas = [m for m in metas if m.get("type") == "audio_chunk_meta"]
        assert chunk_metas, "no audio_chunk_meta frames were sent"
        for meta in chunk_metas:
            assert "crossfade_samples" not in meta["data"]
            # The fields consumers actually read must still be present.
            assert {"seq", "chunk_index", "frame_index", "sample_count"} <= meta["data"].keys()

    def test_controller_exposes_no_crossfade_api(self):
        """
        Guards against the no-op or its tail storage being reintroduced without
        a consumer — that is the state #4642 cleaned up.
        """
        controller = AudioStreamController()
        assert not hasattr(controller, "_apply_boundary_crossfade")
        assert not hasattr(controller, "_chunk_tails")
        assert not hasattr(controller, "_chunk_tails_lock")
        assert not hasattr(controller, "_drop_chunk_tail")


class TestSendPcmChunkBackpressure:
    """Tests for bounded-queue backpressure in _send_pcm_chunk (issue #2122)."""

    @pytest.mark.asyncio
    async def test_all_frames_delivered_to_fast_client(self):
        """All frames reach a normally-responding client (no regression)."""
        controller = AudioStreamController()
        controller._stream_type = "enhanced"

        # 2 seconds of stereo audio at 44100 Hz → a few frames
        samples = np.random.randn(44100 * 2, 2).astype(np.float32)

        received_frames: list[int] = []

        async def capture(text):
            msg = json.loads(text)
            if msg["type"] == "audio_chunk_meta":
                received_frames.append(msg["data"]["frame_index"])

        mock_ws = AsyncMock()
        mock_ws.client_state.name = "CONNECTED"
        mock_ws.send_text = AsyncMock(side_effect=capture)

        await controller._send_pcm_chunk(
            mock_ws,
            pcm_samples=samples,
            chunk_index=0,
            total_chunks=1,
        )

        # Every frame index 0..N-1 must be received exactly once
        assert received_frames == sorted(received_frames)
        assert received_frames == list(range(len(received_frames)))
        assert len(received_frames) > 0

    @pytest.mark.asyncio
    async def test_producer_stops_early_on_client_disconnect(self):
        """When the client disconnects mid-stream, the producer stops encoding further frames."""
        from core.audio_stream_controller import _SEND_QUEUE_MAXSIZE

        controller = AudioStreamController()
        controller._stream_type = "enhanced"

        # Large chunk → many frames (well above _SEND_QUEUE_MAXSIZE)
        samples = np.random.randn(44100 * 30, 2).astype(np.float32)

        sent_frames: list[int] = []
        disconnect_after = 3  # simulate disconnect after this many frames

        async def slow_disconnecting_send(text):
            msg = json.loads(text)
            if msg["type"] == "audio_chunk_meta":
                sent_frames.append(msg["data"]["frame_index"])

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock(side_effect=slow_disconnecting_send)

        def patched_is_connected(ws):
            # Disconnect after disconnect_after successful sends
            return len(sent_frames) < disconnect_after

        controller._is_websocket_connected = patched_is_connected

        await controller._send_pcm_chunk(
            mock_ws,
            pcm_samples=samples,
            chunk_index=0,
            total_chunks=1,
        )

        # Should have stopped well before all frames — allow a few extra due
        # to frames already queued in the bounded queue at disconnect time
        max_expected = disconnect_after + _SEND_QUEUE_MAXSIZE + 1
        assert len(sent_frames) <= max_expected, (
            f"Expected at most {max_expected} frames after disconnect, got {len(sent_frames)}"
        )

    @pytest.mark.asyncio
    async def test_slow_client_bounded_concurrent_frames(self):
        """Queue maxsize is respected: producer blocks until consumer drains a slot."""
        import asyncio

        controller = AudioStreamController()
        controller._stream_type = "enhanced"

        # Use a medium-size chunk (several frames)
        samples = np.random.randn(44100 * 5, 2).astype(np.float32)

        max_concurrent: list[int] = [0]
        in_flight: list[int] = [0]

        async def slow_send(text):
            msg = json.loads(text)
            if msg["type"] != "audio_chunk_meta":
                return
            in_flight[0] += 1
            max_concurrent[0] = max(max_concurrent[0], in_flight[0])
            await asyncio.sleep(0.01)  # simulate a slow client
            in_flight[0] -= 1

        mock_ws = AsyncMock()
        mock_ws.client_state.name = "CONNECTED"
        mock_ws.send_text = AsyncMock(side_effect=slow_send)

        await controller._send_pcm_chunk(
            mock_ws,
            pcm_samples=samples,
            chunk_index=0,
            total_chunks=1,
        )

        # The consumer is single-threaded (one send at a time), so in-flight is always 1.
        # The bounded queue prevents the producer from racing too far ahead.
        assert max_concurrent[0] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
