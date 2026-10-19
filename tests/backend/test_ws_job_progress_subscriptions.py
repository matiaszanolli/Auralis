"""Multi-subscriber job progress (#3868) and a guarded heartbeat ping (#3870).

* **#3868** — `ProcessingEngine.progress_callbacks` was `dict[str, Callable]`,
  a *single* value per job, so with two subscribers all but the newest stopped
  receiving progress with no error on either side. The engine-level registry
  tests below pin the additive fan-out. The `/ws` handler-level half
  (`subscribe_job_progress` frames, per-connection bookkeeping, disconnect
  cleanup) was retired in #5525: no frontend ever sent the frame or consumed
  `job_progress`, and the tests for that plumbing went with it.

* **#3870** — `run_heartbeat_loop` (a closure named `_heartbeat_loop`
  until #4843 extracted it) sent its ping with a bare
  `websocket.send_text(...)` under a blanket `except Exception: return`. A
  send racing a disconnect raises `RuntimeError("Cannot call 'send' once a
  close message has been sent.")`, indistinguishable there from a genuine
  encoder/payload bug. The tests below pin that it now goes through
  `safe_send_text`, which pre-checks connection state and classifies the two.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from starlette.websockets import WebSocketState  # noqa: E402

from ws_handlers import connection as ws_connection  # noqa: E402


# ---------------------------------------------------------------------------
# Engine-level registry (#3868)
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    """A ProcessingEngine with only the progress-callback machinery live.

    Constructed via `__new__` to skip the real `__init__` (thread pools, temp
    dirs, processor pool) — these tests exercise the callback registry and
    `_notify_progress` alone.
    """
    from core.job_progress import ProgressNotifier
    from core.processing_engine import ProcessingEngine

    eng = ProcessingEngine.__new__(ProcessingEngine)
    eng.jobs = {}
    eng._jobs_lock = asyncio.Lock()
    # progress_callbacks is a property backed by ProgressNotifier (#4250
    # follow-up) — construct it directly since __init__ is skipped here.
    eng._progress = ProgressNotifier(eng.jobs, eng._jobs_lock)
    return eng


def _job(engine, job_id="job-1"):
    job = Mock()
    job.progress = 0.0
    engine.jobs[job_id] = job
    return job


class TestMultipleSubscribersPerJob:
    """The registry keeps every subscriber for a job, not just the newest."""

    async def test_two_subscribers_both_receive_progress(self, engine):
        _job(engine)
        seen_a, seen_b = [], []

        async def cb_a(job_id, progress, message):
            seen_a.append(progress)

        async def cb_b(job_id, progress, message):
            seen_b.append(progress)

        await engine.register_progress_callback("job-1", cb_a)
        await engine.register_progress_callback("job-1", cb_b)
        await engine._notify_progress("job-1", 42.0, "working")

        # Pre-#3868 cb_a was overwritten by cb_b and saw nothing.
        assert seen_a == [42.0]
        assert seen_b == [42.0]

    async def test_registering_the_same_callable_twice_does_not_double_deliver(self, engine):
        _job(engine)
        seen = []

        async def cb(job_id, progress, message):
            seen.append(progress)

        await engine.register_progress_callback("job-1", cb)
        await engine.register_progress_callback("job-1", cb)
        await engine._notify_progress("job-1", 10.0, "")

        assert seen == [10.0]

    async def test_unregistering_one_subscriber_leaves_the_other_subscribed(self, engine):
        _job(engine)
        seen_a, seen_b = [], []

        async def cb_a(job_id, progress, message):
            seen_a.append(progress)

        async def cb_b(job_id, progress, message):
            seen_b.append(progress)

        await engine.register_progress_callback("job-1", cb_a)
        await engine.register_progress_callback("job-1", cb_b)
        await engine.unregister_progress_callback("job-1", cb_a)
        await engine._notify_progress("job-1", 55.0, "")

        assert seen_a == []
        assert seen_b == [55.0]

    async def test_unregister_without_a_callback_still_clears_the_whole_job(self, engine):
        """Job-wide teardown (cancel_job / cleanup) drops every subscriber."""
        _job(engine)
        await engine.register_progress_callback("job-1", AsyncMock())
        await engine.register_progress_callback("job-1", AsyncMock())

        await engine.unregister_progress_callback("job-1")

        assert "job-1" not in engine.progress_callbacks

    async def test_unregistering_the_last_subscriber_removes_the_job_entry(self, engine):
        """No empty-list leak: the job_id key goes away with its last subscriber."""
        cb = AsyncMock()
        await engine.register_progress_callback("job-1", cb)
        await engine.unregister_progress_callback("job-1", cb)

        assert "job-1" not in engine.progress_callbacks

    async def test_unregistering_an_already_removed_callback_is_not_an_error(self, engine):
        """A self-unregister racing disconnect cleanup must not raise."""
        cb = AsyncMock()
        await engine.register_progress_callback("job-1", cb)
        await engine.unregister_progress_callback("job-1", cb)
        await engine.unregister_progress_callback("job-1", cb)  # no-op, no raise


class TestFailingSubscriberIsolation:
    """A dead subscriber is pruned individually, not job-wide."""

    async def test_a_raising_callback_does_not_unsubscribe_the_healthy_one(self, engine):
        _job(engine)
        seen = []

        async def cb_bad(job_id, progress, message):
            raise RuntimeError("dead socket")

        async def cb_good(job_id, progress, message):
            seen.append(progress)

        await engine.register_progress_callback("job-1", cb_bad)
        await engine.register_progress_callback("job-1", cb_good)

        await engine._notify_progress("job-1", 1.0, "")
        await engine._notify_progress("job-1", 2.0, "")

        # cb_bad is dropped after the first failure; cb_good keeps receiving.
        # Pre-#3868 the first failure popped the entire job_id entry.
        assert engine.progress_callbacks["job-1"] == [cb_good]
        assert seen == [1.0, 2.0]

    async def test_notify_progress_still_updates_job_progress_with_no_subscribers(self, engine):
        job = _job(engine)
        await engine._notify_progress("job-1", 77.0, "")
        assert job.progress == 77.0


# ---------------------------------------------------------------------------
# Heartbeat ping guard (#3870)
# ---------------------------------------------------------------------------


def _ws(state=WebSocketState.CONNECTED):
    ws = Mock()
    ws.client_state = state
    ws.send_text = AsyncMock()
    return ws


class TestHeartbeatPingIsGuarded:
    """The ping goes through safe_send_text, not a bare send_text."""

    async def _run_one_tick(self, ws, send_result):
        """Start setup_connection's heartbeat loop, let it emit one ping, stop.

        `interval_seconds` is patched to ~0 so the loop's initial sleep returns
        immediately instead of waiting the real 30s.
        """
        manager = Mock()
        manager.connect = AsyncMock()
        sent: list = []

        async def fake_safe_send_text(websocket, message):
            sent.append(message)
            return send_result

        with (
            patch("ws_handlers.connection.safe_send_text", new=fake_safe_send_text),
            patch("ws_handlers.connection.HeartbeatManager") as hb_cls,
        ):
            hb = hb_cls.return_value
            hb.interval_seconds = 0
            hb.is_stale.return_value = False
            # #4843: the loop now schedules on the pending-pong deadline too.
            # None means "no ping outstanding", so only the ping interval
            # governs — which is what this test wants to drive.
            hb.seconds_until_stale.return_value = None
            _cid, heartbeat, task = await ws_connection.setup_connection(ws, manager, None, None)
            # Yield enough times for the loop to run its first iteration.
            for _ in range(10):
                await asyncio.sleep(0)
                if sent:
                    break
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        return sent, heartbeat

    async def test_ping_is_sent_through_safe_send_text(self):
        sent, heartbeat = await self._run_one_tick(_ws(), send_result=True)

        assert {"type": "ping"} in sent
        heartbeat.mark_ping.assert_called()

    async def test_failed_send_stops_the_loop_without_marking_a_ping(self):
        """A ping that never went out must not count as an outstanding ping —
        otherwise is_stale() starts timing a ping the client never received."""
        sent, heartbeat = await self._run_one_tick(_ws(), send_result=False)

        assert {"type": "ping"} in sent
        heartbeat.mark_ping.assert_not_called()

    def test_heartbeat_loop_has_no_bare_send_text(self):
        """Source-level guard: the ping must not regress to an unguarded send.

        Asserted on source because the bare-send bug is the *absence* of a
        state check — a behavioural test on a mock socket passes either way.
        """
        source = (_BACKEND / "ws_handlers" / "connection.py").read_text()
        # #4843 extracted this from a closure inside setup_connection to a
        # module-level coroutine so its scheduling could be tested directly.
        start = source.index("async def run_heartbeat_loop")
        body = source[start:source.index("async def setup_connection")]
        assert "safe_send_text" in body
        assert "websocket.send_text" not in body
