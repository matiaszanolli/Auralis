"""Runtime enhancement_settings is process-global — a second client's
play_enhanced must not retarget a first client's subsequent seeks (#4742).

`handle_play_enhanced` used to write the accepted preset/intensity into the
process-global `enhancement_settings` dict, and `handle_seek` read them back
out of that same dict. Since the dict is shared by every WebSocket
connection, a second connection's `play_enhanced` silently clobbered a first,
still-open connection's subsequent `seek`.

The fix: `handle_play_enhanced` records what it resolved onto
`StreamState.active_stream_settings`, keyed by ws_id, and `handle_seek` reads
its OWN connection's entry from there instead of the shared global.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.audio_stream_controller import ws_id as _ws_id  # noqa: E402
from ws_handlers.context import StreamState, WSDeps  # noqa: E402
from ws_handlers.playback_commands import handle_play_enhanced, handle_seek  # noqa: E402

pytestmark = pytest.mark.asyncio


def _ws():
    websocket = MagicMock()
    websocket.send_text = AsyncMock()
    websocket.client_state = MagicMock()
    websocket.client_state.name = "CONNECTED"
    return websocket


def _state():
    return StreamState(
        active_tasks={},
        active_tasks_lock=asyncio.Lock(),
        active_track_ids={},
        pause_events={},
        flow_events={},
    )


async def _seek_and_await(websocket, message, state, deps):
    """handle_seek fires stream_from_position as a background task; await it
    so the mock's call is recorded before the assertion runs."""
    await handle_seek(websocket, message, state, deps)
    task = state.active_tasks.get(_ws_id(websocket))
    if task is not None:
        await task


def _deps(settings: dict, stream_from_position=None):
    return WSDeps(
        get_repository_factory=None,
        get_enhancement_settings=lambda: settings,
        get_cache_manager=None,
        get_processing_engine=MagicMock(),
        stream_audio=AsyncMock(),
        stream_normal=AsyncMock(),
        stream_from_position=stream_from_position or AsyncMock(),
        broadcast_manager=None,
    )


async def test_second_connections_play_enhanced_does_not_retarget_first_connections_seek():
    # A single shared global, exactly as production wires it (routes.py's
    # `get_enhancement_settings=lambda: enhancement_settings` closure).
    global_settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
    state = _state()

    seek_calls: list[dict] = []

    async def stream_from_position(*_args, **kwargs):
        seek_calls.append(kwargs)

    deps = _deps(global_settings, stream_from_position=stream_from_position)

    ws_a = _ws()
    ws_b = _ws()

    # Connection A starts an enhanced stream with "adaptive".
    await handle_play_enhanced(
        ws_a,
        {"type": "play_enhanced", "data": {"track_id": 1, "preset": "adaptive", "intensity": 1.0}},
        state,
        deps,
    )
    # Connection B starts a DIFFERENT stream with "punchy" — this used to
    # rewrite the shared global that A's seek reads from.
    await handle_play_enhanced(
        ws_b,
        {"type": "play_enhanced", "data": {"track_id": 2, "preset": "punchy", "intensity": 0.6}},
        state,
        deps,
    )
    assert global_settings["preset"] == "punchy"  # confirms the shared global did change

    # Connection A seeks — must stay on its OWN "adaptive" preset, not B's.
    await _seek_and_await(
        ws_a,
        {"type": "seek", "data": {"track_id": 1, "position": 20.0}},
        state,
        deps,
    )

    assert len(seek_calls) == 1
    assert seek_calls[0]["preset"] == "adaptive"
    assert seek_calls[0]["intensity"] == 1.0


async def test_single_connection_play_enhanced_then_seek_uses_its_own_settings():
    """Regression: unchanged single-connection behavior."""
    global_settings = {"enabled": True, "preset": "adaptive", "intensity": 1.0}
    state = _state()

    seek_calls: list[dict] = []

    async def stream_from_position(*_args, **kwargs):
        seek_calls.append(kwargs)

    deps = _deps(global_settings, stream_from_position=stream_from_position)
    websocket = _ws()

    await handle_play_enhanced(
        websocket,
        {"type": "play_enhanced", "data": {"track_id": 5, "preset": "warm", "intensity": 0.7}},
        state,
        deps,
    )
    await _seek_and_await(
        websocket,
        {"type": "seek", "data": {"track_id": 5, "position": 10.0}},
        state,
        deps,
    )

    assert len(seek_calls) == 1
    assert seek_calls[0]["preset"] == "warm"
    assert seek_calls[0]["intensity"] == 0.7


async def test_seek_falls_back_to_global_when_no_prior_play_enhanced_on_this_connection():
    """A seek that arrives before any play_enhanced on this connection has no
    per-connection entry yet — it must still fall back to the stored global
    default rather than erroring."""
    global_settings = {"enabled": True, "preset": "bright", "intensity": 0.9}
    state = _state()

    seek_calls: list[dict] = []

    async def stream_from_position(*_args, **kwargs):
        seek_calls.append(kwargs)

    deps = _deps(global_settings, stream_from_position=stream_from_position)
    websocket = _ws()

    await _seek_and_await(
        websocket,
        {"type": "seek", "data": {"track_id": 9, "position": 3.0}},
        state,
        deps,
    )

    assert len(seek_calls) == 1
    assert seek_calls[0]["preset"] == "bright"
    assert seek_calls[0]["intensity"] == 0.9
