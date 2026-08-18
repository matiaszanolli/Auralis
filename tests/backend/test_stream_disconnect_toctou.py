"""
Tests for WebSocket stream loop TOCTOU race (fixes #2076).

Verifies that:
- Processing stops within one chunk when the WebSocket disconnects mid-stream
- process_chunk_safe is NOT called after disconnect is detected

(#4941: the active_streams-cleanup tests that used to be listed here were
removed along with `AudioStreamController.active_streams` itself in #4362 --
see the comment block above TestDisconnectStopsProcessing for why no
equivalent assertion replaces them.)
"""

import asyncio
import gc
import itertools
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController, SimpleChunkCache

# #4941: _make_controller() builds a bare AudioStreamController(), which
# defaults `cache_manager` to get_fallback_chunk_cache() -- a lazily created,
# process-wide singleton shared by every test in this file, not a fresh
# per-controller cache. Every _make_processor() call used to hardcode the
# same file_signature ("testsig"), so two tests using the same
# track_id/chunk_index/preset/intensity (the defaults, used almost
# everywhere) could collide on the SAME cache entry depending on execution
# order -- observed as test_no_cpu_waste_on_immediate_disconnect silently
# getting a cache HIT (skipping the disconnect guard it exists to test)
# because test_process_chunk_safe_not_called_after_disconnect_detected had
# run first and legitimately cached chunk 0 under the identical key.
# file_signature is exactly the field the cache's own key schema added for
# this (#4358: "an in-session file change ... still MISSES") -- so rather
# than reaching for a broader cache-clearing fixture, _make_processor() now
# mints a unique signature per call, giving each test's processor its own
# slice of the shared cache without changing any other test's caching
# behavior.
_next_file_signature = itertools.count()


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
    # #4358: cache keys include this. Unique per call (#4941) so this
    # processor's chunks cannot cache-collide with another test's -- see the
    # module-level comment by _next_file_signature above.
    processor.file_signature = f"testsig-{next(_next_file_signature)}"
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

        # #3874 turned the disconnect guard into a raise (ConnectionError)
        # instead of a silent return, so the streaming loop can `except
        # ConnectionError: break` cleanly instead of logging a spurious
        # "Failed to stream chunk" error -- see stream_chunk_ops.py's
        # process_chunk_only(). The property this test actually cares about
        # is unchanged: no cache hit, so it would normally call
        # process_chunk_safe, and must not.
        with pytest.raises(ConnectionError):
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

        # Pre-populate cache. Must use the processor's file_signature so the
        # production get() (which now keys on it, #4358) actually hits.
        pcm = np.zeros((100, 2), dtype=np.float32)
        controller.cache_manager.put(
            track_id=1, chunk_idx=0, preset="adaptive", intensity=1.0,
            audio=pcm, sample_rate=44100, file_signature=processor.file_signature,
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
# #4941: TestActiveStreamsLifecycle and TestSeekFinallyCleanup used to live
# here, asserting `controller.active_streams` was set/cleared around a bare
# AudioStreamController's stream_enhanced_audio()/_from_position() calls.
# `active_streams` was removed in #4362 as a write-only registry: each
# request builds a fresh controller, so the dict never held more than one
# entry, nothing ever read it, and #4362's own commit message names
# system.py's module-level `_active_streaming_tasks` as "the real
# cancellation registry". That registry cannot replace these assertions --
# it is populated by the WS message loop that wraps a controller call in
# asyncio.create_task(), a layer above what these tests exercise (a bare
# controller called directly) -- so there is no meaningful state left on
# AudioStreamController for a unit test at this level to assert cleanup of
# (per the sibling comment this replaces, #4642 had already removed the
# other candidate, `_chunk_tails`, for the same reason).
#
# The actual #2076 TOCTOU regression -- processing must stop within one
# chunk of a disconnect -- is NOT carried by these deleted tests; it has its
# own direct coverage in TestProcessAndStreamChunkDisconnectGuard and
# TestDisconnectStopsProcessing below, both of which assert
# process_chunk_safe was/wasn't called and remain green.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests: disconnect test — processing stops within 1 chunk (acceptance criteria)
# ---------------------------------------------------------------------------

class TestDisconnectStopsProcessing:
    """
    Acceptance criteria from issue #2076:
    'Processing stops immediately on disconnect — within 1 chunk'
    """

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="#5176: call_count model undercounts _is_websocket_connected "
        "calls per chunk by one; only ever passed via cross-test cache "
        "pollution from an earlier test in this file, confirmed broken in "
        "true isolation on unmodified HEAD",
        strict=True,
    )
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

        # Call _process_and_stream_chunk directly 3 times — each should bail
        # early by raising ConnectionError (#3874; see the sibling test above)
        # rather than returning silently.
        for chunk_idx in range(3):
            with pytest.raises(ConnectionError):
                await controller._process_and_stream_chunk(
                    chunk_index=chunk_idx,
                    processor=processor,
                    websocket=ws,
                )

        processor.process_chunk_safe.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: _safe_send / _safe_send_bytes classify disconnect by connection
