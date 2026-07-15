"""Regression test for the stream-semaphore permit leak on cancellation (#4329).

All three stream entry points acquire the global stream semaphore permit BEFORE
the track lookup. The lookup awaits `asyncio.to_thread(factory.tracks.get_by_id,
...)`; if the task is cancelled while suspended there, `asyncio.CancelledError`
(a BaseException) is NOT caught by the lookup's `except Exception`. Before the
fix the permit was acquired outside the release-guaranteeing `try`, so the
CancelledError escaped before any `finally` ran — leaking one permit permanently
for the process lifetime. After enough cancellations every new stream would wait
5s then fail with "Server busy - too many active streams".

The fix wraps the lookup inside the same single `try` whose `finally` releases
the permit exactly once. This test cancels each entry point mid-lookup and
asserts the permit count returns to its starting value.
"""

import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController  # noqa: E402
from core import stream_enhanced, stream_seek, stream_normal  # noqa: E402


def _make_websocket() -> Mock:
    ws = Mock()
    ws.client_state = Mock()
    ws.client_state.name = "CONNECTED"
    ws.send_text = AsyncMock()
    return ws


# (label, invoker(controller, ws)) — one per stream entry point (SIBLING check).
_ENTRY_POINTS = [
    (
        "enhanced",
        lambda c, ws: stream_enhanced.stream_enhanced_audio(c, 1, "adaptive", 1.0, ws),
    ),
    (
        "seek",
        lambda c, ws: stream_seek.stream_enhanced_audio_from_position(
            c, 1, "adaptive", 1.0, ws, 5.0
        ),
    ),
    (
        "normal",
        lambda c, ws: stream_normal.stream_normal_audio(c, 1, ws, 0.0),
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("label,invoke", _ENTRY_POINTS, ids=[e[0] for e in _ENTRY_POINTS])
async def test_permit_released_when_cancelled_during_track_lookup(label, invoke):
    controller = AudioStreamController()
    # A fresh, isolated semaphore — never the shared module-level global.
    controller._stream_semaphore = asyncio.Semaphore(2)
    # enhanced/seek assert this is truthy before the lookup; a bare sentinel is fine.
    controller.chunked_processor_class = Mock()

    entered = threading.Event()      # set once get_by_id starts running in its thread
    release_block = threading.Event()  # keeps get_by_id suspended until we allow it to end

    def _blocking_get_by_id(track_id):
        entered.set()
        # Block so the task is guaranteed suspended at the to_thread await when
        # we cancel it. Bounded so a leaked thread can't hang the suite.
        release_block.wait(timeout=10.0)
        return None

    factory = Mock()
    factory.tracks.get_by_id = _blocking_get_by_id
    controller._get_repository_factory = lambda: factory

    initial = controller._stream_semaphore._value

    task = asyncio.create_task(invoke(controller, _make_websocket()))

    # Wait until the lookup is suspended inside the worker thread.
    for _ in range(200):
        if entered.is_set():
            break
        await asyncio.sleep(0.01)
    assert entered.is_set(), f"{label}: get_by_id was never reached"

    # Cancel while suspended at `await asyncio.to_thread(get_by_id, ...)`.
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Let the orphaned worker thread finish so it doesn't linger.
    release_block.set()

    assert controller._stream_semaphore._value == initial, (
        f"{label}: permit leaked on cancellation during track lookup "
        f"({controller._stream_semaphore._value} != {initial}) — regression of #4329"
    )
