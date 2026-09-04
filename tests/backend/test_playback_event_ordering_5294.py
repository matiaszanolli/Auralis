"""Ordering coverage shared by REST and WebSocket playback controls (#5294)."""

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


@pytest.mark.asyncio
async def test_rest_and_websocket_controls_share_one_transport_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All split emission paths must draw from the same monotonic counter."""
    websocket = object()
    ws_id = "client"
    sent = AsyncMock()
    monkeypatch.setattr(playback_control, "_ws_id", lambda _websocket: ws_id)
    monkeypatch.setattr(playback_control, "safe_send_text", sent)

    pause_event = asyncio.Event()
    pause_event.set()
    state = StreamState(
        active_tasks={},
        active_tasks_lock=asyncio.Lock(),
        active_track_ids={},
        pause_events={ws_id: pause_event},
        flow_events={},
    )

    await playback_control.handle_pause(websocket, state)  # type: ignore[arg-type]
    paused = sent.await_args_list[-1].args[1]
    assert pause_event.is_set() is False

    await playback_control.handle_resume(websocket, state)  # type: ignore[arg-type]
    resumed = sent.await_args_list[-1].args[1]
    assert pause_event.is_set() is True

    await playback_control.handle_stop(websocket, state)  # type: ignore[arg-type]
    stopped = sent.await_args_list[-1].args[1]

    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()
    state_manager = MagicMock()
    state_manager.set_playing = AsyncMock(return_value=None)
    service = PlaybackService(MagicMock(), state_manager, connection_manager)
    await service.play()
    started = connection_manager.broadcast.await_args.args[0]

    messages = [paused, resumed, stopped, started]
    assert [message["type"] for message in messages] == [
        "playback_paused",
        "playback_resumed",
        "playback_stopped",
        "playback_started",
    ]
    seqs = [message["data"]["seq"] for message in messages]
    assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))
