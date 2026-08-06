"""
Regression test: NavigationService blocking AudioPlayer calls on the event loop (#4772)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-fix: `next_track()`, `previous_track()`, and `jump_to_track()` called
blocking `AudioPlayer`/`QueueController` engine methods directly on the
FastAPI event loop, unlike the identical hazard already fixed in
`PlaybackService` (#3716) and `QueueService` (#3554).

Post-fix: every synchronous engine call is offloaded via `asyncio.to_thread`,
so a slow/blocking engine call no longer stalls other coroutines scheduled on
the same loop (concurrent HTTP requests, WebSocket audio streams).

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.navigation_service import NavigationService  # noqa: E402

_BLOCK_SECONDS = 0.3
_CANARY_SECONDS = 0.02


def _build_service(*, blocking_attr: str, queue_size: int = 5):
    audio_player = MagicMock()
    audio_player.next_track = MagicMock(return_value=True)
    audio_player.previous_track = MagicMock(return_value=True)
    audio_player.load_file = MagicMock()
    audio_player.play = MagicMock()

    queue = MagicMock()
    queue.get_queue_size = MagicMock(return_value=queue_size)
    queue.set_current_index = MagicMock()
    queue.current_index = 0
    audio_player.queue = queue

    # Whichever engine call the test targets blocks the calling *thread* for
    # _BLOCK_SECONDS. If it ran directly on the event loop (pre-fix), that
    # blocks every other coroutine scheduled on the same loop for the same
    # duration; offloaded via asyncio.to_thread (post-fix), it does not.
    if blocking_attr in ("next_track", "previous_track"):
        target = getattr(audio_player, blocking_attr)
        target.side_effect = lambda: (time.sleep(_BLOCK_SECONDS), True)[1]
    else:
        target = getattr(queue, blocking_attr)
        target.side_effect = lambda *a, **kw: time.sleep(_BLOCK_SECONDS)

    state_manager = MagicMock()
    state_manager.set_playing = AsyncMock()

    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    service = NavigationService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        connection_manager=connection_manager,
        create_track_info_fn=MagicMock(),
    )
    return service


async def _canary_delay(coro) -> float:
    """Run *coro* concurrently with a short 'canary' sleep; return the
    wall-clock time (seconds) from just before both are scheduled until the
    canary completes.

    If *coro* blocks the event loop's thread, the canary task cannot even
    start its own `asyncio.sleep` until *coro*'s synchronous blocking call
    returns and yields control back — so a blocking implementation makes
    this take ~_BLOCK_SECONDS instead of ~_CANARY_SECONDS, regardless of
    how short the canary's own sleep is.
    """
    canary_finished_at = None
    start = time.monotonic()

    async def _canary():
        nonlocal canary_finished_at
        await asyncio.sleep(_CANARY_SECONDS)
        canary_finished_at = time.monotonic()

    await asyncio.gather(coro, _canary())
    assert canary_finished_at is not None
    return canary_finished_at - start


class TestNavigationServiceDoesNotBlockEventLoop:
    @pytest.mark.asyncio
    async def test_next_track_offloads_blocking_engine_call(self):
        service = _build_service(blocking_attr="next_track")
        canary_elapsed = await _canary_delay(service.next_track())
        # Canary should finish close to its own sleep duration, not be
        # forced to wait out the blocking engine call first.
        assert canary_elapsed < _BLOCK_SECONDS / 2

    @pytest.mark.asyncio
    async def test_previous_track_offloads_blocking_engine_call(self):
        service = _build_service(blocking_attr="previous_track")
        canary_elapsed = await _canary_delay(service.previous_track())
        assert canary_elapsed < _BLOCK_SECONDS / 2

    @pytest.mark.asyncio
    async def test_jump_to_track_offloads_blocking_engine_call(self):
        service = _build_service(blocking_attr="set_current_index")
        canary_elapsed = await _canary_delay(service.jump_to_track(2))
        assert canary_elapsed < _BLOCK_SECONDS / 2
