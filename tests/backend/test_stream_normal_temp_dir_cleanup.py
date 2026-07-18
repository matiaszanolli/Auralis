"""Regression test for orphaned temp dir on FFmpeg-decode failure (#4365).

On the compressed-format normal-streaming path, `tempfile.mkdtemp(prefix=
'auralis_stream_')` creates the dir, but `temp_wav_path` is only assigned
after `load_audio` + `sf.write` succeed. If `load_audio` raises (corrupt/
unsupported file, FFmpeg error), `temp_wav_path` stayed `None`, so the
`finally` (`if temp_wav_path:`) skipped `shutil.rmtree` and the freshly
created dir was orphaned. The fix tracks `temp_dir` itself (assigned at
creation time) instead of deriving the cleanup target from `temp_wav_path`.
"""

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
