"""A stalled WebSocket client cannot freeze transport controls (#4581).

`PlaybackService.play/pause/stop` held `_playback_lock` across
`ConnectionManager.broadcast()`, and `broadcast()` did a per-client
`await connection.send_text(...)` with no timeout. Starlette applies
backpressure, so a client that stops reading — a suspended Electron renderer, a
half-open TCP connection not yet detected as stale — makes `send_text` block
until the OS socket buffer drains. Every other transport command then queued
behind that one send, with no bound and no error path.

Two independent remedies, both asserted here: the broadcast now runs outside the
lock, and each per-client send is bounded by `BROADCAST_SEND_TIMEOUT`.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

from config.globals import BROADCAST_SEND_TIMEOUT, ConnectionManager  # noqa: E402


class _StalledClient:
    """A client that accepts the send but never completes it."""

    def __init__(self):
        self.started = asyncio.Event()

    async def send_text(self, _message: str) -> None:
        self.started.set()
        await asyncio.Event().wait()      # never returns


class _HealthyClient:
    def __init__(self):
        self.received: list[str] = []

    async def send_text(self, message: str) -> None:
        self.received.append(message)


class TestBroadcastBoundsEachSend:

    @pytest.mark.asyncio
    async def test_evicts_a_client_that_never_completes_its_send(self, monkeypatch):
        monkeypatch.setattr("config.globals.BROADCAST_SEND_TIMEOUT", 0.05)

        mgr = ConnectionManager()
        stalled = _StalledClient()
        mgr.active_connections.append(stalled)  # type: ignore[arg-type]

        await asyncio.wait_for(mgr.broadcast({"type": "x"}), timeout=2.0)

        assert stalled not in mgr.active_connections, (
            "a wedged client was left registered — every future broadcast "
            "would stall on it again"
        )

    @pytest.mark.asyncio
    async def test_healthy_clients_still_receive_when_one_stalls(self, monkeypatch):
        monkeypatch.setattr("config.globals.BROADCAST_SEND_TIMEOUT", 0.05)

        mgr = ConnectionManager()
        stalled = _StalledClient()
        healthy = _HealthyClient()
        mgr.active_connections.extend([stalled, healthy])  # type: ignore[list-item]

        await asyncio.wait_for(mgr.broadcast({"type": "playback_started"}), timeout=2.0)

        assert len(healthy.received) == 1, "the healthy client was starved"
        assert stalled not in mgr.active_connections
        assert healthy in mgr.active_connections

    @pytest.mark.asyncio
    async def test_normal_broadcast_still_delivers_to_every_client(self):
        mgr = ConnectionManager()
        clients = [_HealthyClient() for _ in range(3)]
        mgr.active_connections.extend(clients)  # type: ignore[list-item]

        await mgr.broadcast({"type": "playback_paused", "data": {"state": "paused"}})

        for c in clients:
            assert len(c.received) == 1
        assert len(mgr.active_connections) == 3, "healthy clients must not be evicted"

    @pytest.mark.asyncio
    async def test_raising_client_is_still_evicted(self):
        """The pre-existing error path must be unchanged."""
        mgr = ConnectionManager()
        broken = Mock()
        broken.send_text = AsyncMock(side_effect=RuntimeError("socket closed"))
        mgr.active_connections.append(broken)

        await mgr.broadcast({"type": "x"})
        assert broken not in mgr.active_connections

    def test_timeout_is_configured(self):
        assert 0 < BROADCAST_SEND_TIMEOUT <= 10


class TestPlaybackLockNotHeldAcrossBroadcast:

    @staticmethod
    def _service(connection_manager):
        from services.playback_service import PlaybackService

        svc = PlaybackService.__new__(PlaybackService)
        svc._playback_lock = asyncio.Lock()
        svc.audio_player = Mock()
        svc.connection_manager = connection_manager

        state_manager = Mock()
        state_manager.set_playing = AsyncMock()
        state_manager.broadcast_state = AsyncMock()
        svc.player_state_manager = state_manager
        return svc

    @pytest.mark.asyncio
    async def test_a_stalled_broadcast_does_not_block_a_concurrent_command(self):
        """The #4581 regression, stated as the user sees it.

        The broadcast is made to hang outright (no timeout involved) so this
        asserts the *lock placement* specifically, not the timeout remedy.
        """
        first_broadcast_started = asyncio.Event()

        class _HangingManager:
            async def broadcast(self, _message):
                first_broadcast_started.set()
                await asyncio.Event().wait()

        svc = self._service(_HangingManager())

        engine_calls: list[str] = []
        svc.audio_player.play = lambda: engine_calls.append("play")
        svc.audio_player.pause = lambda: engine_calls.append("pause")

        play_task = asyncio.create_task(svc.play())
        await asyncio.wait_for(first_broadcast_started.wait(), timeout=2.0)
        assert engine_calls == ["play"]

        # play() is now parked inside broadcast(). pause() must still be able
        # to take _playback_lock and drive the engine. (It will then park in
        # its own broadcast, which is why we assert on the engine call rather
        # than on pause() returning.)
        pause_task = asyncio.create_task(svc.pause())
        try:
            for _ in range(100):
                if "pause" in engine_calls:
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail(
                    "pause() never reached the engine while play() sat in "
                    "broadcast() — _playback_lock is still held across the "
                    "send (#4581)"
                )
        finally:
            play_task.cancel()
            pause_task.cancel()
            await asyncio.gather(play_task, pause_task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_state_transition_still_happens_under_the_lock(self):
        """The lock must still serialize the engine call + state update (#3734)."""
        order: list[str] = []

        class _RecordingManager:
            async def broadcast(self, _message):
                order.append("broadcast")

        svc = self._service(_RecordingManager())
        svc.audio_player.play = lambda: order.append("engine")

        async def _set_playing(_value, *, broadcast=True):
            assert broadcast is False
            order.append("state")
            return "snapshot"

        async def _broadcast_state(_snapshot):
            order.append("state_broadcast")

        svc.player_state_manager.set_playing = _set_playing
        svc.player_state_manager.broadcast_state = _broadcast_state

        await svc.play()

        assert order == ["engine", "state", "state_broadcast", "broadcast"], (
            f"transition order changed: {order}"
        )

    @pytest.mark.asyncio
    async def test_all_three_broadcasting_methods_release_the_lock_first(self):
        """CONSISTENCY: play, pause and stop must all be fixed.

        seek() is deliberately absent — #3777 removed its broadcast, so it has
        no send under the lock to move.
        """
        import inspect

        from services import playback_service

        source = inspect.getsource(playback_service.PlaybackService)

        for method in ("play", "pause", "stop"):
            body = source.split(f"async def {method}(")[1].split("async def ")[0]
            lines = body.split("\n")
            lock_line = next(
                i for i, ln in enumerate(lines)
                if "async with self._playback_lock" in ln
            )
            broadcast_line = next(
                i for i, ln in enumerate(lines)
                if "self.connection_manager.broadcast" in ln
            )
            lock_indent = len(lines[lock_line]) - len(lines[lock_line].lstrip())
            broadcast_indent = (
                len(lines[broadcast_line]) - len(lines[broadcast_line].lstrip())
            )

            assert broadcast_line > lock_line
            # A statement inside `async with` is indented deeper than the
            # `async with` itself; at or below it means the block has closed.
            assert broadcast_indent <= lock_indent, (
                f"{method}() still broadcasts inside the lock (#4581): "
                f"broadcast indent {broadcast_indent} > lock indent {lock_indent}"
            )

    def test_seek_has_no_broadcast_to_move(self):
        import inspect

        from services import playback_service

        source = inspect.getsource(playback_service.PlaybackService.seek)
        assert "connection_manager.broadcast" not in source, (
            "seek() gained a broadcast — it must go outside the lock too"
        )
