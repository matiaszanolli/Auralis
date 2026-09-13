"""Backend "now playing" follows engine navigation, never its own clock (#5456).

PlayerStateManager used to advance its queue when its wall-clock position
estimate reached the track's duration, while the frontend independently asked
NavigationService (and so the engine) to advance on stream completion — two
owners of "what plays next". The self-advance is gone, and NavigationService
now tells the state manager which track the engine moved to; before this, the
self-advance was the only thing that ever moved the manager's current track.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

# tests/backend/conftest.py puts auralis-web/backend on sys.path.
from core.state_manager import PlayerStateManager
from player_state import TrackInfo
from services.navigation_service import NavigationService


class _EngineQueue:
    """Just the engine-queue surface NavigationService reads."""

    def __init__(self, filepaths: list[str], current_index: int = 0) -> None:
        self.filepaths = filepaths
        self.current_index = current_index

    def get_current_track(self):
        return {"filepath": self.filepaths[self.current_index]}

    def get_queue_size(self) -> int:
        return len(self.filepaths)

    def set_current_index(self, index: int) -> None:
        self.current_index = index


class _Engine:
    def __init__(self, queue: _EngineQueue) -> None:
        self.queue = queue

    def next_track(self) -> bool:
        if self.queue.current_index + 1 >= len(self.queue.filepaths):
            return False
        self.queue.current_index += 1
        return True

    def previous_track(self) -> bool:
        if self.queue.current_index == 0:
            return False
        self.queue.current_index -= 1
        return True

    def play(self) -> None:
        pass


def _track(track_id: int) -> TrackInfo:
    return TrackInfo(
        id=track_id, title=f"Track {track_id}", artist="Artist", album="Album",
        duration=180.0 + track_id, filepath=f"/music/{track_id}.flac",
    )


@pytest.fixture
async def rig():
    ws_manager = Mock()
    ws_manager.broadcast = AsyncMock()
    state_manager = PlayerStateManager(ws_manager)
    tracks = [_track(1), _track(2), _track(3)]
    await state_manager.set_queue(tracks, start_index=0)
    engine = _Engine(_EngineQueue([t.filepath for t in tracks]))
    service = NavigationService(engine, state_manager, ws_manager, create_track_info_fn=Mock())
    try:
        yield service, state_manager, engine, ws_manager
    finally:
        await state_manager.shutdown()


def _frames(ws_manager, message_type):
    return [
        c.args[0] for c in ws_manager.broadcast.await_args_list
        if c.args[0].get("type") == message_type
    ]


@pytest.mark.asyncio
async def test_next_moves_backend_now_playing_with_the_engine(rig):
    service, state_manager, engine, ws_manager = rig

    await service.next_track()

    state = state_manager.get_state()
    assert engine.queue.current_index == 1
    assert state.queue_index == 1
    assert state.current_track.id == 2
    assert _frames(ws_manager, "player_state")[-1]["data"]["current_track"]["id"] == 2
    assert _frames(ws_manager, "track_changed")[-1]["data"]["track_index"] == 1


@pytest.mark.asyncio
async def test_previous_moves_backend_now_playing_with_the_engine(rig):
    service, state_manager, engine, _ws = rig
    engine.queue.current_index = 2
    await state_manager.follow_navigation(2, "/music/3.flac")

    await service.previous_track()

    assert state_manager.get_state().current_track.id == 2


@pytest.mark.asyncio
async def test_jump_moves_backend_now_playing_with_the_engine(rig):
    service, state_manager, _engine, ws_manager = rig

    await service.jump_to_track(2)

    state = state_manager.get_state()
    assert state.current_track.id == 3
    assert state.is_playing
    # The set_playing broadcast already carries the jumped-to track.
    assert _frames(ws_manager, "player_state")[-1]["data"]["current_track"]["id"] == 3


@pytest.mark.asyncio
async def test_a_natural_track_end_advances_exactly_once(rig, monkeypatch):
    """The loop reaching the end changes nothing; the one navigation call does."""
    service, state_manager, engine, _ws = rig
    await state_manager.set_playing(True)
    await state_manager.update_state(current_time=state_manager.get_state().duration)

    real_sleep = asyncio.sleep
    ticks = 0

    async def fast_sleep(delay):
        nonlocal ticks
        if delay:
            ticks += 1
        await real_sleep(0)

    monkeypatch.setattr("core.state_manager.asyncio.sleep", fast_sleep)
    await state_manager._stop_position_updates()
    state_manager._start_position_updates()
    while ticks < 5:
        await real_sleep(0)
    assert state_manager.get_state().queue_index == 0, "no advance without navigation"

    await service.next_track()  # the frontend's completion-driven advance
    while ticks < 10:
        await real_sleep(0)

    assert engine.queue.current_index == 1
    assert state_manager.get_state().queue_index == 1


@pytest.mark.asyncio
async def test_a_failing_state_sync_does_not_fail_the_navigation(rig):
    service, state_manager, engine, ws_manager = rig
    state_manager.follow_navigation = AsyncMock(side_effect=RuntimeError("boom"))

    result = await service.next_track()

    assert result == {"message": "Skipped to next track"}
    assert engine.queue.current_index == 1
    assert _frames(ws_manager, "track_changed")
