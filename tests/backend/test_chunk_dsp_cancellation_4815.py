"""
Regression tests for cooperative chunk-DSP cancellation (#4815)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Cancelling a streaming task's asyncio coroutine (seek/track-change/
disconnect) does not stop the concurrent.futures.Future already running the
chunk's DSP inside STREAM_EXECUTOR — .cancel() on a RUNNING future is a
no-op, so the thread ran to completion unreferenced, wasting CPU and
holding the shared HybridProcessor's _process_lock (blocking any new stream
reusing the same pooled processor, ProcessorFactory.get_or_create) for no
reason.

Fix: a per-stream threading.Event (StreamState.chunk_cancel_events, keyed by
ws_id) that chunk_streaming.process_chunk checks before starting DSP, set()
by _cancel_prior_task / handle_stop / teardown_connection before they cancel
the task — same pattern ProcessingEngine._cancel_events already uses for
FFmpeg decode.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import threading
from unittest.mock import AsyncMock, Mock

import pytest

# tests/backend/conftest.py puts auralis-web/backend on sys.path.
from core import chunk_streaming
from core.chunk_streaming import ChunkCancelledError
from core.audio_stream_controller import AudioStreamController, ws_id as _ws_id
from ws_handlers.context import StreamState
from ws_handlers.playback_commands import _cancel_prior_task
from ws_handlers.playback_control import handle_stop
from ws_handlers.connection import teardown_connection


def _fresh_state(**overrides) -> StreamState:
    defaults = dict(
        active_tasks={},
        active_tasks_lock=asyncio.Lock(),
        active_track_ids={},
        pause_events={},
        flow_events={},
    )
    defaults.update(overrides)
    return StreamState(**defaults)


def _make_processor(cancel_event: threading.Event | None = None) -> Mock:
    processor = Mock()
    processor.track_id = 1
    processor.total_chunks = 5
    processor.preset = "adaptive"
    processor.intensity = 1.0
    processor.fingerprint = {"dummy": True}
    processor._cancel_event = cancel_event
    processor._lookup_cached_chunk = Mock(return_value=None)
    processor._validate_chunk_index = Mock()
    processor._processor_lock = threading.RLock()
    return processor


def _connected_ws() -> Mock:
    ws = Mock()
    ws.client_state = Mock()
    ws.client_state.name = "CONNECTED"
    return ws


class TestProcessChunkChecksTheCancelEvent:
    """chunk_streaming.process_chunk bails out before DSP when cancelled."""

    def test_raises_and_skips_dsp_when_cancel_event_is_set(self):
        event = threading.Event()
        event.set()
        processor = _make_processor(cancel_event=event)

        with pytest.raises(ChunkCancelledError):
            chunk_streaming.process_chunk(processor, chunk_index=0, locked=False)

        # The whole point: DSP must never start for an abandoned chunk.
        processor._process_chunk_core.assert_not_called()

    def test_proceeds_normally_when_cancel_event_is_not_set(self):
        event = threading.Event()  # not set
        processor = _make_processor(cancel_event=event)
        processor._process_chunk_core = Mock(return_value=Mock())
        processor.sample_rate = 44100
        processor.total_duration = 15.0
        processor._wav_encoder.encode_and_save_from_path = Mock(return_value="/tmp/chunk_0.wav")
        processor._path_cache.store = Mock()
        processor.file_signature = "sig"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "core.chunk_operations.ChunkOperations.extract_chunk_segment",
                lambda **kw: kw["processed_chunk"],
            )
            chunk_streaming.process_chunk(processor, chunk_index=0, locked=False)

        processor._process_chunk_core.assert_called_once()

    def test_proceeds_normally_when_no_cancel_event_is_wired(self):
        """cancel_event=None (the default, e.g. the prefetch path) must be a no-op."""
        processor = _make_processor(cancel_event=None)
        processor._process_chunk_core = Mock(return_value=Mock())
        processor.sample_rate = 44100
        processor.total_duration = 15.0
        processor._wav_encoder.encode_and_save_from_path = Mock(return_value="/tmp/chunk_0.wav")
        processor._path_cache.store = Mock()
        processor.file_signature = "sig"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "core.chunk_operations.ChunkOperations.extract_chunk_segment",
                lambda **kw: kw["processed_chunk"],
            )
            chunk_streaming.process_chunk(processor, chunk_index=0, locked=False)

        processor._process_chunk_core.assert_called_once()


class TestProcessChunkOnlyTranslatesTheAbort:
    """stream_chunk_ops.process_chunk_only must not report a cancelled chunk
    as a processing failure — it re-raises as ConnectionError, which the
    streaming loops already treat as a clean exit (#2076's existing
    ConnectionError branch)."""

    @pytest.mark.asyncio
    async def test_chunk_cancelled_error_becomes_connection_error(self):
        controller = AudioStreamController()
        processor = _make_processor(cancel_event=threading.Event())
        processor.process_chunk_safe = AsyncMock(
            side_effect=ChunkCancelledError("abandoned")
        )

        with pytest.raises(ConnectionError):
            await controller._process_chunk_only(0, processor, _connected_ws())


class TestCancelSignalsSetBeforeTaskCancel:
    """_cancel_prior_task / handle_stop / teardown_connection must set() the
    chunk cancel event so an in-flight executor thread can observe it —
    covers all three scenarios named in #4815 (seek/track-change,
    explicit stop, disconnect)."""

    @pytest.mark.asyncio
    async def test_cancel_prior_task_sets_the_event(self):
        ws_id = "ws-1"
        cancel_event = threading.Event()
        state = _fresh_state(chunk_cancel_events={ws_id: cancel_event})

        async def _never_ending():
            await asyncio.sleep(100)

        task = asyncio.ensure_future(_never_ending())
        state.active_tasks[ws_id] = task

        assert not cancel_event.is_set()
        await _cancel_prior_task(ws_id, state)
        assert cancel_event.is_set()

    @pytest.mark.asyncio
    async def test_handle_stop_sets_the_event(self):
        websocket = AsyncMock()
        websocket.client_state = Mock()
        websocket.client_state.name = "CONNECTED"
        ws_id = _ws_id(websocket)
        cancel_event = threading.Event()
        state = _fresh_state(chunk_cancel_events={ws_id: cancel_event})

        async def _never_ending():
            await asyncio.sleep(100)

        state.active_tasks[ws_id] = asyncio.ensure_future(_never_ending())

        assert not cancel_event.is_set()
        await handle_stop(websocket, state)
        assert cancel_event.is_set()
        # Matches the other per-ws registries: no dangling entry after stop.
        assert ws_id not in state.chunk_cancel_events

    @pytest.mark.asyncio
    async def test_teardown_connection_sets_the_event(self):
        websocket = AsyncMock()
        websocket.client_state = Mock()
        websocket.client_state.name = "CONNECTED"
        ws_id = _ws_id(websocket)
        cancel_event = threading.Event()
        state = _fresh_state(chunk_cancel_events={ws_id: cancel_event})

        async def _never_ending():
            await asyncio.sleep(100)

        state.active_tasks[ws_id] = asyncio.ensure_future(_never_ending())

        heartbeat_task = asyncio.ensure_future(asyncio.sleep(100))
        manager = Mock()
        manager.disconnect = Mock()
        rate_limiter = Mock()
        rate_limiter.cleanup = Mock()

        assert not cancel_event.is_set()
        await teardown_connection(
            websocket,
            heartbeat_task,
            state,
            get_processing_engine=lambda: None,
            job_subscriptions={},
            manager=manager,
            rate_limiter=rate_limiter,
        )
        assert cancel_event.is_set()
        assert ws_id not in state.chunk_cancel_events
