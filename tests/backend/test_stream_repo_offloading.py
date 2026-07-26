"""
Repository calls on the streaming paths stay off the event loop (#4566)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`check_or_queue_fingerprint` is awaited at the start of *every* enhanced stream
and called the synchronous `fingerprint_repo.exists(track_id)` inline — a full
`session_scope()` + `SELECT COUNT` round-trip against SQLite. That blocked the
whole event loop: every other WebSocket connection, all in-flight chunk sends,
the heartbeat, and the receive loop stalled together, for an unbounded time
whenever the library DB was locked by a concurrent scan or fingerprint write.

Its siblings on the same paths (`stream_enhanced.py`, `stream_normal.py`,
`stream_seek.py`) all wrap their repository calls in `asyncio.to_thread`.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import re
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

from core.stream_fingerprint import check_or_queue_fingerprint

pytestmark = pytest.mark.asyncio

_STREAM_MODULES = sorted((_REPO_ROOT / "auralis-web" / "backend" / "core").glob("stream_*.py"))


def _controller(exists_result=True, blocking_delay=0.0):
    """A controller whose fingerprint repo optionally blocks the calling thread."""

    def exists(track_id):
        if blocking_delay:
            time.sleep(blocking_delay)
        return exists_result

    repo = MagicMock()
    repo.exists = exists
    factory = MagicMock()
    factory.fingerprints = repo

    controller = MagicMock()
    controller._get_repository_factory = MagicMock(return_value=factory)
    return controller


class TestEventLoopStaysResponsive:
    async def test_slow_repo_query_does_not_stall_the_loop(self):
        """The core regression: a 200 ms query must not freeze the heartbeat."""
        ticks = 0
        stop = asyncio.Event()

        async def heartbeat():
            nonlocal ticks
            while not stop.is_set():
                await asyncio.sleep(0.01)
                ticks += 1

        beat = asyncio.create_task(heartbeat())
        try:
            result = await check_or_queue_fingerprint(
                _controller(exists_result=True, blocking_delay=0.2), track_id=1, filepath="/a.flac"
            )
        finally:
            stop.set()
            await beat

        assert result is True
        # Inline, the loop would be blocked for the whole 200 ms and tick ~0
        # times. Offloaded, it keeps ticking every 10 ms.
        assert ticks >= 5, f"event loop stalled during the repo query (ticks={ticks})"


class TestBehaviourUnchanged:
    async def test_returns_true_when_fingerprint_exists(self):
        assert await check_or_queue_fingerprint(
            _controller(exists_result=True), track_id=7, filepath="/a.flac"
        ) is True

    async def test_returns_false_and_enqueues_when_missing(self):
        queue = MagicMock()
        queue.enqueue = MagicMock(return_value=True)

        with pytest.MonkeyPatch.context() as mp:
            import analysis.fingerprint_queue as fq

            mp.setattr(fq, "get_fingerprint_queue", lambda: queue)
            result = await check_or_queue_fingerprint(
                _controller(exists_result=False), track_id=7, filepath="/a.flac"
            )

        assert result is False
        queue.enqueue.assert_called_once_with(7)

    async def test_returns_false_without_a_repository_factory(self):
        controller = MagicMock()
        controller._get_repository_factory = None

        assert await check_or_queue_fingerprint(
            controller, track_id=1, filepath="/a.flac"
        ) is False

    async def test_awaits_the_offloaded_call(self):
        """A missing `await` yields a truthy coroutine and inverts the branch."""
        result = await check_or_queue_fingerprint(
            _controller(exists_result=False), track_id=1, filepath="/a.flac"
        )

        assert result is False, (
            "a forgotten `await` on to_thread() makes the falsy result truthy"
        )


class TestNoSyncRepoCallsRemain:
    """#4566 static guard — the pattern must not creep back in."""

    def test_no_unoffloaded_repository_call_in_stream_modules(self):
        # Repository access looks like `factory.<repo>.<method>(` or
        # `<name>_repo.<method>(`; a bare attribute read (`factory.fingerprints`)
        # is not a query and is fine.
        call = re.compile(r"\b(?:factory\.\w+\.\w+|\w*_repo\.\w+)\s*\(")
        offenders = []

        for path in _STREAM_MODULES:
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#") or "to_thread" in line:
                    continue
                if call.search(line):
                    offenders.append(f"{path.name}:{lineno}: {stripped}")

        assert not offenders, (
            "synchronous repository calls inside async stream code — wrap in "
            "asyncio.to_thread (#4566): " + "; ".join(offenders)
        )

    def test_the_guard_actually_matches_the_shape_it_targets(self):
        """Self-check: the regex must catch the pre-fix line."""
        call = re.compile(r"\b(?:factory\.\w+\.\w+|\w*_repo\.\w+)\s*\(")

        assert call.search("if fingerprint_repo.exists(track_id):")
        assert call.search("queue_state = factory.queue.get_queue_state()")
        assert not call.search("fingerprint_repo = factory.fingerprints")
