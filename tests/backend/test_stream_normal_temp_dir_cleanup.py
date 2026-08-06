"""Regression test for orphaned temp dir on FFmpeg-decode failure (#4365).

On the compressed-format normal-streaming path, `tempfile.mkdtemp(prefix=
'auralis_stream_')` creates the dir, but `temp_wav_path` is only assigned
after `load_audio` + `sf.write` succeed. If `load_audio` raises (corrupt/
unsupported file, FFmpeg error), `temp_wav_path` stayed `None`, so the
`finally` (`if temp_wav_path:`) skipped `shutil.rmtree` and the freshly
created dir was orphaned. The fix tracks `temp_dir` itself (assigned at
creation time) instead of deriving the cleanup target from `temp_wav_path`.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.audio_stream_controller import AudioStreamController  # noqa: E402
from core import stream_normal  # noqa: E402

TRACK_ID = 1
FILEPATH = "/tmp/fake_track.mp3"  # .mp3 -> FFMPEG_FORMATS -> mkdtemp path


def _make_ws() -> Mock:
    ws = Mock()
    ws.client_state = Mock()
    ws.client_state.name = "CONNECTED"
    ws.send_text = AsyncMock()
    return ws


def _make_factory() -> Mock:
    factory = Mock(spec=["tracks", "fingerprints"])
    track = Mock()
    track.id = TRACK_ID
    track.filepath = FILEPATH
    factory.tracks.get_by_id = Mock(return_value=track)
    return factory


@pytest.mark.asyncio
async def test_temp_dir_removed_when_load_audio_fails():
    controller = AudioStreamController()
    controller._get_repository_factory = lambda: _make_factory()

    created_dirs: list[str] = []
    real_mkdtemp = __import__("tempfile").mkdtemp

    def _tracking_mkdtemp(*args, **kwargs):
        d = real_mkdtemp(*args, **kwargs)
        created_dirs.append(d)
        return d

    with (
        patch("tempfile.mkdtemp", side_effect=_tracking_mkdtemp),
        patch("auralis.io.unified_loader.load_audio", side_effect=RuntimeError("decode failed")),
        patch("pathlib.Path.exists", return_value=True),
    ):
        await stream_normal.stream_normal_audio(controller, TRACK_ID, _make_ws(), 0.0)

    assert created_dirs, "mkdtemp was never called — test setup didn't reach the ffmpeg branch"
    for d in created_dirs:
        assert not Path(d).exists(), f"orphaned temp dir left behind: {d}"


@pytest.mark.asyncio
async def test_temp_dir_cleanup_offloaded_via_to_thread():
    """#4754: the finally-block shutil.rmtree() of the temp WAV dir (which
    can hold a full decoded WAV, hundreds of MB) used to run directly on the
    event loop. Asserted directly against asyncio.to_thread's call args
    rather than via wall-clock timing (a canary-coroutine race would
    interleave around stream_normal_audio's other, earlier await points
    regardless of whether rmtree itself blocks — a timing assertion here
    would pass even against the pre-fix code for the wrong reason).

    Unlike test_temp_dir_removed_when_load_audio_fails above (where
    load_audio fails INSIDE convert_to_temp_wav, which cleans up its own
    directory itself and leaves the outer `temp_dir` None — the cleanup
    site this test targets never even runs there), this makes
    convert_to_temp_wav succeed so `temp_dir` is set, then lets a later
    step fail (sf.SoundFile() on a nonexistent converted path) to reach the
    finally block with real cleanup work to do.
    """
    import tempfile as _tempfile

    controller = AudioStreamController()
    controller._get_repository_factory = lambda: _make_factory()

    fake_temp_dir = _tempfile.mkdtemp(prefix="auralis_stream_test_")
    fake_wav_path = str(Path(fake_temp_dir) / "converted.wav")  # never created — sf.SoundFile() will raise

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "core.seekable_source.convert_to_temp_wav",
            return_value=(fake_temp_dir, fake_wav_path),
        ),
        patch("shutil.rmtree") as mock_rmtree,
        patch("asyncio.to_thread", wraps=asyncio.to_thread) as mock_to_thread,
    ):
        await stream_normal.stream_normal_audio(controller, TRACK_ID, _make_ws(), 0.0)

    assert mock_rmtree.called, "rmtree was never invoked — test didn't reach cleanup"
    to_thread_calls_with_rmtree = [
        call for call in mock_to_thread.call_args_list if call.args and call.args[0] is mock_rmtree
    ]
    assert to_thread_calls_with_rmtree, (
        "shutil.rmtree must be offloaded via asyncio.to_thread, not called "
        "directly on the event loop (#4754)"
    )

    # Cleanup the real dir this test created (mock_rmtree never actually ran).
    import shutil as _shutil
    _shutil.rmtree(fake_temp_dir, ignore_errors=True)
