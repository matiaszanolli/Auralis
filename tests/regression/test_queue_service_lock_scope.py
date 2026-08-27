"""Regression coverage for QueueService set-queue lock scope (#4825)."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.queue_service import QueueService


def _track(track_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=track_id,
        title=f"Track {track_id}",
        filepath=f"/music/track_{track_id}.flac",
    )


@pytest.mark.regression
@pytest.mark.asyncio
async def test_slow_queue_state_broadcast_does_not_hold_set_queue_lock():
    tracks = {track_id: _track(track_id) for track_id in (1, 2)}
    repository = MagicMock()
    repository.get_by_ids.side_effect = (
        lambda ids: {track_id: tracks[track_id] for track_id in ids}
    )
    library_database = SimpleNamespace(tracks=repository)

    queue_controller = MagicMock()
    audio_player = MagicMock()
    audio_player.queue = queue_controller

    first_broadcast_started = asyncio.Event()
    release_first_broadcast = asyncio.Event()
    state_mutations: list[int] = []

    class DeferredStateManager:
        async def set_queue(self, track_infos, _start_index, *, broadcast=True):
            assert broadcast is False
            track_id = track_infos[0].id
            state_mutations.append(track_id)
            return SimpleNamespace(track_id=track_id)

        async def broadcast_state(self, snapshot):
            if snapshot.track_id == 1:
                first_broadcast_started.set()
                await release_first_broadcast.wait()

    service = QueueService(
        audio_player=audio_player,
        player_state_manager=DeferredStateManager(),
        library_database=library_database,
        connection_manager=MagicMock(),
        create_track_info_fn=lambda track: SimpleNamespace(id=track.id),
    )

    first_task = asyncio.create_task(service.set_queue([1], start_index=-1))
    await asyncio.wait_for(first_broadcast_started.wait(), timeout=1.0)

    await asyncio.wait_for(service._set_queue_lock.acquire(), timeout=0.1)
    service._set_queue_lock.release()

    second_result = await asyncio.wait_for(
        service.set_queue([2], start_index=-1), timeout=1.0
    )
    release_first_broadcast.set()
    await asyncio.wait_for(first_task, timeout=1.0)

    assert state_mutations == [1, 2]
    queue_controller.set_queue.assert_called_once_with(
        ["/music/track_2.flac"], -1
    )
    assert second_result["track_count"] == 1
