"""
Regression tests: transport engine calls do not queue behind the I/O pool (#6093).

``PlaybackService`` holds the process-wide transition lock across the engine's
play/pause/stop/seek call. On the shared default pool that call queued behind
whatever else saturated it (library scan, repository calls), so the lock stayed
held and every WS transport handler waiting on it inside its receive loop (flow
control, pongs) stalled with it.
"""

import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import executors
from services.playback_service import PlaybackService


@pytest.fixture(autouse=True)
async def _pools():
    executors.shutdown_executors()
    executors.install_executors()
    try:
        yield
    finally:
        executors.shutdown_executors()


async def _saturate_io_pool(release: threading.Event) -> list["asyncio.Future[None]"]:
    """Occupy every worker of the default (I/O) pool with a blocking call."""
    loop = asyncio.get_running_loop()
    started = threading.Barrier(executors.IO_POOL_SIZE + 1)

    def _block() -> None:
        started.wait(timeout=5)
        release.wait(timeout=30)

    futures = [loop.run_in_executor(None, _block) for _ in range(executors.IO_POOL_SIZE)]
    # Wait on the transport pool: the I/O pool is exactly what is being filled.
    await loop.run_in_executor(executors.get_transport_executor(), started.wait, 5)
    return futures


def _service() -> tuple[PlaybackService, MagicMock]:
    player = MagicMock()
    state_manager = MagicMock()
    state_manager.set_playing = AsyncMock(return_value=None)
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()
    return PlaybackService(player, state_manager, connection_manager), player


@pytest.mark.asyncio
async def test_pause_completes_while_the_io_pool_is_fully_blocked():
    release = threading.Event()
    blockers = await _saturate_io_pool(release)
    try:
        service, player = _service()

        result = await asyncio.wait_for(service.pause(), timeout=1)

        assert result["state"] == "paused"
        player.pause.assert_called_once()
    finally:
        release.set()
        await asyncio.gather(*blockers)


@pytest.mark.asyncio
async def test_every_transport_command_runs_on_the_transport_pool():
    service, player = _service()
    seen: dict[str, str] = {}
    for name in ("play", "pause", "stop", "seek"):
        getattr(player, name).side_effect = lambda *a, n=name: seen.__setitem__(
            n, threading.current_thread().name
        )

    await service.play()
    await service.pause()
    await service.stop()
    await service.seek(1.0)

    assert set(seen) == {"play", "pause", "stop", "seek"}
    assert all(thread.startswith("auralis-transport") for thread in seen.values()), seen


@pytest.mark.asyncio
async def test_transport_pool_is_installed_sized_and_torn_down():
    pool = executors.get_transport_executor()
    assert pool is not None
    assert pool._max_workers == executors.TRANSPORT_POOL_SIZE
    assert executors.install_executors() is not None
    assert executors.get_transport_executor() is pool  # idempotent

    executors.shutdown_executors()

    assert executors.get_transport_executor() is None


@pytest.mark.asyncio
async def test_falls_back_to_the_default_executor_when_no_pool_is_installed():
    executors.shutdown_executors()

    ran_on = await executors.run_in_transport_executor(lambda: threading.current_thread().name)

    assert isinstance(ran_on, str) and ran_on
