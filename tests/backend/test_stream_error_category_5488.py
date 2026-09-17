"""
Regression tests: streaming entry points surface the safe error category (#5488)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

stream_enhanced.py, stream_normal.py and stream_seek.py each end in an
``except Exception`` that sends an audio_stream_error. They used to send the
literal "Audio streaming failed" for every failure, discarding the specific
category ``_safe_error_message()`` already computes for the job path — so a
corrupt file and a missing decoder looked identical to the user. Unmapped
failures must still read "Audio streaming failed", not the job path's
"unexpected error during processing" fallback.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.utils.logging import Code, ModuleError
from core import stream_enhanced, stream_normal, stream_seek
from core.audio_stream_controller import AudioStreamController

TRACK_ID = 5488

CORRUPT = ModuleError(f"{Code.ERROR_CORRUPTED}: /secret/path.flac")
CORRUPT_MESSAGE = "Audio file is corrupted or unsupported"
GENERIC_MESSAGE = "Audio streaming failed"


def _controller(processor_class: MagicMock | None = None) -> AudioStreamController:
    controller = AudioStreamController(chunked_processor_class=processor_class)
    controller._send_error = AsyncMock()
    controller._is_websocket_connected = MagicMock(return_value=True)
    factory = MagicMock()
    factory.tracks.get_by_id.return_value = MagicMock(filepath="/tmp/fake_5488.wav")
    factory.fingerprints.exists.return_value = False
    controller._get_repository_factory = MagicMock(return_value=factory)
    return controller


def _sent_message(controller: AudioStreamController) -> str:
    controller._send_error.assert_awaited_once()
    return controller._send_error.await_args.args[2]


async def _run_enhanced(exc: Exception) -> AudioStreamController:
    controller = _controller(MagicMock(side_effect=exc))
    with patch.object(stream_enhanced, "validate_file_path", side_effect=lambda p, **_kw: p), \
         patch.object(controller, "_check_or_queue_fingerprint", new=AsyncMock(return_value=False)):
        await stream_enhanced.stream_enhanced_audio(
            controller=controller, track_id=TRACK_ID, preset="adaptive",
            intensity=1.0, websocket=MagicMock(),
        )
    return controller


async def _run_seek(exc: Exception) -> AudioStreamController:
    controller = _controller(MagicMock(side_effect=exc))
    with patch.object(stream_seek, "validate_file_path", side_effect=lambda p, **_kw: p), \
         patch.object(controller, "_check_or_queue_fingerprint", new=AsyncMock(return_value=False)):
        await stream_seek.stream_enhanced_audio_from_position(
            controller=controller, track_id=TRACK_ID, preset="adaptive",
            intensity=1.0, websocket=MagicMock(), start_position=0.0,
        )
    return controller


async def _run_normal(exc: Exception) -> AudioStreamController:
    controller = _controller()
    with patch.object(stream_normal, "validate_file_path", side_effect=lambda p, **_kw: p), \
         patch.object(stream_normal.sf, "SoundFile", side_effect=exc):
        await stream_normal.stream_normal_audio(
            controller=controller, track_id=TRACK_ID, websocket=MagicMock(),
        )
    return controller


RUNNERS = [_run_enhanced, _run_seek, _run_normal]


@pytest.mark.asyncio
@pytest.mark.parametrize("run", RUNNERS, ids=["enhanced", "seek", "normal"])
async def test_specific_category_reaches_client(run):
    controller = await run(CORRUPT)
    message = _sent_message(controller)
    assert message == CORRUPT_MESSAGE
    assert "/secret/path.flac" not in message


@pytest.mark.asyncio
@pytest.mark.parametrize("run", RUNNERS, ids=["enhanced", "seek", "normal"])
async def test_unmapped_failure_keeps_streaming_wording(run):
    controller = await run(RuntimeError("internal detail"))
    assert _sent_message(controller) == GENERIC_MESSAGE


@pytest.mark.asyncio
async def test_seek_keeps_seek_error_code():
    controller = await _run_seek(CORRUPT)
    assert controller._send_error.await_args.kwargs["error_code"] == "SEEK_ERROR"
