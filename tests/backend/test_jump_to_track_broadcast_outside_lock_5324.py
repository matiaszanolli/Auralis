"""Regression test: jump_to_track releases _sequencer.lock before broadcasting (#5324).

next_track/previous_track already broadcast only after releasing
_TrackChangeSequencer.lock (#4582); jump_to_track was the one outlier still
awaiting set_playing(True)'s broadcast (bounded by BROADCAST_SEND_TIMEOUT per
client, config/globals.py) while holding the lock — one slow WebSocket
client stalled every other next/previous/jump command behind it for up to
that timeout.

NavigationService is re-instantiated per HTTP request (routers/player.py
wires it via FastAPI Depends()), so the lock must be the shared module-level
`_sequencer` singleton for these tests to actually exercise cross-request
contention — same reasoning as
test_navigation_service_track_changed_ordering_4582.py.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.navigation_service import NavigationService, _sequencer  # noqa: E402


def _make_service(*, slow_broadcast_seconds: float = 0.0) -> NavigationService:
    audio_player = MagicMock()
    audio_player.next_track = MagicMock(return_value=True)
    audio_player.load_file = MagicMock()
    audio_player.play = MagicMock()

    queue = MagicMock()
    queue.get_queue_size = MagicMock(return_value=5)
    queue.set_current_index = MagicMock()
    queue.current_index = 0
    queue.get_current_track = MagicMock(return_value=None)
    audio_player.queue = queue

    # Mirrors the REAL PlayerStateManager.set_playing: when broadcast=True
    # (its default), the broadcast happens *inside* set_playing itself; a
    # separate broadcast_state() call is only ever made for a *deferred*
    # broadcast (broadcast=False, then broadcast_state() later). So on
    # pre-fix code — which calls set_playing(True) with the default
    # broadcast=True — the slow path must live in set_playing, not
    # broadcast_state, or these mocks would never reproduce the bug they're
    # meant to catch (verified: without this, the "does not stall" tests
    # below pass even against pre-#5324 code).
    state_manager = MagicMock()

    async def _set_playing(playing, *, broadcast=True):
        if broadcast and slow_broadcast_seconds:
            await asyncio.sleep(slow_broadcast_seconds)
        return MagicMock()

    state_manager.set_playing = AsyncMock(side_effect=_set_playing)
    state_manager.follow_navigation = AsyncMock(return_value=None)

    async def _broadcast_state(snapshot):
        if slow_broadcast_seconds:
            await asyncio.sleep(slow_broadcast_seconds)

    state_manager.broadcast_state = AsyncMock(side_effect=_broadcast_state)

    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    return NavigationService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        connection_manager=connection_manager,
        create_track_info_fn=MagicMock(),
    )


@pytest.mark.asyncio
async def test_lock_released_before_broadcast_state_is_awaited():
    """The lock must already be free the instant broadcast_state() runs."""
    lock_held_during_broadcast: list[bool] = []
    service = _make_service()

    async def _spy_broadcast(snapshot):
        lock_held_during_broadcast.append(_sequencer.lock.locked())

    service.player_state_manager.broadcast_state = AsyncMock(side_effect=_spy_broadcast)

    await service.jump_to_track(2)

    assert lock_held_during_broadcast == [False], (
        "_sequencer.lock was still held while broadcast_state() was awaited"
    )


@pytest.mark.asyncio
async def test_slow_broadcast_does_not_stall_a_concurrent_next_track():
    """A slow WS client (slow broadcast_state) during jump_to_track must not
    block a concurrent next_track() behind _sequencer.lock — the exact
    scenario the issue describes."""
    slow_service = _make_service(slow_broadcast_seconds=0.3)
    fast_service = _make_service()

    jump_task = asyncio.create_task(slow_service.jump_to_track(1))
    # Give jump_to_track a moment to acquire+release the lock and enter its
    # slow broadcast — the window this bug widens BROADCAST_SEND_TIMEOUT-wide.
    await asyncio.sleep(0.02)

    start = asyncio.get_event_loop().time()
    await fast_service.next_track()
    elapsed = asyncio.get_event_loop().time() - start

    await jump_task  # let the slow broadcast finish before the test exits

    assert elapsed < 0.15, (
        f"next_track() took {elapsed:.3f}s — blocked behind jump_to_track's "
        "in-flight slow broadcast instead of running concurrently with it"
    )


@pytest.mark.asyncio
async def test_slow_broadcast_does_not_stall_a_concurrent_jump_to_track():
    """Same scenario, but the racing command is itself a jump — both must
    serialize only on the synchronous mutate-and-tag step, not the broadcast."""
    slow_service = _make_service(slow_broadcast_seconds=0.3)
    fast_service = _make_service()

    jump_task = asyncio.create_task(slow_service.jump_to_track(1))
    await asyncio.sleep(0.02)

    start = asyncio.get_event_loop().time()
    await fast_service.jump_to_track(3)
    elapsed = asyncio.get_event_loop().time() - start

    await jump_task

    assert elapsed < 0.15, (
        f"jump_to_track() took {elapsed:.3f}s — blocked behind another "
        "jump_to_track's in-flight slow broadcast"
    )
