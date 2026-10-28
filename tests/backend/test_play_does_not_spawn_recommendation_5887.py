"""Starting a track no longer runs a mastering-recommendation analysis (#5887).

#4542 wired play_enhanced / play_normal to spawn a recommendation analysis because a
recommendation panel consumed the broadcast. The panel and its hook were removed in
#5767, so each track start ran a DB read, a ChunkedAudioProcessor build and a full
analysis on the shared pool - contending with the first-chunk latency of the stream the
user is waiting for - and broadcast a message with no subscriber. The REST route
(GET /api/player/mastering/recommendation/{id}) is unchanged.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from ws_handlers.context import StreamState  # noqa: E402
from ws_handlers.playback_commands import handle_play_enhanced, handle_play_normal  # noqa: E402

pytestmark = pytest.mark.asyncio


def _ws():
    ws = MagicMock()
    ws.send_text = AsyncMock()
    ws.client_state = MagicMock()
    ws.client_state.name = "CONNECTED"
    return ws


def _state():
    return StreamState(
        active_tasks={},
        active_tasks_lock=asyncio.Lock(),
        active_track_ids={},
        pause_events={},
        flow_events={},
    )


def _deps():
    deps = MagicMock()
    deps.get_enhancement_settings = lambda: {"enabled": True, "preset": "adaptive", "intensity": 1.0}
    deps.stream_audio = AsyncMock()
    deps.stream_normal = AsyncMock()
    deps.broadcast_manager = MagicMock()
    repos = MagicMock()
    deps.get_repository_factory = lambda: repos
    return deps, repos


@pytest.mark.parametrize("handler, message", [
    (handle_play_enhanced, {"data": {"track_id": 7, "preset": "adaptive", "intensity": 1.0}}),
    (handle_play_normal, {"data": {"track_id": 7}}),
])
async def test_play_command_does_not_read_the_track_or_analyse_it_for_a_recommendation(handler, message):
    deps, repos = _deps()

    await handler(_ws(), message, _state(), deps)
    for _ in range(20):
        await asyncio.sleep(0)

    repos.tracks.get_by_id.assert_not_called()  # no recommendation lookup
    deps.broadcast_manager.broadcast.assert_not_called()


def test_the_trigger_helper_is_gone_from_the_play_path():
    import ws_handlers.enhancement_params as params
    import ws_handlers.playback_commands as commands

    assert not hasattr(params, "_generate_mastering_recommendation")
    assert not hasattr(commands, "_generate_mastering_recommendation")
