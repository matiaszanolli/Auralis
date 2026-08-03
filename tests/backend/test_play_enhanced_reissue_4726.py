"""Same-track enhanced commands must apply their new live parameters (#4726)."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from ws_handlers.context import StreamState, WSDeps  # noqa: E402
from ws_handlers.playback_commands import handle_play_enhanced  # noqa: E402

pytestmark = pytest.mark.asyncio


def _ws():
    websocket = MagicMock()
    websocket.send_text = AsyncMock()
    websocket.client_state = MagicMock()
    websocket.client_state.name = "CONNECTED"
    return websocket


async def test_same_track_reissue_replaces_task_and_applies_new_parameters():
    settings = {"enabled": True, "preset": "warm", "intensity": 0.4}
    calls: list[dict] = []
    starts = [asyncio.Event(), asyncio.Event()]
    never_finish = asyncio.Event()

    async def stream_audio(*_args, **kwargs):
        calls.append(kwargs)
        starts[len(calls) - 1].set()
        await never_finish.wait()

    deps = WSDeps(
        get_repository_factory=None,
        get_enhancement_settings=lambda: settings,
        get_cache_manager=None,
        get_processing_engine=MagicMock(),
        stream_audio=stream_audio,
        stream_normal=AsyncMock(),
        stream_from_position=AsyncMock(),
        broadcast_manager=None,
    )
    state = StreamState(
        active_tasks={},
        active_tasks_lock=asyncio.Lock(),
        active_track_ids={},
        pause_events={},
        flow_events={},
    )
    websocket = _ws()
    first = {
        "type": "play_enhanced",
        "data": {"track_id": 7, "preset": "warm", "intensity": 0.4},
    }
    second = {
        "type": "play_enhanced",
        "data": {
            "track_id": 7,
            "preset": "bright",
            "intensity": 0.8,
            "start_position": 12.5,
        },
    }

    await handle_play_enhanced(websocket, first, state, deps)
    await starts[0].wait()
    ws_id = next(iter(state.active_tasks))
    first_task = state.active_tasks[ws_id]

    await handle_play_enhanced(websocket, second, state, deps)
    await starts[1].wait()
    second_task = state.active_tasks[ws_id]

    try:
        assert first_task.cancelled()
        assert second_task is not first_task
        assert len(calls) == 2
        assert calls[1]["track_id"] == 7
        assert calls[1]["preset"] == "bright"
        assert calls[1]["intensity"] == 0.8
        assert calls[1]["start_position"] == 12.5
        assert settings["preset"] == "bright"
        assert settings["intensity"] == 0.8
    finally:
        second_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second_task
