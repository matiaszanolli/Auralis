"""Regression test: queue mutators supersede an in-flight set_queue via the
shared generation protocol (#5320).

clear_queue() and the other queue-shape mutators (add/remove/reorder/move/
shuffle/unshuffle) used to bypass set_queue's generation protocol entirely.
A mutator landing while _set_queue_impl was between its generation check
(inside _set_queue_lock) and its engine-mutating steps (inside
_set_queue_engine_lock) still let the in-flight request run load_file()/
play() afterward, against a queue the mutator had just changed out from
under it.

Follows the real-QueueController pattern established in
test_queue_service_mutations.py rather than mocking audio_player.queue, so
the assertions check real post-mutation state (queue size, filepath) instead
of mock call counts on an object with no real semantics.
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


def _db_track(track_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=track_id,
        title=f"Track {track_id}",
        filepath=f"/music/track_{track_id}.flac",
    )


def _build_service(track_ids: list[int]):
    tracks = {tid: _db_track(tid) for tid in track_ids}
    repo = MagicMock()
    repo.get_by_ids = MagicMock(
        side_effect=lambda ids: {tid: tracks[tid] for tid in ids if tid in tracks}
    )
    # add_track_to_queue() looks tracks up individually, not via get_by_ids.
    repo.get_by_id = MagicMock(side_effect=tracks.get)
    library_database = SimpleNamespace(tracks=repo)

    controller = QueueController(lambda: None)
    audio_player = SimpleNamespace(
        queue=controller,
        load_file=MagicMock(),
        play=MagicMock(),
        stop=MagicMock(),
    )

    broadcast_started = asyncio.Event()
    release_broadcast = asyncio.Event()

    class DeferredStateManager:
        """Stalls exactly in the window the issue describes: after
        _set_queue_impl claims the generation and mutates state-manager
        state, before it enters _set_queue_engine_lock."""

        async def set_queue(self, track_infos, _start_index, *, broadcast=True):
            assert broadcast is False
            return SimpleNamespace(kind="queue", track_id=track_infos[0].id)

        async def broadcast_state(self, snapshot):
            if snapshot.kind == "queue":
                broadcast_started.set()
                await release_broadcast.wait()

        async def set_track(self, *_a, **_kw):
            return SimpleNamespace(kind="track")

        async def set_playing(self, *_a, **_kw):
            return SimpleNamespace(kind="playing")

    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    service = QueueService(
        audio_player=audio_player,
        player_state_manager=DeferredStateManager(),
        library_database=library_database,
        connection_manager=connection_manager,
        create_track_info_fn=lambda track: SimpleNamespace(id=track.id, filepath=track.filepath),
    )
    return service, controller, audio_player, broadcast_started, release_broadcast


async def _race_mutator_against_in_flight_set_queue(mutate, track_ids=(1, 2)):
    """Start set_queue, let it stall in the described window, run *mutate*,
    then release the stall and let set_queue finish. Returns (controller,
    audio_player) for the caller to assert on."""
    service, controller, audio_player, broadcast_started, release_broadcast = (
        _build_service(list(track_ids))
    )

    set_queue_task = asyncio.create_task(service.set_queue([track_ids[0]], start_index=0))
    await asyncio.wait_for(broadcast_started.wait(), timeout=1.0)

    await mutate(service)

    release_broadcast.set()
    await asyncio.wait_for(set_queue_task, timeout=1.0)
    return controller, audio_player


@pytest.mark.regression
@pytest.mark.asyncio
async def test_clear_queue_during_in_flight_set_queue_prevents_load_and_play():
    controller, audio_player = await _race_mutator_against_in_flight_set_queue(
        lambda service: service.clear_queue()
    )

    # The in-flight set_queue must never have reached its engine calls.
    audio_player.load_file.assert_not_called()
    audio_player.play.assert_not_called()
    # clear_queue's own mutation stuck: the real queue stayed empty rather
    # than being repopulated by the superseded set_queue.
    assert controller.get_queue_size() == 0


@pytest.mark.regression
@pytest.mark.asyncio
async def test_add_track_during_in_flight_set_queue_is_not_overwritten():
    controller, audio_player = await _race_mutator_against_in_flight_set_queue(
        lambda service: service.add_track_to_queue(2)
    )

    audio_player.load_file.assert_not_called()
    audio_player.play.assert_not_called()
    # The add landed on the pre-set_queue (empty) queue and must not have
    # been clobbered by the superseded set_queue's engine mutation.
    assert [t['id'] for t in controller.get_queue()] == [2]


@pytest.mark.regression
@pytest.mark.asyncio
async def test_shuffle_queue_during_in_flight_set_queue_prevents_load_and_play():
    _controller, audio_player = await _race_mutator_against_in_flight_set_queue(
        lambda service: service.shuffle_queue()
    )

    audio_player.load_file.assert_not_called()
    audio_player.play.assert_not_called()


@pytest.mark.regression
@pytest.mark.asyncio
async def test_uncontested_set_queue_still_loads_and_plays():
    """Regression: without a racing mutator, set_queue must behave exactly
    as before — this fix must not make it always abort."""
    service, controller, audio_player, broadcast_started, release_broadcast = (
        _build_service([1, 2])
    )

    set_queue_task = asyncio.create_task(service.set_queue([1], start_index=0))
    await asyncio.wait_for(broadcast_started.wait(), timeout=1.0)
    release_broadcast.set()
    await asyncio.wait_for(set_queue_task, timeout=1.0)

    audio_player.load_file.assert_called_once_with("/music/track_1.flac")
    audio_player.play.assert_called_once()
    assert [t['filepath'] for t in controller.get_queue()] == ["/music/track_1.flac"]
