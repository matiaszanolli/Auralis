"""Enhancement pre-warm must not race a live stream for the same track (#5323).

Pre-warm builds its own ChunkedAudioProcessor, which resolves to the same
shared HybridProcessor as the live stream and writes to the same on-disk
chunk path the stream serves as a cache hit — with a fresh LevelManager. The
frontend re-issues the stream on every mid-playback toggle/preset/intensity
change, so while that stream is live, pre-warm is skipped (and stops early if
the stream starts while it is running).

Harness mirrors test_preset_intensity_prewarm_4425.py: the real enhancement
router, with spawn_background_task run synchronously.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.system as system_module
from routers.enhancement import create_enhancement_router
from tests.backend.test_preset_intensity_prewarm_4425 import (
    _make_playing_state_manager,
    _patched_prewarm_chain,
    _run_prewarm_synchronously,
)

TRACK_ID = 1  # _make_playing_state_manager's current track


@pytest.fixture(autouse=True)
def _allow_fake_paths(monkeypatch):
    from pathlib import Path as _Path
    monkeypatch.setattr("routers.enhancement.validate_file_path", lambda filepath, *a, **k: _Path(filepath))


@pytest.fixture
def live_streams(monkeypatch):
    """Register fake streams in system.py's real registries, restored afterwards."""
    monkeypatch.setattr(system_module, "_active_streaming_tasks", {})
    monkeypatch.setattr(system_module, "_active_streaming_track_ids", {})

    def _register(ws_id: str, track_id: int, done: bool = False) -> None:
        task = Mock()
        task.done.return_value = done
        system_module._active_streaming_tasks[ws_id] = task
        system_module._active_streaming_track_ids[ws_id] = track_id

    return _register


def _client() -> TestClient:
    connection_manager = Mock()
    connection_manager.broadcast = AsyncMock()
    router = create_enhancement_router(
        get_enhancement_settings=lambda: {"enabled": True, "preset": "adaptive", "intensity": 1.0},
        connection_manager=connection_manager,
        get_player_state_manager=_make_playing_state_manager,
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _change_intensity(client: TestClient):
    return client.post("/api/player/enhancement/intensity", json={"intensity": 0.5})


def test_no_prewarm_while_the_track_is_live_streaming(live_streams):
    live_streams("ws-a", TRACK_ID)
    p1, p2, p3, _ = _patched_prewarm_chain()
    with _run_prewarm_synchronously() as spawn, p1, p2 as ctor, p3:
        response = _change_intensity(_client())

    assert response.status_code == 200
    spawn.assert_not_called()
    ctor.assert_not_called()


def test_prewarm_still_runs_when_only_another_track_is_streaming(live_streams):
    live_streams("ws-a", TRACK_ID + 1)
    p1, p2, p3, processor = _patched_prewarm_chain()
    with _run_prewarm_synchronously(), p1, p2 as ctor, p3:
        _change_intensity(_client())

    ctor.assert_called_once()
    assert processor.get_wav_chunk_path.call_count == 3


def test_a_finished_stream_does_not_block_prewarm(live_streams):
    live_streams("ws-a", TRACK_ID, done=True)
    p1, p2, p3, processor = _patched_prewarm_chain()
    with _run_prewarm_synchronously(), p1, p2 as ctor, p3:
        _change_intensity(_client())

    ctor.assert_called_once()
    assert processor.get_wav_chunk_path.call_count == 3


def test_prewarm_stops_once_a_live_stream_starts_mid_run(live_streams):
    """The concurrent case: the frontend re-issues the stream while pre-warm runs."""
    p1, p2, p3, processor = _patched_prewarm_chain()

    def _render(chunk_idx):
        live_streams("ws-a", TRACK_ID)  # the re-issued stream registers
        return f"/tmp/chunk_{chunk_idx}.wav"

    processor.get_wav_chunk_path.side_effect = _render
    with _run_prewarm_synchronously(), p1, p2, p3:
        _change_intensity(_client())

    assert processor.get_wav_chunk_path.call_count == 1
    processor.close.assert_called_once()


def test_prewarm_chunk_dsp_runs_on_the_stream_executor(live_streams):
    """#5086 SIBLING: chunk DSP belongs on the streaming pool, not the I/O pool."""
    p1, p2, p3, processor = _patched_prewarm_chain()
    calls = []

    async def _fake_stream_executor(func, *args, **kwargs):
        calls.append(func)
        return func(*args, **kwargs)

    with _run_prewarm_synchronously(), p1, p2, p3, \
         patch("routers.enhancement.run_in_stream_executor", side_effect=_fake_stream_executor):
        _change_intensity(_client())

    assert calls == [processor.get_wav_chunk_path] * 3