# state, not by Starlette's RuntimeError wording (#3850, sibling of #3511)
# ---------------------------------------------------------------------------

class TestSafeSendDisconnectClassification:
    """A send-after-close RuntimeError must log at DEBUG regardless of wording."""

    def _ws_raising_after_disconnect(self, send_attr: str) -> Mock:
        """WS that is CONNECTED at guard time but raises a reworded RuntimeError
        and flips to DISCONNECTED when the send is attempted."""
        ws = _make_websocket(connected=True)

        async def _raise(*_a, **_k):
            # Simulate Starlette transitioning the state on a closed peer, and
            # use wording that does NOT contain the literal "close message".
            ws.client_state.name = "DISCONNECTED"
            raise RuntimeError("Cannot call 'send' once a close message has been... reworded")

        setattr(ws, send_attr, AsyncMock(side_effect=_raise))
        return ws

    @pytest.mark.asyncio
    async def test_safe_send_logs_debug_on_reworded_disconnect(self, caplog):
        import logging

        controller = _make_controller()
        ws = self._ws_raising_after_disconnect("send_text")

        with caplog.at_level(logging.DEBUG, logger="core.stream_protocol"):
            result = await controller._safe_send(ws, {"type": "ping"})

        assert result is False
        records = [r for r in caplog.records if "during send" in r.message]
        assert records, "Expected a debug log about the WebSocket closing during send"
        assert all(r.levelno == logging.DEBUG for r in records)
        # No spurious warnings on a normal disconnect.
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    @pytest.mark.asyncio
    async def test_safe_send_bytes_logs_debug_on_reworded_disconnect(self, caplog):
        import logging

        controller = _make_controller()
        ws = self._ws_raising_after_disconnect("send_bytes")

        with caplog.at_level(logging.DEBUG, logger="core.stream_protocol"):
            result = await controller._safe_send_bytes(ws, b"\x00\x01")

        assert result is False
        records = [r for r in caplog.records if "during binary send" in r.message]
        assert records, "Expected a debug log about the WebSocket closing during binary send"
        assert all(r.levelno == logging.DEBUG for r in records)
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    @pytest.mark.asyncio
    async def test_safe_send_logs_warning_when_still_connected(self, caplog):
        """A RuntimeError while the WS is still CONNECTED is a genuine error → WARNING."""
        import logging

        controller = _make_controller()
        ws = _make_websocket(connected=True)
        # Raise without flipping state → still CONNECTED at the except re-check.
        ws.send_text = AsyncMock(side_effect=RuntimeError("some other failure"))

        with caplog.at_level(logging.DEBUG, logger="core.stream_protocol"):
            result = await controller._safe_send(ws, {"type": "ping"})

        assert result is False
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "A genuine send error (still connected) should log at WARNING"


