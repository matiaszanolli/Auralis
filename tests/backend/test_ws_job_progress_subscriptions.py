"""Multi-subscriber job progress (#3868) and a guarded heartbeat ping (#3870).

Both bugs lived in the `/ws` job-progress path and both were silent:

* **#3868** — `ProcessingEngine.progress_callbacks` was `dict[str, Callable]`,
  a *single* value per job. Every `subscribe_job_progress` overwrote the
  previous subscriber's closure, so with two subscribers (multi-window
  Electron, or one client subscribing twice) all but the newest stopped
  receiving `job_progress` with no error on either side. The disconnect paths
  were the mirror image: `unregister_progress_callback(job_id)` dropped the
  whole entry, so one client closing its socket unsubscribed everyone else.

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
from ws_handlers import messages as msg_handlers  # noqa: E402


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
# Handler-level subscription bookkeeping (#3868)
# ---------------------------------------------------------------------------


def _ws(state=WebSocketState.CONNECTED):
    ws = Mock()
    ws.client_state = state
    ws.send_text = AsyncMock()
    return ws


def _deps(processing_engine):
    deps = Mock()
    deps.get_processing_engine = Mock(return_value=processing_engine)
    return deps


class TestHandlerSubscriptionBookkeeping:
    """`job_subscriptions` records this connection's own callback per job."""

    async def test_subscription_is_recorded_against_the_registered_callback(self, engine):
        subs: dict = {}
        await msg_handlers.handle_subscribe_job_progress(
            _ws(), {"data": {"job_id": "job-1"}}, _deps(engine), subs
        )

        assert set(subs) == {"job-1"}
        # The tracked object is exactly what the engine holds — that identity is
        # what lets teardown unregister only this connection's subscription.
        assert engine.progress_callbacks["job-1"] == [subs["job-1"]]

    async def test_resubscribing_same_job_replaces_rather_than_stacks(self, engine):
        subs: dict = {}
        ws = _ws()
        for _ in range(3):
            await msg_handlers.handle_subscribe_job_progress(
                ws, {"data": {"job_id": "job-1"}}, _deps(engine), subs
            )

        # One subscriber, not three — otherwise this socket gets every tick 3x.
        assert len(engine.progress_callbacks["job-1"]) == 1
        assert engine.progress_callbacks["job-1"] == [subs["job-1"]]

    async def test_two_connections_on_one_job_are_tracked_independently(self, engine):
        subs_a: dict = {}
        subs_b: dict = {}
        await msg_handlers.handle_subscribe_job_progress(
            _ws(), {"data": {"job_id": "job-1"}}, _deps(engine), subs_a
        )
        await msg_handlers.handle_subscribe_job_progress(
            _ws(), {"data": {"job_id": "job-1"}}, _deps(engine), subs_b
        )

        assert subs_a["job-1"] is not subs_b["job-1"]
        assert len(engine.progress_callbacks["job-1"]) == 2

    async def test_invalid_job_id_registers_nothing(self, engine):
        subs: dict = {}
        with patch("ws_handlers.messages.send_error_response", new=AsyncMock()) as err:
            await msg_handlers.handle_subscribe_job_progress(
                _ws(), {"data": {"job_id": ""}}, _deps(engine), subs
            )
        err.assert_awaited_once()
        assert subs == {}
        assert engine.progress_callbacks == {}

    async def test_disconnected_socket_self_unregisters_only_its_own_callback(self, engine):
        """The closure's disconnect path must not evict the other subscriber."""
        _job(engine)
        subs_live: dict = {}
        subs_dead: dict = {}
        ws_dead = _ws(WebSocketState.DISCONNECTED)

        await msg_handlers.handle_subscribe_job_progress(
            _ws(), {"data": {"job_id": "job-1"}}, _deps(engine), subs_live
        )
        await msg_handlers.handle_subscribe_job_progress(
            ws_dead, {"data": {"job_id": "job-1"}}, _deps(engine), subs_dead
        )

        await engine._notify_progress("job-1", 30.0, "")

        assert engine.progress_callbacks["job-1"] == [subs_live["job-1"]]
        ws_dead.send_text.assert_not_awaited()


class TestTeardownUnregistersOnlyItsOwn:
    """`teardown_connection` leaves other connections' subscriptions intact."""

    async def test_teardown_leaves_the_other_connection_subscribed(self, engine):
        subs_a: dict = {}
        subs_b: dict = {}
        await msg_handlers.handle_subscribe_job_progress(
            _ws(), {"data": {"job_id": "job-1"}}, _deps(engine), subs_a
        )
        await msg_handlers.handle_subscribe_job_progress(
            _ws(), {"data": {"job_id": "job-1"}}, _deps(engine), subs_b
        )

        await _teardown(engine, subs_a)

        # Pre-#3868 this popped "job-1" outright, silently unsubscribing B.
        assert engine.progress_callbacks["job-1"] == [subs_b["job-1"]]

    async def test_teardown_of_the_last_subscriber_clears_the_job(self, engine):
        subs: dict = {}
        await msg_handlers.handle_subscribe_job_progress(
            _ws(), {"data": {"job_id": "job-1"}}, _deps(engine), subs
        )

        await _teardown(engine, subs)

        assert "job-1" not in engine.progress_callbacks


async def _teardown(engine, job_subscriptions):
    """Drive teardown_connection with everything but the subscription cleanup
    stubbed out — that step is what these tests are about."""
    heartbeat_task = asyncio.create_task(asyncio.sleep(3600))
    state = Mock()
    state.active_tasks_lock = asyncio.Lock()
    state.active_tasks = {}
    state.active_track_ids = {}
    state.pause_events = {}
    state.flow_events = {}
    state.active_stream_settings = {}
    manager = Mock()
    manager.disconnect = AsyncMock()
    await ws_connection.teardown_connection(
        _ws(),
        heartbeat_task,
        state,
        lambda: engine,
        job_subscriptions,
        manager,
        Mock(),
    )


# ---------------------------------------------------------------------------
# Heartbeat ping guard (#3870)
# ---------------------------------------------------------------------------


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
