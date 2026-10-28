"""Shuffling records shuffle_enabled in PlayerState (#5899).

Nothing wrote PlayerState.shuffle_enabled, so every player_state snapshot carried False and
the next one (a repeat toggle, a reconnect push) switched the UI's shuffle off while the
engine queue stayed shuffled.
"""

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

pytestmark = pytest.mark.asyncio


def _service(update_state=None):
    controller = QueueController(lambda: None)
    controller.set_queue([
        {"id": i, "title": f"T{i}", "filepath": f"/m/{i}.flac"} for i in range(1, 8)
    ], 0)
    state_manager = SimpleNamespace(update_state=update_state or AsyncMock())
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()
    service = QueueService(
        audio_player=SimpleNamespace(queue=controller, load_file=MagicMock(), play=MagicMock(), stop=MagicMock()),
        player_state_manager=state_manager,
        library_database=SimpleNamespace(tracks=MagicMock()),
        connection_manager=connection_manager,
        create_track_info_fn=lambda t: t,
    )
    return service, state_manager


async def test_shuffle_then_unshuffle_are_mirrored_into_player_state():
    service, state_manager = _service()

    await service.shuffle_queue()
    state_manager.update_state.assert_awaited_with(shuffle_enabled=True)

    await service.unshuffle_queue()
    state_manager.update_state.assert_awaited_with(shuffle_enabled=False)


async def test_a_failing_state_update_does_not_fail_the_shuffle():
    service, _ = _service(update_state=AsyncMock(side_effect=RuntimeError("state manager down")))

    result = await service.shuffle_queue()

    assert result["message"] == "Queue shuffled successfully"


async def test_unshuffle_after_an_edit_still_turns_the_flag_off_5936():
    """#5936: an intervening edit drops the pre-shuffle snapshot; 'No shuffle to undo' used to
    leave the engine flag True while the UI had already flipped it off."""
    service, state_manager = _service()
    await service.shuffle_queue()
    controller = service.audio_player.queue
    assert controller.shuffle_enabled is True
    controller.queue.remove_track(0)  # any shape edit drops the snapshot
    state_manager.update_state.reset_mock()

    result = await service.unshuffle_queue()

    assert result["message"] == "No shuffle to undo"
    assert controller.shuffle_enabled is False
    state_manager.update_state.assert_awaited_with(shuffle_enabled=False)
