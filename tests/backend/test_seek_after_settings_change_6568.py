"""A seek after a Settings change uses the new preset/intensity (#6568).

#5874 made a Settings save reach later seeks by re-issuing the playing stream as
play_enhanced, which refreshes this connection's active_stream_settings snapshot.
The client skips that re-issue once the stream has finished delivering, so a
Settings change after that left the snapshot stale and the next seek re-mastered
with the old values. Settings changes are now recorded with a revision; a
snapshot older than the latest change loses to it on seek.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.audio_stream_controller import ws_id as _ws_id  # noqa: E402
from ws_handlers.context import StreamState, WSDeps  # noqa: E402
from ws_handlers.enhancement_params import note_settings_change, settings_revision  # noqa: E402
from ws_handlers.playback_commands import handle_play_enhanced  # noqa: E402
from ws_handlers.seek_command import handle_seek  # noqa: E402


def _ws():
    websocket = MagicMock()
    websocket.send_text = AsyncMock()
    websocket.client_state = MagicMock()
    websocket.client_state.name = "CONNECTED"
    return websocket


def _state():
    return StreamState(
        active_tasks={}, active_tasks_lock=asyncio.Lock(), active_track_ids={},
        pause_events={}, flow_events={},
    )


def _setup(global_settings):
    seeks: list[dict] = []

    async def stream_from_position(*_args, **kwargs):
        seeks.append(kwargs)

    deps = WSDeps(
        get_repository_factory=None,
        get_enhancement_settings=lambda: global_settings,
        get_processing_engine=MagicMock(),
        stream_audio=AsyncMock(),
        stream_normal=AsyncMock(),
        stream_from_position=stream_from_position,
        broadcast_manager=None,
    )
    return deps, seeks


async def _play(ws, state, deps, intensity):
    await handle_play_enhanced(
        ws, {"type": "play_enhanced", "data": {"track_id": 1, "preset": "adaptive", "intensity": intensity}},
        state, deps,
    )


async def _seek(ws, state, deps):
    await handle_seek(ws, {"type": "seek", "data": {"track_id": 1, "position": 30.0}}, state, deps)
    task = state.active_tasks.get(_ws_id(ws))
    if task is not None:
        await task


@pytest.mark.asyncio
async def test_seek_after_a_settings_change_uses_the_new_intensity():
    global_settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
    deps, seeks = _setup(global_settings)
    state, ws = _state(), _ws()

    await _play(ws, state, deps, 1.0)
    # The stream finished delivering, so the client did not re-issue; Settings lowers intensity.
    global_settings["intensity"] = 0.4
    note_settings_change("adaptive", 0.4)
    await _seek(ws, state, deps)

    assert seeks[-1]["intensity"] == 0.4


@pytest.mark.asyncio
async def test_a_live_stream_reissued_after_the_change_keeps_its_own_values():
    global_settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
    deps, seeks = _setup(global_settings)
    state, ws = _state(), _ws()

    await _play(ws, state, deps, 1.0)
    note_settings_change("adaptive", 0.4)
    # Mid-stream the broadcast re-issues play_enhanced; it re-snapshots at the current revision.
    await _play(ws, state, deps, 0.7)
    await _seek(ws, state, deps)

    assert seeks[-1]["intensity"] == 0.7


@pytest.mark.asyncio
async def test_another_connections_play_still_does_not_retarget_this_seek():
    """#4742 holds: play_enhanced moves the global but is not a Settings change."""
    global_settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
    deps, seeks = _setup(global_settings)
    state, ws_a, ws_b = _state(), _ws(), _ws()

    await _play(ws_a, state, deps, 1.0)
    await _play(ws_b, state, deps, 0.6)
    await _seek(ws_a, state, deps)

    assert seeks[-1]["intensity"] == 1.0


def test_the_intensity_route_records_a_settings_change(client):
    before = settings_revision()
    response = client.post("/api/player/enhancement/intensity", json={"intensity": 0.35})
    assert response.status_code == 200
    assert settings_revision() == before + 1
