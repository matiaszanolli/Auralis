"""
Regression test: ffprobe absence is reported clearly (#4119)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

_probe_audio caught (TimeoutExpired, JSONDecodeError, ValueError) but not
FileNotFoundError, so a missing ffprobe binary escaped and was mislabeled
ERROR_FFMPEG_CONVERSION by load_with_ffmpeg's outer handler. ffprobe is now
guarded (check_ffprobe, cached like check_ffmpeg) so its absence surfaces as
ERROR_FFMPEG_NOT_FOUND, and _probe_audio catches FileNotFoundError defensively.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from auralis.io.loaders import ffmpeg_loader
from auralis.utils.logging import Code, ModuleError


@pytest.fixture(autouse=True)
def _clear_caches():
    ffmpeg_loader.check_ffmpeg.cache_clear()
    ffmpeg_loader.check_ffprobe.cache_clear()
    yield
    ffmpeg_loader.check_ffmpeg.cache_clear()
    ffmpeg_loader.check_ffprobe.cache_clear()


def test_check_ffprobe_false_when_missing():
    with patch.object(ffmpeg_loader.subprocess, "run", side_effect=FileNotFoundError):
        assert ffmpeg_loader.check_ffprobe() is False


def test_check_ffprobe_true_when_present():
    with patch.object(ffmpeg_loader.subprocess, "run", return_value=MagicMock(returncode=0)):
        assert ffmpeg_loader.check_ffprobe() is True


def test_probe_audio_does_not_let_filenotfound_escape():
    """A missing ffprobe binary must not raise out of _probe_audio."""
    with patch.object(ffmpeg_loader.subprocess, "run", side_effect=FileNotFoundError):
        result = ffmpeg_loader._probe_audio(Path("track.mp3"))

    # Degrades to the empty probe dict instead of raising.
    assert result == {"duration": None, "sample_rate": None, "channels": None}


def test_load_with_ffmpeg_reports_ffprobe_not_found(tmp_path):
    """ffmpeg present but ffprobe absent -> ERROR_FFMPEG_NOT_FOUND, not CONVERSION."""
    audio = tmp_path / "track.mp3"
    audio.write_bytes(b"\x00" * 16)

    with patch.object(ffmpeg_loader, "check_ffmpeg", return_value=True), \
         patch.object(ffmpeg_loader, "check_ffprobe", return_value=False):
        with pytest.raises(ModuleError) as exc_info:
            ffmpeg_loader.load_with_ffmpeg(audio)

    msg = str(exc_info.value)
    assert str(Code.ERROR_FFMPEG_NOT_FOUND) in msg
    assert str(Code.ERROR_FFMPEG_CONVERSION) not in msg
    assert "ffprobe" in msg
