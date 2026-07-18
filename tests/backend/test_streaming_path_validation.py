"""Regression tests for streaming endpoints validating track.filepath (#4345).

routers/metadata.py deliberately runs validate_file_path() on DB-sourced
track.filepath "before any file I/O (fixes #2302)". The WebSocket streaming
entry points (stream_normal_audio, stream_enhanced_audio,
stream_enhanced_audio_from_position) — the highest-traffic consumers of
track.filepath — omitted the same guard. They now call validate_file_path()
too, so a filepath outside the allowed directories (Music/Documents/
registered scan folders) is rejected with a clean WS error instead of
reaching file I/O.

conftest.py's autouse `_bypass_streaming_path_validation` fixture stands in
for the real validate_file_path() in most tests (so pre-existing Path.exists
mocks keep working); these tests explicitly restore the real function to
exercise the actual validation boundary.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from core.audio_stream_controller import AudioStreamController
from core import stream_enhanced, stream_normal, stream_seek

TRACK_ID = 42


def _make_ws() -> Mock:
    ws = Mock()
    ws.client_state = Mock()
    ws.client_state.name = "CONNECTED"
    ws.send_text = AsyncMock()
    return ws


def _make_factory(filepath: str) -> Mock:
    factory = Mock(spec=["tracks", "fingerprints"])
    track = Mock()
    track.id = TRACK_ID
    track.filepath = filepath
    factory.tracks.get_by_id = Mock(return_value=track)
    factory.fingerprints.exists = Mock(return_value=False)
    return factory


def _restore_real_validate_file_path(monkeypatch):
    """Undo conftest's bypass so these tests exercise the real function."""
    from security.path_security import validate_file_path

    monkeypatch.setattr("core.stream_normal.validate_file_path", validate_file_path)
    monkeypatch.setattr("core.stream_enhanced.validate_file_path", validate_file_path)
    monkeypatch.setattr("core.stream_seek.validate_file_path", validate_file_path)


def _sent_error_messages(ws: Mock) -> list[str]:
    messages = []
    for call in ws.send_text.call_args_list:
        import json
        data = json.loads(call.args[0])
        if data.get("type") == "audio_stream_error":
            messages.append(data.get("data", {}).get("message", ""))
    return messages


@pytest.mark.asyncio
async def test_stream_normal_rejects_path_outside_allowed_dirs(monkeypatch):
    _restore_real_validate_file_path(monkeypatch)

    controller = AudioStreamController()
    controller._get_repository_factory = lambda: _make_factory("/etc/passwd")
    ws = _make_ws()

    await stream_normal.stream_normal_audio(controller, TRACK_ID, ws, 0.0)

    errors = _sent_error_messages(ws)
    assert errors, "expected a clean audio_stream_error, not an unhandled exception"


@pytest.mark.asyncio
async def test_stream_enhanced_rejects_path_outside_allowed_dirs(monkeypatch):
    _restore_real_validate_file_path(monkeypatch)

    controller = AudioStreamController()
    controller._stream_semaphore = asyncio.Semaphore(2)
    controller.chunked_processor_class = Mock()
    controller._get_repository_factory = lambda: _make_factory("/etc/passwd")
    ws = _make_ws()

    await stream_enhanced.stream_enhanced_audio(controller, TRACK_ID, "adaptive", 1.0, ws)

    errors = _sent_error_messages(ws)
    assert errors, "expected a clean audio_stream_error, not an unhandled exception"


@pytest.mark.asyncio
async def test_stream_seek_rejects_path_outside_allowed_dirs(monkeypatch):
    _restore_real_validate_file_path(monkeypatch)

    controller = AudioStreamController()
    controller._stream_semaphore = asyncio.Semaphore(2)
    controller.chunked_processor_class = Mock()
    controller._get_repository_factory = lambda: _make_factory("/etc/passwd")
    ws = _make_ws()

    await stream_seek.stream_enhanced_audio_from_position(
        controller, TRACK_ID, "adaptive", 1.0, ws, 5.0
    )

    errors = _sent_error_messages(ws)
    assert errors, "expected a clean audio_stream_error, not an unhandled exception"


@pytest.mark.asyncio
async def test_stream_normal_accepts_valid_in_library_path(monkeypatch, tmp_path):
    """Regression: a legitimate in-library filepath still streams normally."""
    _restore_real_validate_file_path(monkeypatch)

    from security.path_security import register_allowed_directory, unregister_allowed_directory

    music_dir = tmp_path / "Music"
    music_dir.mkdir()
    track_file = music_dir / "track.wav"

    import numpy as np
    from auralis.io.saver import save as save_audio
    save_audio(str(track_file), np.zeros((44100, 2), dtype=np.float32), 44100, subtype='PCM_16')

    register_allowed_directory(music_dir)
    try:
        controller = AudioStreamController()
        controller._get_repository_factory = lambda: _make_factory(str(track_file))
        ws = _make_ws()

        await stream_normal.stream_normal_audio(controller, TRACK_ID, ws, 0.0)

        errors = _sent_error_messages(ws)
        assert not errors, f"valid in-library path should stream, got errors: {errors}"
    finally:
        unregister_allowed_directory(music_dir)