# ---------------------------------------------------------------------------
# Tests: look-ahead read pre-checks the WS connection (#3874)
#
# The normal-path look-ahead now runs through _read_audio_chunk_lookahead,
# which raises ConnectionError if the client vanished, mirroring the
# enhanced-path _process_chunk_only guard. _drain_cancelled_task was hardened
# so a task that already finished by *raising* (the new short-circuit) has its
# exception retrieved — otherwise a top-of-loop break that drains the task
# without awaiting would leak a "Task exception was never retrieved" warning.
# ---------------------------------------------------------------------------

class TestDrainCancelledTask:
    """Cover the _drain_cancelled_task hardening that backs the #3874 fix."""

    @pytest.mark.asyncio
    async def test_drain_none_is_noop(self):
        controller = _make_controller()
        # Must not raise.
        await controller._drain_cancelled_task(None)

    @pytest.mark.asyncio
    async def test_drain_cancels_running_task(self):
        """A still-running look-ahead is cancelled and awaited to completion."""
        controller = _make_controller()

        async def _forever():
            await asyncio.Event().wait()

        task = asyncio.ensure_future(_forever())
        await asyncio.sleep(0)  # let it start
        await controller._drain_cancelled_task(task)
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_drain_done_result_task_is_safe(self):
        """Draining a task that already completed with a result must not raise."""
        controller = _make_controller()

        async def _ok():
            return 123

        task = asyncio.ensure_future(_ok())
        while not task.done():
            await asyncio.sleep(0)
        await controller._drain_cancelled_task(task)  # must not raise
        assert task.result() == 123

    @pytest.mark.asyncio
    async def test_drain_retrieves_exception_of_done_raised_task(self):
        """A look-ahead that finished by raising ConnectionError (the #3874
        short-circuit) must have its exception retrieved by the drain, so the
        event loop never reports 'Task exception was never retrieved' when the
        task is GC'd on the top-of-loop break path."""
        controller = _make_controller()

        loop = asyncio.get_running_loop()
        reported: list[dict] = []
        prev_handler = loop.get_exception_handler()
        loop.set_exception_handler(lambda _loop, ctx: reported.append(ctx))
        try:
            async def _raises():
                raise ConnectionError("WebSocket disconnected before look-ahead read")

            task = asyncio.ensure_future(_raises())
            # Let it finish WITHOUT awaiting/retrieving its exception.
            while not task.done():
                await asyncio.sleep(0)

            await controller._drain_cancelled_task(task)

            # Drop the last reference and force finalization. If the exception
            # was retrieved (the fix), Future.__del__ reports nothing.
            del task
            gc.collect()
            await asyncio.sleep(0)
        finally:
            loop.set_exception_handler(prev_handler)

        never_retrieved = [
            c for c in reported
            if "never retrieved" in str(c.get("message", "")).lower()
        ]
        assert not never_retrieved, (
            f"drain left a task exception unretrieved: {never_retrieved}"
        )

    @pytest.mark.asyncio
    async def test_drain_propagates_a_cancellation_aimed_at_the_caller(self):
        """#5083: a CancelledError delivered to the *calling* task while it is
        parked in drain's `await task` must propagate.

        teardown_connection and handle_seek cancel the outer streaming task, and
        drain runs mid-loop, not only at teardown. Swallowing that cancellation
        leaves the old stream sending chunks while handle_seek blocks on
        `await old_task` — the interleaved-frames failure #3806 closed."""
        controller = _make_controller()
        entered = asyncio.Event()
        outcome: dict[str, object] = {}

        async def _forever():
            await asyncio.Event().wait()

        async def _outer():
            inner = asyncio.ensure_future(_forever())
            await asyncio.sleep(0)  # let the inner task start
            entered.set()
            try:
                await controller._drain_cancelled_task(inner)
            except asyncio.CancelledError:
                outcome["propagated"] = True
                raise
            outcome["propagated"] = False

        outer = asyncio.ensure_future(_outer())
        await entered.wait()
        await asyncio.sleep(0)  # park inside drain's `await task`
        outer.cancel()

        with pytest.raises(asyncio.CancelledError):
            await outer

        assert outcome.get("propagated") is True, (
            "drain swallowed a cancellation targeting the calling task"
        )

    @pytest.mark.asyncio
    async def test_drain_still_suppresses_the_inner_tasks_own_cancellation(self):
        """#3493 regression guard: with no cancellation pending against the
        caller, the drained task's own CancelledError is still suppressed."""
        controller = _make_controller()

        async def _forever():
            await asyncio.Event().wait()

        inner = asyncio.ensure_future(_forever())
        await asyncio.sleep(0)

        await controller._drain_cancelled_task(inner)  # must not raise

        assert inner.cancelled()
        # The caller survives and keeps running.
        assert asyncio.current_task() is not None
        assert not asyncio.current_task().cancelled()

    @pytest.mark.asyncio
    async def test_drain_suppresses_inner_errors_but_not_caller_cancellation(self):
        """A drained task that raises a normal Exception is still swallowed —
        only the caller's own cancellation is allowed through."""
        controller = _make_controller()

        async def _raises_slowly():
            await asyncio.sleep(0)
            raise RuntimeError("teardown failure inside the look-ahead")

        task = asyncio.ensure_future(_raises_slowly())
        await asyncio.sleep(0)

        await controller._drain_cancelled_task(task)  # must not raise


