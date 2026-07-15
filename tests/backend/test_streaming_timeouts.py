"""
Test streaming timeout scenarios (#2333)

Verifies that AudioStreamController properly handles:
1. Semaphore timeout when MAX_CONCURRENT_STREAMS is exceeded
2. Processor initialization timeout (30s threshold)
3. Error message delivery to WebSocket on timeout
4. Semaphore cleanup after timeout

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from core.audio_stream_controller import AudioStreamController, MAX_CONCURRENT_STREAMS


@pytest.mark.asyncio
class TestSemaphoreTimeout:
    """Test behavior when MAX_CONCURRENT_STREAMS is exceeded."""

    async def test_rejects_when_semaphore_full(self):
        """Client receives error when all stream slots are occupied."""
        controller = AudioStreamController()
        # Both must be truthy to pass the top-of-function guards and reach the
        # semaphore acquire (the impl now lives in core.stream_enhanced).
        controller.chunked_processor_class = MagicMock()
        controller._get_repository_factory = MagicMock()
        # Fresh semaphore bound to THIS test's event loop (the default is a
        # module-level global bound to import-time's loop → cross-loop errors).
        controller._stream_semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)

        # Exhaust all semaphore slots
        for _ in range(MAX_CONCURRENT_STREAMS):
            await controller._stream_semaphore.acquire()

        mock_ws = AsyncMock()
        mock_ws.client_state.name = "CONNECTED"

        # Attempt to stream — should timeout on semaphore
        await controller.stream_enhanced_audio(
            websocket=mock_ws,
            track_id=1,
            preset="balanced",
            intensity=0.5,
        )

        # Verify error was sent to client
        calls = [c for c in mock_ws.send_text.call_args_list]
        error_sent = any("busy" in str(c).lower() or "too many" in str(c).lower() for c in calls)
        assert error_sent, "Client must receive 'too many streams' error"

        # Release slots for cleanup
        for _ in range(MAX_CONCURRENT_STREAMS):
            controller._stream_semaphore.release()

    async def test_semaphore_value_after_timeout(self):
        """Semaphore must not leak after timeout rejection."""
        controller = AudioStreamController()
        controller.chunked_processor_class = MagicMock()
        controller._get_repository_factory = MagicMock()
        # Fresh semaphore bound to THIS test's event loop (see sibling test).
        controller._stream_semaphore = asyncio.Semaphore(MAX_CONCURRENT_STREAMS)
        initial_value = controller._stream_semaphore._value

        # Exhaust all slots
        for _ in range(MAX_CONCURRENT_STREAMS):
            await controller._stream_semaphore.acquire()

        mock_ws = AsyncMock()
        mock_ws.client_state.name = "CONNECTED"

        await controller.stream_enhanced_audio(
            websocket=mock_ws,
            track_id=1,
            preset="balanced",
            intensity=0.5,
        )

        # Release all slots
        for _ in range(MAX_CONCURRENT_STREAMS):
            controller._stream_semaphore.release()

        # Semaphore should be back to initial value
        assert controller._stream_semaphore._value == initial_value


@pytest.mark.asyncio
class TestProcessorInitTimeout:
    """Test 30-second processor initialization timeout."""

    async def test_timeout_error_message_sent(self):
        """Client must receive timeout error when processor init takes >30s."""
        controller = AudioStreamController()

        # Mock track lookup to succeed
        mock_track = MagicMock()
        mock_track.filepath = "/fake/track.wav"

        mock_factory = MagicMock()
        mock_factory.tracks.get_by_id.return_value = mock_track
        controller._get_repository_factory = lambda: mock_factory

        # Mock processor class to hang forever
        async def hang_forever(*args, **kwargs):
            await asyncio.sleep(100)

        controller.chunked_processor_class = MagicMock()

        mock_ws = AsyncMock()
        mock_ws.client_state.name = "CONNECTED"

        # Patch asyncio.wait_for to simulate timeout
        original_wait_for = asyncio.wait_for

        async def mock_wait_for(coro, *, timeout):
            if timeout == 30.0:
                # Cancel the coroutine
                coro.close() if hasattr(coro, 'close') else None
                raise TimeoutError()
            return await original_wait_for(coro, timeout=timeout)

        with patch("asyncio.wait_for", side_effect=mock_wait_for), \
             patch.object(Path, "exists", return_value=True):
            await controller.stream_enhanced_audio(
                websocket=mock_ws,
                track_id=1,
                preset="balanced",
                intensity=0.5,
            )

        # Verify timeout error was sent
        calls = [str(c) for c in mock_ws.send_text.call_args_list]
        timeout_sent = any("timed out" in c.lower() for c in calls)
        assert timeout_sent, "Client must receive 'initialization timed out' error"


@pytest.mark.asyncio
class TestSemaphoreCleanup:
    """Ensure the semaphore is released exactly once, in a finally block.

    The controller methods are thin wrappers; the real implementations (and the
    release-guaranteeing finally) live in the core.stream_* modules. These tests
    inspect those module functions directly and assert the single-release-in-
    finally invariant that #4329 depends on.
    """

    def _assert_single_finally_release(self, func):
        import inspect
        source = inspect.getsource(func)
        # Exactly one release — no manual pre-finally release() can be skipped
        # by an early return or a BaseException (#4329).
        assert source.count("_stream_semaphore.release()") == 1, (
            f"{func.__name__} must release the semaphore exactly once "
            f"(found {source.count('_stream_semaphore.release()')})"
        )
        # And that single release must sit inside a finally block.
        finally_idx = source.rfind("finally:")
        release_idx = source.rfind("_stream_semaphore.release()")
        assert finally_idx != -1 and release_idx > finally_idx, (
            f"{func.__name__} must release the semaphore in a finally block"
        )

    async def test_source_enhanced_has_finally_release(self):
        from core import stream_enhanced
        self._assert_single_finally_release(stream_enhanced.stream_enhanced_audio)

    async def test_source_seek_has_finally_release(self):
        from core import stream_seek
        self._assert_single_finally_release(
            stream_seek.stream_enhanced_audio_from_position
        )

    async def test_source_normal_has_finally_release(self):
        from core import stream_normal
        self._assert_single_finally_release(stream_normal.stream_normal_audio)
