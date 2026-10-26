"""Regression test: set_queue ordering spans requests, not one service (#5944).

FastAPI builds a fresh QueueService for every /api/player/queue* request, so the
lock and generation counters that make a later request supersede an earlier one
used to live on an instance no other request could see (a regression of #3721,
which also voided #4825 and #5320). These tests build the two services the way
dependency injection does — separate instances over the same collaborators —
and race them.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.queue_service import QueueService  # noqa: E402

from auralis.player.queue_controller import QueueController  # noqa: E402


class _World:
    """The shared collaborators every per-request QueueService is built over."""

    def __init__(self, track_ids):
        tracks = {
            tid: SimpleNamespace(id=tid, title=f"Track {tid}", filepath=f"/music/track_{tid}.flac")
            for tid in track_ids
        }
        repo = MagicMock()
        repo.get_by_ids = MagicMock(
            side_effect=lambda ids: {tid: tracks[tid] for tid in ids if tid in tracks}
        )
        self.library_database = SimpleNamespace(tracks=repo)
        self.controller = QueueController(lambda: None)
        self.audio_player = SimpleNamespace(
            queue=self.controller, load_file=MagicMock(), play=MagicMock(), stop=MagicMock()
        )
        self.first_broadcast_started = asyncio.Event()
        self.release_first_broadcast = asyncio.Event()
        world = self

        class StateManager:
            async def set_queue(self, track_infos, _start_index, *, broadcast=True):
                return SimpleNamespace(kind="queue", track_id=track_infos[0].id)

            async def broadcast_state(self, snapshot):
                # Stall only the first request's queue snapshot, in the window
                # between its generation claim and its engine calls.
                if snapshot.kind == "queue" and snapshot.track_id == 1:
                    world.first_broadcast_started.set()
                    await world.release_first_broadcast.wait()

            async def set_track(self, *_a, **_kw):
                return SimpleNamespace(kind="track")

            async def set_playing(self, *_a, **_kw):
                return SimpleNamespace(kind="playing")

            async def clear_queue(self, *_a, **_kw):
                return SimpleNamespace(kind="clear")

        self.player_state_manager = StateManager()
        self.connection_manager = MagicMock()
        self.connection_manager.broadcast = AsyncMock()

    def new_request_service(self) -> QueueService:
        """What `_get_queue_service` does per request."""
        return QueueService(
            audio_player=self.audio_player,
            player_state_manager=self.player_state_manager,
            library_database=self.library_database,
            connection_manager=self.connection_manager,
            create_track_info_fn=lambda t: SimpleNamespace(id=t.id, filepath=t.filepath),
        )


@pytest.mark.regression
@pytest.mark.asyncio
async def test_per_request_services_share_the_set_queue_coordination_state():
    world = _World([1, 2])
    a, b = world.new_request_service(), world.new_request_service()

    assert a is not b
    assert a._set_queue_lock is b._set_queue_lock
    assert a._set_queue_engine_lock is b._set_queue_engine_lock
    before = b._set_queue_generation
    await a._invalidate_set_queue_generation()
    assert b._set_queue_generation > before


@pytest.mark.regression
@pytest.mark.asyncio
async def test_later_set_queue_on_another_request_supersedes_the_earlier_one():
    world = _World([1, 2])
    first = asyncio.create_task(world.new_request_service().set_queue([1], start_index=0))
    await asyncio.wait_for(world.first_broadcast_started.wait(), timeout=1.0)

    await world.new_request_service().set_queue([2], start_index=0)
    world.release_first_broadcast.set()
    await asyncio.wait_for(first, timeout=1.0)

    # The engine ends on the second request's track; the first never loaded.
    world.audio_player.load_file.assert_called_once_with("/music/track_2.flac")
    assert world.controller.get_queue_size() == 1


@pytest.mark.regression
@pytest.mark.asyncio
async def test_clear_queue_on_another_request_prevents_the_in_flight_load_and_play():
    world = _World([1, 2])
    in_flight = asyncio.create_task(world.new_request_service().set_queue([1], start_index=0))
    await asyncio.wait_for(world.first_broadcast_started.wait(), timeout=1.0)

    await world.new_request_service().clear_queue()
    world.release_first_broadcast.set()
    await asyncio.wait_for(in_flight, timeout=1.0)

    world.audio_player.load_file.assert_not_called()
    world.audio_player.play.assert_not_called()
    assert world.controller.get_queue_size() == 0