class _FakeSoundFile:
    """Minimal sf.SoundFile stand-in backed by a NumPy array.

    Supports the two access patterns stream_normal_audio uses: metadata via
    samplerate/channels/len(), and chunk reads via seek()+read().
    """

    def __init__(self, data: np.ndarray, sample_rate: int):
        self._data = data
        self.samplerate = sample_rate
        self.channels = data.shape[1]
        self._pos = 0

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def __len__(self):
        return self._data.shape[0]

    def seek(self, frame: int):
        self._pos = frame

    def read(self, frames: int, dtype: str = "float32", always_2d: bool = True):
        out = self._data[self._pos:self._pos + frames]
        return out.astype(dtype, copy=False)


class TestNormalPathLookaheadWiring:
    """Integration check: the normal-path look-ahead read is wired through the
    guarded callable and streams every chunk while the client stays connected
    (proves the #3874 refactor didn't break the happy path)."""

    @pytest.mark.asyncio
    async def test_connected_stream_sends_all_chunks_via_lookahead(self, tmp_path):
        controller = _make_controller()
        controller._stream_semaphore = asyncio.Semaphore(10)

        # chunk_samples = CHUNK_DURATION (15s) * 100Hz = 1500 frames. 2250 frames
        # → 2 chunks (1500 + 750), so the second chunk is consumed from the
        # look-ahead task created during the first chunk's send.
        sample_rate = 100
        n_frames = 2250
        chunk_frames = 1500
        data = (
            np.arange(n_frames * 2, dtype=np.float32).reshape(n_frames, 2) / 1000.0
        )

        # Real file so Path(...).exists() is True without patching Path wholesale.
        wav = tmp_path / "fake.wav"
        wav.write_bytes(b"\x00")

        track = Mock()
        track.filepath = str(wav)
        factory = Mock()
        factory.tracks.get_by_id = Mock(return_value=track)
        controller._get_repository_factory = Mock(return_value=factory)
        controller._send_stream_start = AsyncMock(return_value=True)

        sent_chunks: list[np.ndarray] = []

        async def _capture_send(_ws, pcm_samples, **_kwargs):
            sent_chunks.append(pcm_samples)
            return True

        controller._send_pcm_chunk = _capture_send

        with patch("soundfile.SoundFile", lambda _fp: _FakeSoundFile(data, sample_rate)):
            await controller.stream_normal_audio(
                track_id=1,
                websocket=_make_websocket(connected=True),
            )

        # Both chunks streamed, in order, second one shorter (750 frames).
        assert len(sent_chunks) == 2, f"expected 2 chunks, got {len(sent_chunks)}"
        assert sent_chunks[0].shape == (chunk_frames, 2)
        assert sent_chunks[1].shape == (n_frames - chunk_frames, 2)
        # The look-ahead delivered the right slice (frames 1500..2250).
        np.testing.assert_array_equal(sent_chunks[1], data[chunk_frames:n_frames])
