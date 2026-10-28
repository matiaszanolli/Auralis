"""Malformed WS play/seek frames get typed errors, not internal_error (#5973).

``WebSocketMessageBase.data`` is ``dict | None`` and ``model_dump()`` always emits
the key, so ``{"type": "play_normal"}`` arrives as ``{"data": None}``;
``message.get("data", {})`` returned None and ``data.get`` raised
AttributeError. A non-numeric ``start_position`` raised ValueError from
``float()``, and ``force="false"`` was coerced to True by ``bool()``. All of them
surfaced as the generic ``internal_error`` "Command failed".
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from ws_handlers import playback_commands, seek_command  # noqa: E402
from ws_handlers.context import StreamState, WSDeps  # noqa: E402


def _state() -> StreamState:
    return StreamState(
        active_tasks={}, active_tasks_lock=asyncio.Lock(), active_track_ids={},
        pause_events={}, flow_events={},
    )


def _deps() -> WSDeps:
    deps = MagicMock(spec=WSDeps)
    deps.get_enhancement_settings = lambda: {"enabled": True, "preset": "adaptive", "intensity": 1.0}
    deps.get_repository_factory = lambda: None
    deps.stream_audio = AsyncMock()
    deps.stream_normal = AsyncMock()
    return deps


def _ws() -> MagicMock:
    ws = MagicMock()
    ws.send_text = AsyncMock()
    return ws


def _sent(ws) -> list[dict]:
    import json
    return [json.loads(c.args[0]) for c in ws.send_text.call_args_list]


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [
    playback_commands.handle_play_enhanced, playback_commands.handle_play_normal, seek_command.handle_seek,
])
@pytest.mark.parametrize("message", [{"type": "x"}, {"type": "x", "data": None}])
async def test_missing_or_null_data_is_an_invalid_track_id_error(handler, message):
    ws = _ws()

    await handler(ws, message, _state(), _deps())

    assert [f["error"] for f in _sent(ws)] == ["invalid_track_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("handler, command", [
    (playback_commands.handle_play_enhanced, "play_enhanced"),
    (playback_commands.handle_play_normal, "play_normal"),
])
@pytest.mark.parametrize("bad", ["abc", [1], {"x": 1}])
async def test_non_numeric_start_position_is_a_typed_error(handler, command, bad):
    ws = _ws()
    state = _state()

    await handler(ws, {"type": command, "data": {"track_id": 5, "start_position": bad}}, state, _deps())

    frames = _sent(ws)
    assert [f["error"] for f in frames] == ["invalid_start_position"]
    assert frames[0]["command"] == command
    assert not state.active_tasks, "no stream may start for a rejected command"


@pytest.mark.asyncio
@pytest.mark.parametrize("raw, expected", [(None, 0.0), (0, 0.0), ("12.5", 12.5), (30, 30.0), (float("inf"), 0.0)])
async def test_valid_and_degradable_start_positions_still_start_a_stream(raw, expected):
    ws, deps, state = _ws(), _deps(), _state()

    await playback_commands.handle_play_normal(
        ws, {"type": "play_normal", "data": {"track_id": 5, "start_position": raw}}, state, deps
    )

    assert _sent(ws) == []
    assert deps.stream_normal.call_args.kwargs["start_position"] == expected
    for task in list(state.active_tasks.values()):
        await task


@pytest.mark.asyncio
@pytest.mark.parametrize("force", ["false", 1, 0, "yes"])
async def test_force_must_be_a_real_boolean(force):
    ws = _ws()

    await playback_commands.handle_play_enhanced(
        ws, {"type": "play_enhanced", "data": {"track_id": 5, "force": force}}, _state(), _deps()
    )

    assert [f["error"] for f in _sent(ws)] == ["invalid_force"]
