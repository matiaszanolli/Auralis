"""handle_stop must not hold the process-wide transition lock across teardown (#5319).

``playback_event_sequencer.transition_lock`` is shared by every WebSocket
connection's pause/resume/stop and by the REST ``PlaybackService``. Awaiting a
cancelled streaming task's (unbounded) teardown while holding it stalled
playback control for every other connection until that teardown finished.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.playback_service import PlaybackService
from ws_handlers import playback_control
from ws_handlers.context import StreamState


class _Socket:
    def __init__(self, ws_id: str) -> None:
        self.ws_id = ws_id


def _state_with_slow_teardown(
    ws_id: str,
    teardown_started: asyncio.Event,
    release_teardown: asyncio.Event,
) -> tuple[StreamState, asyncio.Event]:
    async def _stream() -> None:
        try:
            await asyncio.sleep(3600)
        finally:
            # Stand-in for stream_enhanced's `await to_thread(processor.close)`
            # queued behind other IO_EXECUTOR work.
            teardown_started.set()
            await release_teardown.wait()

    other_pause = asyncio.Event()
    other_pause.set()
    state = StreamState(
        active_tasks={ws_id: asyncio.create_task(_stream())},
        active_tasks_lock=asyncio.Lock(),
        active_track_ids={ws_id: 1},
        pause_events={ws_id: asyncio.Event(), "other": other_pause},
        flow_events={},
    )
    return state, other_pause


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(playback_control, "_ws_id", lambda websocket: websocket.ws_id)
    monkeypatch.setattr(playback_control, "safe_send_text", mock)
    return mock


@pytest.mark.asyncio
async def test_other_connection_pause_is_not_blocked_by_stop_teardown(sent: AsyncMock) -> None:
    teardown_started = asyncio.Event()
    release_teardown = asyncio.Event()
    state, other_pause = _state_with_slow_teardown("stopper", teardown_started, release_teardown)
    await asyncio.sleep(0)  # let the stream task reach its sleep

    stop = asyncio.create_task(playback_control.handle_stop(_Socket("stopper"), state))  # type: ignore[arg-type]
    await asyncio.wait_for(teardown_started.wait(), timeout=1)

    # Connection B's pause must complete while A's teardown is still parked.
    await asyncio.wait_for(
        playback_control.handle_pause(_Socket("other"), state),  # type: ignore[arg-type]
        timeout=1,
    )
    assert other_pause.is_set() is False
    assert not stop.done()

    release_teardown.set()
    await asyncio.wait_for(stop, timeout=1)

    messages = [c.args[1] for c in sent.await_args_list]
    assert [m["type"] for m in messages] == ["playback_paused", "playback_stopped"]
    paused, stopped = messages
    # The stop was decided first, so it still owns the earlier transport seq
    # even though its message is sent after teardown completes.
    assert stopped["data"]["seq"] < paused["data"]["seq"]
    assert "stopper" not in state.active_tasks


@pytest.mark.asyncio
async def test_rest_pause_is_not_blocked_by_ws_stop_teardown(sent: AsyncMock) -> None:
    teardown_started = asyncio.Event()
    release_teardown = asyncio.Event()
    state, _ = _state_with_slow_teardown("stopper", teardown_started, release_teardown)
    await asyncio.sleep(0)

    stop = asyncio.create_task(playback_control.handle_stop(_Socket("stopper"), state))  # type: ignore[arg-type]
    await asyncio.wait_for(teardown_started.wait(), timeout=1)

    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()
    state_manager = MagicMock()
    state_manager.set_playing = AsyncMock(return_value=None)
    service = PlaybackService(MagicMock(), state_manager, connection_manager)
    await asyncio.wait_for(service.pause(), timeout=1)
    assert not stop.done()

    release_teardown.set()
    await asyncio.wait_for(stop, timeout=1)
