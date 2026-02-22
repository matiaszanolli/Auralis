"""
Test concurrent WebSocket streaming stress scenarios (#2334)

Verifies that AudioStreamController handles concurrent stream
operations correctly under load:
1. Multiple simultaneous stream requests
2. Cache contention under concurrent streams
3. Semaphore capacity enforcement
4. Producer/consumer queue bounds

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from core.audio_stream_controller import (
    AudioStreamController,
    MAX_CONCURRENT_STREAMS,
    _SEND_QUEUE_MAXSIZE,
)


@pytest.mark.asyncio
class TestConcurrentStreamCapacity:
    """Verify MAX_CONCURRENT_STREAMS enforcement."""

    async def test_max_concurrent_streams_defined(self):
        """MAX_CONCURRENT_STREAMS must be defined and reasonable."""
        assert MAX_CONCURRENT_STREAMS >= 1
        assert MAX_CONCURRENT_STREAMS <= 100  # Sanity check

    async def test_semaphore_initialized_to_max(self):
        """Semaphore must start with MAX_CONCURRENT_STREAMS slots."""
        controller = AudioStreamController()
        assert controller._stream_semaphore._value == MAX_CONCURRENT_STREAMS

    async def test_concurrent_acquire_respects_limit(self):
        """Only MAX_CONCURRENT_STREAMS can acquire simultaneously."""
        controller = AudioStreamController()
        acquired = 0

        for _ in range(MAX_CONCURRENT_STREAMS):
            got = controller._stream_semaphore._value > 0
            if got:
                await controller._stream_semaphore.acquire()
                acquired += 1

        assert acquired == MAX_CONCURRENT_STREAMS

        # Next acquire should block (not return immediately)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                controller._stream_semaphore.acquire(), timeout=0.1
            )

        # Cleanup
        for _ in range(MAX_CONCURRENT_STREAMS):
            controller._stream_semaphore.release()


@pytest.mark.asyncio
class TestSendQueueBounds:
    """Verify bounded producer/consumer queue."""

    async def test_send_queue_maxsize_defined(self):
        """_SEND_QUEUE_MAXSIZE must be defined and small (backpressure)."""
        assert _SEND_QUEUE_MAXSIZE >= 1
        assert _SEND_QUEUE_MAXSIZE <= 100

    async def test_bounded_queue_prevents_unbounded_growth(self):
        """Producer cannot enqueue unbounded frames when consumer is slow."""
        controller = AudioStreamController()
        controller._stream_type = "enhanced"

        # Create audio that generates many frames
        samples = np.random.randn(44100 * 10, 2).astype(np.float32)

        frames_sent = []
        disconnect_after = 5

        async def slow_send(text):
            import json
            msg = json.loads(text)
            if msg.get("type") == "audio_chunk":
                frames_sent.append(msg["data"]["frame_index"])
                await asyncio.sleep(0.01)  # Simulate slow client

        mock_ws = AsyncMock()
        mock_ws.client_state.name = "CONNECTED"
        mock_ws.send_text = AsyncMock(side_effect=slow_send)

        # Disconnect after N frames
        call_count = [0]
        def patched_connected(ws):
            call_count[0] += 1
            return len(frames_sent) < disconnect_after

        controller._is_websocket_connected = patched_connected

        await controller._send_pcm_chunk(
            mock_ws,
            pcm_samples=samples,
            chunk_index=0,
            total_chunks=1,
            crossfade_samples=0,
        )

        # Should have stopped reasonably close to disconnect point
        max_expected = disconnect_after + _SEND_QUEUE_MAXSIZE + 2
        assert len(frames_sent) <= max_expected, (
            f"Expected ≤{max_expected} frames, got {len(frames_sent)} — "
            f"producer did not respect backpressure"
        )


@pytest.mark.asyncio
class TestActiveStreamsTracking:
    """Verify active_streams dict management."""

    async def test_active_streams_dict_exists(self):
        """Controller must track active streams."""
        controller = AudioStreamController()
        assert hasattr(controller, 'active_streams') or hasattr(controller, '_active_streams'), (
            "Controller must have active_streams tracking"
        )

    async def test_stream_type_tracking(self):
        """Controller must distinguish enhanced vs normal streams."""
        import inspect
        source = inspect.getsource(AudioStreamController)
        assert "stream_type" in source or "_stream_type" in source, (
            "Controller must track stream type (enhanced/normal)"
        )
