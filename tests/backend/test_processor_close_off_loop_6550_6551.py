"""ChunkedAudioProcessor.close() runs off the event loop, and stop() waits for a render (#6550, #6551).

close() releases the processor's converted temp WAV, and a release that pushes the idle
conversions over the cap rmtrees a full-track WAV: run on the event loop (the proactive buffer's
finally, the streamlined worker's evictions) it stalled every WebSocket. And the worker's stop()
closed every cached processor directly, even one a render was still running in, which is what
close_dropped_processor's lease check exists to prevent (#5064).
"""

import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import proactive_buffer  # noqa: E402
from core.processor_close import wait_for_pending_closes  # noqa: E402
from core.streamlined_processor_disposal import close_dropped_processor, leased  # noqa: E402
from core.streamlined_worker import StreamlinedCacheWorker  # noqa: E402

pytestmark = pytest.mark.asyncio


class _RecordingProcessor:
    def __init__(self):
        self.closed_on: list[int] = []

    def close(self):
        self.closed_on.append(threading.get_ident())


async def test_a_dropped_processor_closes_off_the_loop():
    processor = _RecordingProcessor()

    close_dropped_processor((1, "adaptive", 1.0, "sig"), processor)
    await wait_for_pending_closes()

    assert len(processor.closed_on) == 1
    assert processor.closed_on[0] != threading.get_ident()


async def test_the_proactive_buffer_closes_its_processor_off_the_loop_even_when_cancelled(monkeypatch):
    from core import chunked_processor

    processor = _RecordingProcessor()
    started = asyncio.Event()

    async def hang(*_args, **_kwargs):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(chunked_processor, "ChunkedAudioProcessor", lambda **_kwargs: processor)
    monkeypatch.setattr(proactive_buffer, "_buffer_chunk", hang)

    task = asyncio.create_task(proactive_buffer._buffer_one_preset(
        "adaptive", 1, "/music/a.m4a", 1.0, 2, None, lambda: False,
    ))
    await asyncio.wait_for(started.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(processor.closed_on) == 1, "a cancelled buffering task skipped the close"
    assert processor.closed_on[0] != threading.get_ident()


async def test_stop_defers_the_close_of_a_processor_a_render_still_holds():
    worker = StreamlinedCacheWorker(Mock(current_track_id=None), Mock())
    busy, idle = Mock(), Mock()
    worker._processor_cache[(1, "adaptive", 1.0, "sig")] = busy
    worker._processor_cache[(2, "adaptive", 1.0, "sig")] = idle

    with leased(busy):  # a render in an executor thread
        await worker.stop()
        busy.close.assert_not_called()
        idle.close.assert_called_once()
    await wait_for_pending_closes()

    busy.close.assert_called_once()
    assert len(worker._processor_cache) == 0
