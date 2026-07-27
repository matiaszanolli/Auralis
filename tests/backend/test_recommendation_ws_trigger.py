"""The mastering recommendation fires on the live WS play paths (#4542).

``RecommendationService.generate_and_broadcast_recommendation`` — which computes
and broadcasts the ``mastering_recommendation`` message — was only ever
scheduled as a FastAPI ``BackgroundTask`` from ``POST /api/player/load``. The
frontend never calls that endpoint: its real playback path is the WebSocket
``play_enhanced`` / ``play_normal`` commands. The feature was therefore dead for
every track in every session — the panel would show a loading state for 10s and
time out, 100% of the time.

Both handlers now spawn the recommendation via ``spawn_background_task``
(not ``BackgroundTasks``, per #3553, which flagged that running the full audio
analysis through it puts the work on the event loop).

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from ws_handlers import playback_commands  # noqa: E402
from ws_handlers.playback_commands import (  # noqa: E402
    handle_play_enhanced,
    handle_play_normal,
)

pytestmark = pytest.mark.asyncio


def _ws():
    ws = MagicMock()
    ws.send_text = AsyncMock()
    ws.client_state = MagicMock()
    ws.client_state.name = "CONNECTED"
    return ws


def _state():
    from ws_handlers.context import StreamState

    return StreamState(
        active_tasks={},
        active_tasks_lock=asyncio.Lock(),
        active_track_ids={},
        pause_events={},
        flow_events={},
    )


def _deps(*, filepath="/music/track.flac", with_manager=True, with_repos=True):
    deps = MagicMock()
    deps.get_enhancement_settings = lambda: {
        "enabled": True,
        "preset": "adaptive",
        "intensity": 1.0,
    }
    deps.stream_audio = AsyncMock()
    deps.stream_normal = AsyncMock()

    if with_repos:
        track = MagicMock()
        track.filepath = filepath
        repos = MagicMock()
        repos.tracks.get_by_id = MagicMock(return_value=track)
        deps.get_repository_factory = lambda: repos
    else:
        deps.get_repository_factory = None

    deps.broadcast_manager = MagicMock() if with_manager else None
    return deps


async def _drain():
    """Let the spawned background task run to completion."""
    for _ in range(20):
        await asyncio.sleep(0)


class TestRecommendationFiresOnPlayPaths:
    """The whole finding: the function had no reachable caller."""

    async def test_play_enhanced_triggers_recommendation(self, monkeypatch):
        service = MagicMock()
        service.generate_and_broadcast_recommendation = AsyncMock(return_value={})
        factory = MagicMock(return_value=service)
        monkeypatch.setattr(
            "services.recommendation_service.RecommendationService", factory
        )

        deps = _deps()
        await handle_play_enhanced(
            _ws(), {"type": "play_enhanced", "data": {"track_id": 7}}, _state(), deps
        )
        await _drain()

        service.generate_and_broadcast_recommendation.assert_awaited_once()
        kwargs = service.generate_and_broadcast_recommendation.await_args.kwargs
        assert kwargs["track_id"] == 7
        assert kwargs["track_path"] == "/music/track.flac"

    async def test_play_normal_triggers_recommendation(self, monkeypatch):
        """SIBLING: wiring only the enhanced path leaves normal playback dead."""
        service = MagicMock()
        service.generate_and_broadcast_recommendation = AsyncMock(return_value={})
        factory = MagicMock(return_value=service)
        monkeypatch.setattr(
            "services.recommendation_service.RecommendationService", factory
        )

        deps = _deps()
        await handle_play_normal(
            _ws(), {"type": "play_normal", "data": {"track_id": 9}}, _state(), deps
        )
        await _drain()

        service.generate_and_broadcast_recommendation.assert_awaited_once()
        kwargs = service.generate_and_broadcast_recommendation.await_args.kwargs
        assert kwargs["track_id"] == 9

    async def test_broadcast_manager_is_passed_to_the_service(self, monkeypatch):
        """The service broadcasts to every client, not just this socket."""
        service = MagicMock()
        service.generate_and_broadcast_recommendation = AsyncMock(return_value={})
        factory = MagicMock(return_value=service)
        monkeypatch.setattr(
            "services.recommendation_service.RecommendationService", factory
        )

        deps = _deps()
        await handle_play_enhanced(
            _ws(), {"type": "play_enhanced", "data": {"track_id": 1}}, _state(), deps
        )
        await _drain()

        assert factory.call_args.kwargs["connection_manager"] is deps.broadcast_manager


class TestRecommendationNeverBreaksPlayback:
    """A failed recommendation must not affect the stream."""

    async def test_service_failure_is_swallowed(self, monkeypatch):
        service = MagicMock()
        service.generate_and_broadcast_recommendation = AsyncMock(
            side_effect=RuntimeError("analysis exploded")
        )
        monkeypatch.setattr(
            "services.recommendation_service.RecommendationService",
            MagicMock(return_value=service),
        )

        deps = _deps()
        state = _state()
        # Must not raise, and the stream task must still have been created.
        await handle_play_enhanced(
            _ws(), {"type": "play_enhanced", "data": {"track_id": 3}}, state, deps
        )
        await _drain()

        assert state.active_track_ids, "streaming task was not registered"

    async def test_missing_broadcast_manager_is_a_noop(self, monkeypatch):
        factory = MagicMock()
        monkeypatch.setattr(
            "services.recommendation_service.RecommendationService", factory
        )

        deps = _deps(with_manager=False)
        await handle_play_enhanced(
            _ws(), {"type": "play_enhanced", "data": {"track_id": 4}}, _state(), deps
        )
        await _drain()

        factory.assert_not_called()

    async def test_missing_repository_factory_is_a_noop(self, monkeypatch):
        factory = MagicMock()
        monkeypatch.setattr(
            "services.recommendation_service.RecommendationService", factory
        )

        deps = _deps(with_repos=False)
        await handle_play_enhanced(
            _ws(), {"type": "play_enhanced", "data": {"track_id": 5}}, _state(), deps
        )
        await _drain()

        factory.assert_not_called()

    async def test_track_without_filepath_is_skipped(self, monkeypatch):
        factory = MagicMock()
        monkeypatch.setattr(
            "services.recommendation_service.RecommendationService", factory
        )

        deps = _deps(filepath=None)
        await handle_play_enhanced(
            _ws(), {"type": "play_enhanced", "data": {"track_id": 6}}, _state(), deps
        )
        await _drain()

        factory.assert_not_called()

    async def test_invalid_track_id_does_not_trigger(self, monkeypatch):
        """Rejected before any background work is launched (#2393)."""
        factory = MagicMock()
        monkeypatch.setattr(
            "services.recommendation_service.RecommendationService", factory
        )

        deps = _deps()
        await handle_play_enhanced(
            _ws(), {"type": "play_enhanced", "data": {"track_id": -1}}, _state(), deps
        )
        await _drain()

        factory.assert_not_called()


class TestWiring:
    """The finding was a function with no reachable caller — pin that it has one."""

    def test_live_ws_path_calls_the_service(self):
        source = Path(_BACKEND) / "ws_handlers" / "playback_commands.py"
        text = source.read_text()
        assert "generate_and_broadcast_recommendation" in text, (
            "the WS play path must call the recommendation service (#4542)"
        )

    def test_both_play_handlers_dispatch(self):
        import inspect

        for handler in (handle_play_enhanced, handle_play_normal):
            body = inspect.getsource(handler)
            assert "_generate_mastering_recommendation" in body, (
                f"{handler.__name__} must trigger the mastering recommendation "
                "(#4542 SIBLING — both play paths need it)"
            )

    def test_uses_spawn_background_task_not_fastapi_background_tasks(self):
        """#3553: BackgroundTasks would run the analysis on the event loop.

        Checks for actual *use* (`background_tasks.add_task(...)`) rather than
        the bare word, which appears legitimately in the explanatory comment.
        """
        source = Path(_BACKEND) / "ws_handlers" / "playback_commands.py"
        text = source.read_text()
        assert "spawn_background_task" in text
        assert "background_tasks.add_task" not in text
