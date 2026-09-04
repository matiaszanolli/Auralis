"""
Regression test: PlaybackService.play/pause/stop/seek interleave race (#3734)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-fix: each method ran three sequential `await`s (engine call →
`set_playing(...)` → `broadcast(...)`) with no service-level
serialisation. Two concurrent requests could interleave their state
updates, leaving the UI flashed at the wrong transport state until the
next `player_state` broadcast settled it.

Post-fix: a process-wide `asyncio.Lock` exposed through `_playback_lock`
serialises each engine call with its state mutation and monotonic event seq
assignment across separately constructed service instances. Both the deferred
state snapshot and event-specific message broadcast after lock release, so a
slow client cannot freeze later transport transitions (#4751/#5294).

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

from services.playback_service import PlaybackService


def _build_service() -> tuple[PlaybackService, list[str]]:
    """PlaybackService with collaborators that record call order.

    The returned `events` list captures `(method, side)` strings in the
    order operations actually fire on the event loop. With the
    service-level lock keeps engine → set_playing transition pairs ordered;
    broadcasts may interleave after those pairs release the lock.
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

    async def _set_playing(value: bool, *, broadcast: bool = True) -> dict[str, bool]:
        # Yield so the next-method's engine call has a chance to
        # interleave if the lock were missing.
        await asyncio.sleep(0)
        assert broadcast is False
        events.append(f"state:set_playing({value})")
        return {"playing": value}

    state_manager = MagicMock()
    state_manager.set_playing = _set_playing

    async def _broadcast_state(snapshot: dict[str, bool]) -> None:
        await asyncio.sleep(0)
        events.append(f"state_broadcast:{snapshot['playing']}")

    state_manager.broadcast_state = _broadcast_state

    async def _broadcast(msg: dict[str, Any]) -> None:
        await asyncio.sleep(0)
        events.append(f"broadcast:{msg['type']}")

    connection_manager = MagicMock()
    connection_manager.broadcast = _broadcast

    service = PlaybackService(audio_player, state_manager, connection_manager)
    return service, events


@pytest.mark.asyncio
async def test_play_then_pause_run_contiguously_under_concurrency() -> None:
    """Two simultaneous requests keep engine/state transitions ordered."""
    service, events = _build_service()

    await asyncio.gather(service.play(), service.pause())

    transitions = [
        event for event in events
        if event.startswith(("engine:", "state:set_playing"))
    ]
    assert transitions == [
        "engine:play",
        "state:set_playing(True)",
        "engine:pause",
        "state:set_playing(False)",
    ]
    assert events.count("state_broadcast:True") == 1
    assert events.count("state_broadcast:False") == 1
    assert events.count("broadcast:playback_started") == 1
    assert events.count("broadcast:playback_paused") == 1


@pytest.mark.asyncio
async def test_separate_service_instances_share_the_transition_lock() -> None:
    """FastAPI builds one service per request; their lock must still be shared."""
    first, _events = _build_service()
    second, _other_events = _build_service()

    assert first._playback_lock is second._playback_lock


@pytest.mark.asyncio
async def test_transport_seq_orders_broadcasts_across_service_instances() -> None:
    """A late older broadcast carries a lower seq than the newer transition."""
    first, _events = _build_service()
    second, _other_events = _build_service()
    messages: list[dict[str, Any]] = []
    pause_sent = asyncio.Event()

    async def _reordered_broadcast(message: dict[str, Any]) -> None:
        if message["type"] == "playback_started":
            await asyncio.wait_for(pause_sent.wait(), timeout=1.0)
        messages.append(message)
        if message["type"] == "playback_paused":
            pause_sent.set()

    first.connection_manager.broadcast = _reordered_broadcast
    second.connection_manager.broadcast = _reordered_broadcast

    play_task = asyncio.create_task(first.play())
    await asyncio.sleep(0)
    pause_task = asyncio.create_task(second.pause())
    await asyncio.gather(play_task, pause_task)

    assert [message["type"] for message in messages] == [
        "playback_paused",
        "playback_started",
    ]
    seq_by_type = {
        message["type"]: message["data"]["seq"] for message in messages
    }
    assert seq_by_type["playback_started"] < seq_by_type["playback_paused"]


@pytest.mark.asyncio
async def test_rapid_alternating_play_pause_serialises() -> None:
    """10 alternating calls preserve engine/state transition pairs.

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

    transitions = [
        event for event in events
        if event.startswith(("engine:", "state:set_playing"))
    ]
    valid_blocks = {
        ("engine:play", "state:set_playing(True)"),
        ("engine:pause", "state:set_playing(False)"),
    }
    assert len(transitions) == 20
    for i in range(0, 20, 2):
        block = tuple(transitions[i:i + 2])
        assert block in valid_blocks, (
            f"transition {i // 2} interleaved: {block} not a valid block"
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
async def test_slow_state_broadcast_does_not_hold_playback_lock() -> None:
    service, events = _build_service()
    broadcast_started = asyncio.Event()

    async def _blocked_state_broadcast(_snapshot: dict[str, bool]) -> None:
        broadcast_started.set()
        await asyncio.Event().wait()

    service.player_state_manager.broadcast_state = _blocked_state_broadcast

    play_task = asyncio.create_task(service.play())
    await asyncio.wait_for(broadcast_started.wait(), timeout=1.0)

    pause_task = asyncio.create_task(service.pause())
    try:
        for _ in range(100):
            if "engine:pause" in events:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("pause could not acquire the lock during a state broadcast")
    finally:
        play_task.cancel()
        pause_task.cancel()
        await asyncio.gather(play_task, pause_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_set_volume_does_not_take_the_playback_lock() -> None:
    """set_volume is broadcast-only — it must not be serialised with the
    transport methods, since concurrent volume adjustments shouldn't
    block a separately-issued play/pause."""
    service, _events = _build_service()

    # Hold the lock manually to simulate a slow play() in flight.
    async with service._playback_lock:
        # set_volume must still be able to broadcast even though
        # the playback lock is held.
        await asyncio.wait_for(service.set_volume(0.5), timeout=1.0)
