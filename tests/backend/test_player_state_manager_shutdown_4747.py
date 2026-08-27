"""The 1 Hz position loop is stopped at lifespan shutdown (#4747).

`PlayerStateManager._position_update_task` was the only long-lived task in the
app lifespan with no symmetric stop. It is started by `set_playing(True)` and
cancelled only by `set_playing(False)`, while `_shutdown_components` tears down
every *other* component explicitly — so shutting the process down mid-playback
left the loop broadcasting `position_changed` against closing WebSockets until
the event loop went away, surfacing as "Task was destroyed but it is pending".

`PlayerStateManager.shutdown()` is the public, idempotent stop, called first in
`_shutdown_components` so nothing below it races a broadcast.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.background_workers import BACKGROUND_WORKER_KEYS  # noqa: E402
from config.startup import _shutdown_components  # noqa: E402
from core.state_manager import PlayerStateManager  # noqa: E402

pytestmark = pytest.mark.asyncio


def _globals(**overrides):
    """A globals_dict with every shutdown participant present and healthy."""
    base = {key: Mock(stop=AsyncMock()) for key in BACKGROUND_WORKER_KEYS}
    base['streamlined_worker'] = Mock(stop=AsyncMock())
    base['processing_engine'] = Mock(stop_worker=AsyncMock(), close_processor_pool=AsyncMock())
    base['audio_player'] = Mock(stop=Mock(), cleanup=Mock())
    base['library_database'] = Mock(shutdown=Mock())
    base['player_state_manager'] = Mock(shutdown=AsyncMock())
    base.update(overrides)
    return base


async def _run(globals_dict):
    with (
        patch("core.processor_factory.get_processor_factory", MagicMock()),
        patch("services.artwork_downloader.close_artwork_downloader", AsyncMock()),
        patch("analysis.fingerprint_generator.shutdown_fingerprint_executor_bounded", AsyncMock()),
    ):
        await _shutdown_components(globals_dict)


class TestLifespanStopsIt:
    async def test_shutdown_is_called(self):
        g = _globals()
        await _run(g)
        g['player_state_manager'].shutdown.assert_awaited_once()

    async def test_it_runs_before_the_components_it_broadcasts_about(self):
        """Ordering is the point: nothing below may race a 1 Hz broadcast."""
        order: list[str] = []
        g = _globals()
        g['player_state_manager'].shutdown = AsyncMock(
            side_effect=lambda: order.append('player_state_manager')
        )
        g['audio_player'].stop = Mock(side_effect=lambda: order.append('audio_player'))
        g['library_database'].shutdown = Mock(side_effect=lambda: order.append('library_database'))

        await _run(g)

        assert order[0] == 'player_state_manager'
        assert order == ['player_state_manager', 'audio_player', 'library_database']

    async def test_a_failure_here_does_not_skip_the_rest(self):
        """Same step-isolation guarantee as every other step (#4569)."""
        g = _globals()
        g['player_state_manager'].shutdown = AsyncMock(side_effect=RuntimeError("boom"))

        await _run(g)

        g['library_database'].shutdown.assert_called_once()
        g['audio_player'].cleanup.assert_called_once()

    async def test_an_absent_manager_is_not_an_error(self):
        """A rolled-back startup may never have built one."""
        g = _globals()
        del g['player_state_manager']

        await _run(g)

        g['library_database'].shutdown.assert_called_once()


class TestTheManagerItself:
    def _manager(self):
        ws = MagicMock()
        ws.broadcast = AsyncMock()
        return PlayerStateManager(ws)

    async def test_shutdown_cancels_a_running_position_task(self):
        manager = self._manager()
        manager._start_position_updates()
        task = manager._position_update_task
        assert task is not None and not task.done()

        await manager.shutdown()

        assert task.cancelled() or task.done()
        assert manager._position_update_task is None

    async def test_no_pending_task_survives_shutdown(self):
        """The actual symptom: a task still pending at loop teardown."""
        manager = self._manager()
        manager._start_position_updates()

        await manager.shutdown()

        pending = [
            t for t in asyncio.all_tasks()
            if t is not asyncio.current_task() and not t.done()
            and 'position_update_loop' in (t.get_name() or '')
        ]
        assert pending == []

    async def test_shutdown_is_idempotent(self):
        manager = self._manager()
        manager._start_position_updates()

        await manager.shutdown()
        await manager.shutdown()  # must not raise

        assert manager._position_update_task is None

    async def test_shutdown_without_playback_is_a_no_op(self):
        """_shutdown_components calls this without knowing if playback ran."""
        manager = self._manager()
        assert manager._position_update_task is None

        await manager.shutdown()

        assert manager._position_update_task is None

    async def test_a_paused_manager_is_already_stopped_and_stays_so(self):
        manager = self._manager()
        manager._start_position_updates()
        await manager._stop_position_updates()

        await manager.shutdown()

        assert manager._position_update_task is None
