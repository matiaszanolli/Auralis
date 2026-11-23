"""A WS seek/play position that is a huge JSON integer gets a typed error, not internal_error (#6505).

JSON integers are unbounded: math.isfinite(10**400) and float(10**400) raise OverflowError instead of
answering, so a position above ~1.8e308 fell through the validation and reached the dispatch loop's
generic catch as internal_error, with an ERROR traceback.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from tests.backend.test_ws_malformed_play_commands_5973 import _deps, _sent, _state, _ws  # noqa: E402
from ws_handlers import playback_commands, seek_command  # noqa: E402
from ws_handlers.enhancement_params import is_finite_position  # noqa: E402

HUGE = 10 ** 400


@pytest.mark.asyncio
async def test_a_huge_seek_position_is_invalid_seek_position():
    ws = _ws()
    state = _state()

    await seek_command.handle_seek(ws, {"type": "seek", "data": {"track_id": 5, "position": HUGE}}, state, _deps())

    assert [f["error"] for f in _sent(ws)] == ["invalid_seek_position"]
    assert not state.active_tasks


@pytest.mark.asyncio
@pytest.mark.parametrize("handler, command", [
    (playback_commands.handle_play_enhanced, "play_enhanced"),
    (playback_commands.handle_play_normal, "play_normal"),
])
async def test_a_huge_start_position_is_invalid_start_position(handler, command):
    ws = _ws()
    state = _state()

    await handler(ws, {"type": command, "data": {"track_id": 5, "start_position": HUGE}}, state, _deps())

    assert [f["error"] for f in _sent(ws)] == ["invalid_start_position"]
    assert not state.active_tasks


@pytest.mark.parametrize("value, ok", [
    (0, True), (12.5, True), (HUGE, False), (-HUGE, False), (-1, False),
    (float("nan"), False), (float("inf"), False), (True, False), ("3", False),
])
def test_is_finite_position(value, ok):
    assert is_finite_position(value) is ok
