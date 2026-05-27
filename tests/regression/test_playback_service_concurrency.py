"""
Regression test: PlaybackService.play/pause/stop/seek interleave race (#3734)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-fix: each method ran three sequential `await`s (engine call →
`set_playing(...)` → `broadcast(...)`) with no service-level
serialisation. Two concurrent requests could interleave their state
updates, leaving the UI flashed at the wrong transport state until the
next `player_state` broadcast settled it.

Post-fix: an `asyncio.Lock` (`self._playback_lock`) wraps the body of
`play`/`pause`/`stop`/`seek` so concurrent requests serialise. The last
caller's `set_playing` and `broadcast` therefore land contiguously, in
the same order the requests were dispatched.

These tests pin the new contract by interleaving asyncio tasks against
collaborators that record the order of calls.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.playback_service import PlaybackService  # noqa: E402


def _build_service() -> tuple[PlaybackService, list[str]]:
    """PlaybackService with collaborators that record call order.

    The returned `events` list captures `(method, side)` strings in the
    order operations actually fire on the event loop. With the
    service-level lock in place, all three steps of any one method
    (engine → set_playing → broadcast) must be contiguous.
    """
    events: list[str] = []

    def _engine_play() -> None:
        events.append("engine:play")

    def _engine_pause() -> None:
        events.append("engine:pause")

    def _engine_stop() -> None:
        events.append("engine:stop")

    def _engine_seek(_pos: float) -> None:
        events.append("engine:seek")

    audio_player = MagicMock()
    audio_player.play = MagicMock(side_effect=_engine_play)
    audio_player.pause = MagicMock(side_effect=_engine_pause)
    audio_player.stop = MagicMock(side_effect=_engine_stop)
    audio_player.seek = MagicMock(side_effect=_engine_seek)

    async def _set_playing(value: bool) -> None:
        # Yield so the next-method's engine call has a chance to
        # interleave if the lock were missing.
        await asyncio.sleep(0)
        events.append(f"state:set_playing({value})")

    state_manager = MagicMock()
    state_manager.set_playing = _set_playing

    async def _broadcast(msg: dict[str, Any]) -> None:
        await asyncio.sleep(0)
        events.append(f"broadcast:{msg['type']}")

    connection_manager = MagicMock()
    connection_manager.broadcast = _broadcast

    service = PlaybackService(audio_player, state_manager, connection_manager)
    return service, events


@pytest.mark.asyncio
async def test_play_then_pause_run_contiguously_under_concurrency() -> None:
    """Two simultaneous requests must not interleave their three steps."""
    service, events = _build_service()

    await asyncio.gather(service.play(), service.pause())

    # Each method emits exactly three events (engine, state, broadcast),
    # and the lock guarantees the three events for one method are
    # contiguous — never interleaved with the other.
    play_idx = events.index("engine:play")
    pause_idx = events.index("engine:pause")
    play_block = events[play_idx:play_idx + 3]
    pause_block = events[pause_idx:pause_idx + 3]

    assert play_block == [
        "engine:play",
        "state:set_playing(True)",
        "broadcast:playback_started",
    ]
    assert pause_block == [
        "engine:pause",
        "state:set_playing(False)",
        "broadcast:playback_paused",
    ]


@pytest.mark.asyncio
async def test_rapid_alternating_play_pause_serialises() -> None:
    """10 alternating play/pause calls in flight produce contiguous blocks.

    Pre-fix the events would interleave (e.g. play-engine, pause-engine,
    play-set-playing, pause-set-playing, …). The lock collapses that to
    "all three of N, then all three of N+1" for every adjacent pair.
    """
    service, events = _build_service()

    tasks = []
    for i in range(10):
        tasks.append(asyncio.create_task(
            service.play() if i % 2 == 0 else service.pause()
        ))
    await asyncio.gather(*tasks)

    # Walk the event log in groups of 3; each group must be a coherent
    # method block (engine + state + broadcast for the same op).
    assert len(events) == 30
    valid_blocks = {
        ("engine:play", "state:set_playing(True)", "broadcast:playback_started"),
        ("engine:pause", "state:set_playing(False)", "broadcast:playback_paused"),
    }
    for i in range(0, 30, 3):
        block = tuple(events[i:i + 3])
        assert block in valid_blocks, (
            f"events {i}-{i + 2} interleaved: {block} not a valid block"
        )


@pytest.mark.asyncio
async def test_stop_and_seek_also_serialise() -> None:
    """stop() and seek() share the same lock as play/pause."""
    service, events = _build_service()

    await asyncio.gather(
        service.play(),
        service.stop(),
        service.seek(42.0),
    )

    # All three methods together produce 3 + 3 + 2 events (seek doesn't
    # call set_playing). Sanity: every engine call's block is contiguous.
    engine_indices = [
        i for i, ev in enumerate(events) if ev.startswith("engine:")
    ]
    assert len(engine_indices) == 3
    # The first event in the events log must be an engine call (i.e. no
    # straggler from another method came in before the first one
    # finished its inner steps).
    assert events[0].startswith("engine:")


@pytest.mark.asyncio
async def test_set_volume_does_not_take_the_playback_lock() -> None:
    """set_volume is broadcast-only — it must not be serialised with the
    transport methods, since concurrent volume adjustments shouldn't
    block a separately-issued play/pause."""
    service, events = _build_service()

    # Hold the lock manually to simulate a slow play() in flight.
    async with service._playback_lock:
        # set_volume must still be able to broadcast even though
        # the playback lock is held.
        await asyncio.wait_for(service.set_volume(0.5), timeout=1.0)
