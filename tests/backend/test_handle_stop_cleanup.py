"""
Regression test: handle_stop clears all per-ws registries (#4364)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

handle_stop previously popped only active_tasks, leaving active_track_ids /
pause_events / flow_events entries dangling until the next play/seek or the
disconnect teardown. It now clears all four, matching _cancel_prior_task and
teardown_connection.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

# tests/backend/conftest.py puts auralis-web/backend on sys.path.
from ws_handlers.context import StreamState
from ws_handlers.playback_control import handle_stop
from core.audio_stream_controller import ws_id as _ws_id


def _fresh_state() -> StreamState:
    return StreamState(
        active_tasks={},
        active_tasks_lock=asyncio.Lock(),
        active_track_ids={},
        pause_events={},
        flow_events={},
    )


@pytest.mark.asyncio
async def test_handle_stop_clears_all_four_registries():
    state = _fresh_state()
    websocket = AsyncMock()
    ws_id = _ws_id(websocket)

    # Populate every per-ws registry as an active stream would.
    state.active_track_ids[ws_id] = 42
    state.pause_events[ws_id] = asyncio.Event()
    state.flow_events[ws_id] = asyncio.Event()
    # No live task needed for this path (task is None → no cancel).

    await handle_stop(websocket, state)

    assert ws_id not in state.active_tasks
    assert ws_id not in state.active_track_ids
    assert ws_id not in state.pause_events
    assert ws_id not in state.flow_events
    # Client is told the stream stopped.
    websocket.send_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_stop_cancels_live_task_and_cleans_up():
    state = _fresh_state()
    websocket = AsyncMock()
    ws_id = _ws_id(websocket)

    async def _never_ending():
        await asyncio.Event().wait()

    task = asyncio.ensure_future(_never_ending())
    await asyncio.sleep(0)  # let it start
    state.active_tasks[ws_id] = task
    state.active_track_ids[ws_id] = 7
    state.pause_events[ws_id] = asyncio.Event()
    state.flow_events[ws_id] = asyncio.Event()

    await handle_stop(websocket, state)

    assert task.cancelled() or task.done()
    for reg in (state.active_tasks, state.active_track_ids, state.pause_events, state.flow_events):
        assert ws_id not in reg
