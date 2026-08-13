"""
timeout_seconds actually governs detection latency (#4843)

``HeartbeatManager`` was constructed with ``interval_seconds=30,
timeout_seconds=10``, but ``_heartbeat_loop`` slept a full ``interval_seconds``
and only then called ``is_stale()`` — i.e. exactly one interval after the
previous ``mark_ping()``, never one *timeout* after it. So ``elapsed`` at check
time was always ≈30s once a ping went unanswered, ``30 > 10`` was
unconditionally true, and ``timeout_seconds`` could not influence anything.
Anyone tuning it down to get faster failover got no improvement at all unless
they also lowered ``interval_seconds``; real worst-case latency was
``1-2 x interval_seconds``.

The loop now sleeps to whichever deadline comes first — the next ping, or the
pending pong's timeout — so detection happens ``timeout_seconds`` after the
unanswered ping, as the constructor docstring claims. An idle connection still
wakes exactly once per interval, so the accuracy costs no extra wake-ups.

These tests drive the real loop with a fake clock rather than sleeping in
wall-clock, so they assert latency in *scheduled* time and stay fast.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from websocket.websocket_protocol import HeartbeatManager  # noqa: E402


class TestSecondsUntilStale:
    """The accessor the loop schedules on."""

    def test_none_when_no_ping_outstanding(self):
        hb = HeartbeatManager(interval_seconds=30, timeout_seconds=10)

        assert hb.seconds_until_stale("c1") is None

    def test_full_timeout_immediately_after_a_ping(self):
        hb = HeartbeatManager(interval_seconds=30, timeout_seconds=10)
        hb.mark_ping("c1")

        remaining = hb.seconds_until_stale("c1")

        assert remaining is not None
        assert 9.0 < remaining <= 10.0

    def test_counts_down_as_the_ping_ages(self):
        hb = HeartbeatManager(interval_seconds=30, timeout_seconds=10)
        hb.mark_ping("c1")
        # Age the pending ping by 7s without sleeping.
        hb.pending_pongs["c1"] = datetime.now(timezone.utc) - timedelta(seconds=7)

        remaining = hb.seconds_until_stale("c1")

        assert remaining is not None
        assert 2.5 < remaining <= 3.0

    def test_goes_negative_once_the_deadline_has_passed(self):
        hb = HeartbeatManager(interval_seconds=30, timeout_seconds=10)
        hb.mark_ping("c1")
        hb.pending_pongs["c1"] = datetime.now(timezone.utc) - timedelta(seconds=25)

        remaining = hb.seconds_until_stale("c1")

        assert remaining is not None and remaining < 0
        assert hb.is_stale("c1") is True

    def test_agrees_with_is_stale_at_every_point(self):
        """The scheduler and the predicate must not disagree."""
        hb = HeartbeatManager(interval_seconds=30, timeout_seconds=10)
        hb.mark_ping("c1")

        for age in (0, 5, 9, 11, 20):
            hb.pending_pongs["c1"] = datetime.now(timezone.utc) - timedelta(seconds=age)
            remaining = hb.seconds_until_stale("c1")
            assert remaining is not None
            assert (remaining < 0) == hb.is_stale("c1"), f"disagree at age={age}"

    def test_a_pong_clears_the_deadline(self):
        hb = HeartbeatManager(interval_seconds=30, timeout_seconds=10)
        hb.mark_ping("c1")
        hb.mark_pong("c1")

        assert hb.seconds_until_stale("c1") is None
        assert hb.is_stale("c1") is False


class _FakeClock:
    """A monotonic clock the test advances, driving `loop.time()`."""

    def __init__(self) -> None:
        self.now = 1000.0

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def _run_loop_with_fake_clock(
    interval: int,
    timeout: int,
    *,
    answer_pongs: bool,
    max_wakeups: int = 40,
) -> tuple[list[float], float | None]:
    """Drive the real `run_heartbeat_loop` on a fake clock.

    `asyncio.sleep` is replaced with an advance of the fake clock, so the loop's
    own scheduling decisions determine simulated elapsed time — latency is
    asserted in scheduled time, and the tests stay fast.

    HeartbeatManager stamps wall-clock `datetime`s, so the pending-pong
    timestamp is rewritten in step with the fake clock to make `is_stale`
    observe the simulated age.
    """
    from ws_handlers import connection as connection_module

    clock = _FakeClock()
    ping_times: list[float] = []
    closed_at: list[float] = []
    wakeups = 0

    heartbeat = HeartbeatManager(interval_seconds=interval, timeout_seconds=timeout)
    ping_wall_time: dict[str, float] = {}

    async def fake_sleep(delay: float) -> None:
        nonlocal wakeups
        wakeups += 1
        if wakeups > max_wakeups:
            raise asyncio.CancelledError("wake-up budget exhausted")
        clock.advance(delay)
        if "c1" in heartbeat.pending_pongs:
            simulated_age = clock.now - ping_wall_time["c1"]
            heartbeat.pending_pongs["c1"] = (
                datetime.now(timezone.utc) - timedelta(seconds=simulated_age)
            )

    real_mark_ping = heartbeat.mark_ping

    def fake_mark_ping(cid: str) -> None:
        ping_times.append(clock.now)
        ping_wall_time[cid] = clock.now
        real_mark_ping(cid)
        if answer_pongs:
            heartbeat.mark_pong(cid)

    heartbeat.mark_ping = fake_mark_ping  # type: ignore[method-assign]

    websocket = MagicMock()

    async def fake_close(**_kwargs):
        closed_at.append(clock.now)

    websocket.close = fake_close

    fake_loop = MagicMock()
    fake_loop.time = clock.time

    with (
        patch.object(connection_module.asyncio, "sleep", fake_sleep),
        patch.object(connection_module.asyncio, "get_running_loop", lambda: fake_loop),
        patch.object(connection_module, "safe_send_text", AsyncMock(return_value=True)),
    ):
        try:
            await connection_module.run_heartbeat_loop(websocket, heartbeat, "c1")
        except asyncio.CancelledError:
            pass

    return ping_times, (closed_at[0] if closed_at else None)


@pytest.mark.asyncio
class TestDetectionLatencyFollowsTimeout:
    """The acceptance criterion: a smaller timeout means faster detection."""

    async def test_detects_one_timeout_after_the_unanswered_ping(self):
        pings, closed = await _run_loop_with_fake_clock(
            interval=30, timeout=10, answer_pongs=False
        )

        assert pings, "no ping was ever sent"
        assert closed is not None, "a hung connection was never closed"
        latency = closed - pings[0]
        assert 10.0 <= latency < 12.0, (
            f"detection took {latency}s after the unanswered ping; expected ~10s "
            "(timeout_seconds). Pre-fix this was ~30s (interval_seconds) (#4843)"
        )

    async def test_lowering_timeout_measurably_shortens_detection(self):
        """The exact thing the issue says is impossible pre-fix."""
        _, slow = await _run_loop_with_fake_clock(
            interval=30, timeout=10, answer_pongs=False
        )
        pings_fast, fast = await _run_loop_with_fake_clock(
            interval=30, timeout=3, answer_pongs=False
        )

        assert slow is not None and fast is not None
        fast_latency = fast - pings_fast[0]
        assert 3.0 <= fast_latency < 5.0, (
            f"timeout_seconds=3 gave {fast_latency}s detection — the parameter "
            "is still inert (#4843)"
        )
        assert fast < slow, "lowering timeout_seconds did not shorten detection"

    async def test_first_ping_still_waits_a_full_interval(self):
        """The ping cadence must not have been accelerated by the fix."""
        pings, _ = await _run_loop_with_fake_clock(
            interval=30, timeout=10, answer_pongs=True
        )

        assert pings, "no ping was sent"
        assert pings[0] == pytest.approx(1030.0, abs=0.5), (
            f"first ping at {pings[0]}, expected +30s from start"
        )

    async def test_healthy_connection_pings_once_per_interval(self):
        """A responsive connection must not gain extra wake-ups or pings."""
        pings, closed = await _run_loop_with_fake_clock(
            interval=30, timeout=10, answer_pongs=True, max_wakeups=10
        )

        assert closed is None, "a healthy connection was closed"
        gaps = [b - a for a, b in zip(pings, pings[1:])]
        assert gaps, "expected several pings"
        for gap in gaps:
            assert gap == pytest.approx(30.0, abs=0.5), (
                f"ping cadence drifted to {gap}s; interval_seconds must still govern"
            )
