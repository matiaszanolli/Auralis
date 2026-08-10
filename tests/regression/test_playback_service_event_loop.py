"""
Regression test: PlaybackService blocking engine calls on the event loop (#3716, test debt #3736)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-fix: `play()`, `pause()`, `stop()`, and `seek()` called the synchronous
`AudioPlayer` methods directly from their coroutines. `seek()` is the
load-bearing case — it acquires `file_manager._audio_lock`, which a concurrent
`load_file()` can hold for hundreds of ms while decoding a large file — so the
FastAPI worker froze and every other in-flight HTTP request and WebSocket audio
stream stalled with it.

Post-fix (#3716): each engine call is offloaded via `asyncio.to_thread`.

#3736 recorded that no test asserted this. The canary technique here mirrors
`test_navigation_service_event_loop.py` (#4772), which pinned the same contract
for NavigationService: run a short `asyncio.sleep` concurrently with the service
call and measure when the sleep finishes. A blocking implementation prevents the
canary task from even starting its sleep until the engine call returns.

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

from services.playback_service import PlaybackService  # noqa: E402

_BLOCK_SECONDS = 0.3
_CANARY_SECONDS = 0.02


def _build_service(*, blocking_attr: str) -> PlaybackService:
    """PlaybackService whose *blocking_attr* engine call sleeps the thread."""
    audio_player = MagicMock()
    for name in ("play", "pause", "stop", "seek"):
        getattr(audio_player, name).return_value = True

    getattr(audio_player, blocking_attr).side_effect = (
        lambda *_a, **_kw: time.sleep(_BLOCK_SECONDS)
    )

    state_manager = MagicMock()
    state_manager.set_playing = AsyncMock(return_value=None)

    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    return PlaybackService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        connection_manager=connection_manager,
    )


async def _canary_delay(coro) -> float:
    """Wall-clock seconds until a short concurrent canary sleep completes.

    If *coro* blocks the loop thread, the canary cannot start its own sleep
    until the synchronous call returns, so this measures ~_BLOCK_SECONDS
    instead of ~_CANARY_SECONDS.
    """
    canary_finished_at: float | None = None
    start = time.monotonic()

    async def _canary() -> None:
        nonlocal canary_finished_at
        await asyncio.sleep(_CANARY_SECONDS)
        canary_finished_at = time.monotonic()

    await asyncio.gather(coro, _canary())
    assert canary_finished_at is not None
    return canary_finished_at - start


def _assert_not_blocked(elapsed: float) -> None:
    """The canary must finish on its own schedule, not the engine call's."""
    assert elapsed < _BLOCK_SECONDS / 2, (
        f"canary took {elapsed:.3f}s (blocking call is {_BLOCK_SECONDS}s) — "
        "the engine call ran on the event loop instead of asyncio.to_thread"
    )


@pytest.mark.asyncio
async def test_play_offloads_blocking_engine_call() -> None:
    service = _build_service(blocking_attr="play")
    _assert_not_blocked(await _canary_delay(service.play()))


@pytest.mark.asyncio
async def test_pause_offloads_blocking_engine_call() -> None:
    service = _build_service(blocking_attr="pause")
    _assert_not_blocked(await _canary_delay(service.pause()))


@pytest.mark.asyncio
async def test_stop_offloads_blocking_engine_call() -> None:
    service = _build_service(blocking_attr="stop")
    _assert_not_blocked(await _canary_delay(service.stop()))


@pytest.mark.asyncio
async def test_seek_offloads_blocking_engine_call() -> None:
    """The load-bearing case: seek() contends with load_file() on _audio_lock."""
    service = _build_service(blocking_attr="seek")
    _assert_not_blocked(await _canary_delay(service.seek(12.5)))


@pytest.mark.asyncio
async def test_offloaded_call_still_reaches_the_engine() -> None:
    """Offloading must not turn the engine call into a no-op."""
    service = _build_service(blocking_attr="seek")

    result = await service.seek(12.5)

    service.audio_player.seek.assert_called_once_with(12.5)
    assert result["position"] == 12.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
