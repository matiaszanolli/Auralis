"""
Tests for WebSocket stream loop TOCTOU race and active_streams cleanup (fixes #2076).

Verifies that:
- Processing stops within one chunk when the WebSocket disconnects mid-stream
- process_chunk_safe is NOT called after disconnect is detected
- active_streams is populated during streaming and empty after it ends
- _chunk_tails is cleaned up on all exit paths (including seek/error)
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from audio_stream_controller import AudioStreamController, SimpleChunkCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_websocket(connected: bool = True) -> Mock:
    """Create a mock WebSocket that reports the given connection state."""
    ws = Mock()
    ws.client_state = Mock()
    ws.client_state.name = "CONNECTED" if connected else "DISCONNECTED"
    ws.send_text = AsyncMock()
    return ws


def _make_controller() -> AudioStreamController:
    """Create a bare AudioStreamController without any dependencies."""
    return AudioStreamController()


def _make_processor(total_chunks: int = 5, sample_rate: int = 44100) -> Mock:
    """Create a minimal mock ChunkedAudioProcessor."""
    processor = Mock()
    processor.track_id = 1
    processor.total_chunks = total_chunks
    processor.sample_rate = sample_rate
    processor.channels = 2
    processor.duration = float(total_chunks * 10)
    processor.chunk_duration = 10.0
    processor.preset = "adaptive"
    processor.intensity = 1.0
    # process_chunk_safe returns (path, pcm_array)
    pcm = np.zeros((total_chunks * sample_rate, 2), dtype=np.float32)
    processor.process_chunk_safe = AsyncMock(
        return_value=(Path("/tmp/chunk.wav"), pcm[:sample_rate])
    )
    return processor


# ---------------------------------------------------------------------------
# Tests: disconnect check in _process_and_stream_chunk
# ---------------------------------------------------------------------------

class TestProcessAndStreamChunkDisconnectGuard:
    """Verify the disconnect guard in _process_and_stream_chunk (fixes #2076)."""

    @pytest.mark.asyncio
    async def test_process_chunk_safe_skipped_when_disconnected(self):
        """
        When WebSocket is disconnected, process_chunk_safe must NOT be called
        even if the outer loop check already passed (TOCTOU fix).
        """
        controller = _make_controller()
        processor = _make_processor(total_chunks=1)
        ws = _make_websocket(connected=False)  # disconnected by the time we enter

        # No cache hit — would normally call process_chunk_safe
        await controller._process_and_stream_chunk(
            chunk_index=0,
            processor=processor,
            websocket=ws,
        )

        processor.process_chunk_safe.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_chunk_safe_called_when_connected(self):
        """
        When WebSocket is connected, process_chunk_safe should be called normally.
        """
        controller = _make_controller()
        processor = _make_processor(total_chunks=1)
        ws = _make_websocket(connected=True)

        with patch.object(
            controller, "_send_pcm_chunk", new_callable=AsyncMock
        ) as mock_send:
            await controller._process_and_stream_chunk(
                chunk_index=0,
                processor=processor,
                websocket=ws,
            )

        processor.process_chunk_safe.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_still_checks_send_when_disconnected(self):
        """
        A cache hit bypasses process_chunk_safe but _send_pcm_chunk handles
        the disconnected case via _safe_send internally (no crash expected).
        """
        controller = _make_controller()
        processor = _make_processor(total_chunks=1)
        ws = _make_websocket(connected=False)

        # Pre-populate cache
        pcm = np.zeros((100, 2), dtype=np.float32)
        controller.cache_manager.put(
            track_id=1, chunk_idx=0, preset="adaptive", intensity=1.0,
            audio=pcm, sample_rate=44100,
        )

        # Should complete without error; _safe_send returns False silently
        with patch.object(
            controller, "_send_pcm_chunk", new_callable=AsyncMock
        ):
            await controller._process_and_stream_chunk(
                chunk_index=0, processor=processor, websocket=ws
            )
        # No exception — pass


# ---------------------------------------------------------------------------
# Tests: active_streams lifecycle
# ---------------------------------------------------------------------------

class TestActiveStreamsLifecycle:
    """Verify active_streams is set during streaming and cleared on exit (fixes #2076)."""

    @pytest.mark.asyncio
    async def test_active_streams_set_during_enhanced_stream(self):
        """active_streams[track_id] is set once a stream actually starts."""
        controller = _make_controller()
        track_id = 42
        recorded_during: list[bool] = []

        original_send_start = controller._send_stream_start

        async def _mock_send_start(*args, **kwargs):
            # Capture whether active_streams is set at the point streaming begins
            recorded_during.append(track_id in controller.active_streams)
            return False  # Pretend WebSocket disconnected → stream exits immediately

        with (
            patch.object(controller, "_get_repository_factory") as mock_factory,
            patch.object(controller, "_send_stream_start", side_effect=_mock_send_start),
            patch.object(controller, "_check_or_queue_fingerprint", new_callable=AsyncMock, return_value=False),
            patch("audio_stream_controller.asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for,
        ):
            # Mock semaphore acquire
            controller._stream_semaphore = asyncio.Semaphore(10)

            # Mock track lookup
            factory = Mock()
            mock_factory.return_value = factory
            track = Mock()
            track.filepath = "/tmp/fake.wav"
            factory.tracks.get_by_id = Mock(return_value=track)

            # Mock Path.exists
            with patch("audio_stream_controller.Path") as mock_path:
                mock_path.return_value.exists.return_value = True

                # Mock processor creation
                processor = _make_processor(total_chunks=3)
                mock_wait_for.return_value = processor

                controller.chunked_processor_class = Mock()
                controller._get_repository_factory = mock_factory

                await controller.stream_enhanced_audio(
                    track_id=track_id,
                    preset="adaptive",
                    intensity=1.0,
                    websocket=_make_websocket(connected=True),
                )

        # active_streams was set by the time _send_stream_start was called
        assert any(recorded_during), "active_streams should be set before streaming begins"

    @pytest.mark.asyncio
    async def test_active_streams_empty_after_enhanced_stream_completes(self):
        """active_streams is empty after stream_enhanced_audio exits normally."""
        controller = _make_controller()
        track_id = 7

        with (
            patch.object(controller, "_get_repository_factory") as mock_factory,
            patch.object(controller, "_send_stream_start", new_callable=AsyncMock, return_value=False),
            patch.object(controller, "_check_or_queue_fingerprint", new_callable=AsyncMock, return_value=False),
            patch("audio_stream_controller.asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for,
        ):
            controller._stream_semaphore = asyncio.Semaphore(10)

            factory = Mock()
            mock_factory.return_value = factory
            track = Mock()
            track.filepath = "/tmp/fake.wav"
            factory.tracks.get_by_id = Mock(return_value=track)

            with patch("audio_stream_controller.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                processor = _make_processor(total_chunks=2)
                mock_wait_for.return_value = processor
                controller.chunked_processor_class = Mock()
                controller._get_repository_factory = mock_factory

                await controller.stream_enhanced_audio(
                    track_id=track_id,
                    preset="adaptive",
                    intensity=1.0,
                    websocket=_make_websocket(connected=True),
                )

        assert track_id not in controller.active_streams

    @pytest.mark.asyncio
    async def test_active_streams_empty_after_enhanced_stream_exception(self):
        """active_streams is cleaned up even when streaming raises an exception."""
        controller = _make_controller()
        track_id = 8

        with (
            patch.object(controller, "_get_repository_factory") as mock_factory,
            patch.object(
                controller, "_send_stream_start", new_callable=AsyncMock,
                side_effect=RuntimeError("simulated send failure")
            ),
            patch.object(controller, "_check_or_queue_fingerprint", new_callable=AsyncMock, return_value=False),
            patch("audio_stream_controller.asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for,
        ):
            controller._stream_semaphore = asyncio.Semaphore(10)

            factory = Mock()
            mock_factory.return_value = factory
            track = Mock()
            track.filepath = "/tmp/fake.wav"
            factory.tracks.get_by_id = Mock(return_value=track)

            with patch("audio_stream_controller.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                processor = _make_processor(total_chunks=2)
                mock_wait_for.return_value = processor
                controller.chunked_processor_class = Mock()
                controller._get_repository_factory = mock_factory

                # Should not raise — exception handled internally
                await controller.stream_enhanced_audio(
                    track_id=track_id,
                    preset="adaptive",
                    intensity=1.0,
                    websocket=_make_websocket(connected=True),
                )

        assert track_id not in controller.active_streams


# ---------------------------------------------------------------------------
# Tests: _chunk_tails cleaned up in seek (stream_enhanced_audio_from_position)
# ---------------------------------------------------------------------------

class TestSeekFinallyCleanup:
    """Verify _chunk_tails is cleaned up in seek's finally (orphaned state fix)."""

    @pytest.mark.asyncio
    async def test_chunk_tails_cleared_after_seek_stream(self):
        """seek stream cleans _chunk_tails in finally even on error exit."""
        controller = _make_controller()
        track_id = 99

        # Plant a tail as if a previous chunk had been processed
        controller._chunk_tails[track_id] = np.zeros((100, 2), dtype=np.float32)

        with (
            patch.object(controller, "_get_repository_factory") as mock_factory,
            patch.object(
                controller, "_send_stream_start_with_seek", new_callable=AsyncMock,
                return_value=False  # immediate disconnect
            ),
            patch("audio_stream_controller.asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for,
        ):
            controller._stream_semaphore = asyncio.Semaphore(10)

            factory = Mock()
            mock_factory.return_value = factory
            track = Mock()
            track.filepath = "/tmp/fake.wav"
            factory.tracks.get_by_id = Mock(return_value=track)

            with patch("audio_stream_controller.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                processor = _make_processor(total_chunks=3)
                mock_wait_for.return_value = processor
                controller.chunked_processor_class = Mock()
                controller._get_repository_factory = mock_factory

                await controller.stream_enhanced_audio_from_position(
                    track_id=track_id,
                    preset="adaptive",
                    intensity=1.0,
                    websocket=_make_websocket(connected=True),
                    start_position=0.0,
                )

        assert track_id not in controller._chunk_tails
        assert track_id not in controller.active_streams

    @pytest.mark.asyncio
    async def test_chunk_tails_cleared_after_seek_exception(self):
        """_chunk_tails is still cleaned when seek stream raises an exception."""
        controller = _make_controller()
        track_id = 100

        controller._chunk_tails[track_id] = np.zeros((100, 2), dtype=np.float32)

        with (
            patch.object(controller, "_get_repository_factory") as mock_factory,
            patch.object(
                controller, "_send_stream_start_with_seek", new_callable=AsyncMock,
                side_effect=RuntimeError("boom")
            ),
            patch("audio_stream_controller.asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for,
        ):
            controller._stream_semaphore = asyncio.Semaphore(10)

            factory = Mock()
            mock_factory.return_value = factory
            track = Mock()
            track.filepath = "/tmp/fake.wav"
            factory.tracks.get_by_id = Mock(return_value=track)

            with patch("audio_stream_controller.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                processor = _make_processor(total_chunks=3)
                mock_wait_for.return_value = processor
                controller.chunked_processor_class = Mock()
                controller._get_repository_factory = mock_factory

                await controller.stream_enhanced_audio_from_position(
                    track_id=track_id,
                    preset="adaptive",
                    intensity=1.0,
                    websocket=_make_websocket(connected=True),
                    start_position=0.0,
                )

        assert track_id not in controller._chunk_tails
        assert track_id not in controller.active_streams


# ---------------------------------------------------------------------------
# Tests: disconnect test — processing stops within 1 chunk (acceptance criteria)
# ---------------------------------------------------------------------------

class TestDisconnectStopsProcessing:
    """
    Acceptance criteria from issue #2076:
    'Processing stops immediately on disconnect — within 1 chunk'
    """

    @pytest.mark.asyncio
    async def test_process_chunk_safe_not_called_after_disconnect_detected(self):
        """
        After disconnect is detected inside _process_and_stream_chunk,
        further calls do not invoke process_chunk_safe.

        Simulates the TOCTOU window: outer loop passed, but WebSocket
        dropped before the expensive DSP work.
        """
        controller = _make_controller()
        num_chunks = 4
        processor = _make_processor(total_chunks=num_chunks)

        call_count = 0

        def _disconnects_on_second_inner_call(_ws=None):
            """
            Returns True (connected) for the outer loop checks and the FIRST
            inner check, then False on subsequent inner checks.

            This simulates: outer loop OK, first chunk OK, disconnect between
            chunk 0 and chunk 1 such that the inner guard catches it.
            """
            nonlocal call_count
            call_count += 1
            # First 3 calls: connected (outer loop × 1, inner guard × 1, send check × 1)
            # After that: disconnected
            return call_count <= 3

        controller._is_websocket_connected = _disconnects_on_second_inner_call

        send_pcm_calls = 0

        async def _count_sends(*args, **kwargs):
            nonlocal send_pcm_calls
            send_pcm_calls += 1

        controller._send_pcm_chunk = _count_sends

        for chunk_idx in range(num_chunks):
            if not controller._is_websocket_connected(None):
                break
            await controller._process_and_stream_chunk(
                chunk_index=chunk_idx,
                processor=processor,
                websocket=Mock(),
            )

        # process_chunk_safe must not have been called for ALL 4 chunks;
        # at most chunk 0 was processed before disconnect
        assert processor.process_chunk_safe.call_count <= 1, (
            f"process_chunk_safe was called {processor.process_chunk_safe.call_count} times; "
            "expected at most 1 (the chunk in flight when disconnect happened)"
        )

    @pytest.mark.asyncio
    async def test_no_cpu_waste_on_immediate_disconnect(self):
        """
        If the WebSocket is already disconnected when _process_and_stream_chunk
        is called with a cache miss, process_chunk_safe is never invoked.
        """
        controller = _make_controller()
        processor = _make_processor(total_chunks=10)
        ws = _make_websocket(connected=False)

        # Call _process_and_stream_chunk directly 3 times — each should bail early
        for chunk_idx in range(3):
            await controller._process_and_stream_chunk(
                chunk_index=chunk_idx,
                processor=processor,
                websocket=ws,
            )

        processor.process_chunk_safe.assert_not_called()
