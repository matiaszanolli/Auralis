"""A transient FFmpeg probe failure is not cached for the process lifetime (#6318)

check_ffmpeg()/check_ffprobe() were lru_cached, so one slow first spawn (a 10 s timeout on a
cold disk) disabled every FFmpeg format until restart, and a PermissionError escaped as a raw
exception. Only definitive answers are cached now.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from auralis.io.loaders import ffmpeg_probe

OK = MagicMock(returncode=0, stdout="ffmpeg version 7.0 Copyright", stderr="")


@pytest.fixture(autouse=True)
def _fresh_cache():
    ffmpeg_probe.check_ffmpeg.cache_clear()
    ffmpeg_probe.check_ffprobe.cache_clear()
    yield
    ffmpeg_probe.check_ffmpeg.cache_clear()
    ffmpeg_probe.check_ffprobe.cache_clear()


@pytest.mark.parametrize("name", ["check_ffmpeg", "check_ffprobe"])
def test_a_timeout_is_retried_not_remembered(name):
    probe = getattr(ffmpeg_probe, name)
    with patch.object(ffmpeg_probe.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 10)):
        assert probe() is False
    with patch.object(ffmpeg_probe.subprocess, "run", return_value=OK):
        assert probe() is True  # the binary was fine; the first spawn was just slow


@pytest.mark.parametrize("name", ["check_ffmpeg", "check_ffprobe"])
def test_a_permission_error_reports_unavailable_instead_of_raising(name):
    with patch.object(ffmpeg_probe.subprocess, "run", side_effect=PermissionError("not executable")):
        assert getattr(ffmpeg_probe, name)() is False


@pytest.mark.parametrize("name", ["check_ffmpeg", "check_ffprobe"])
def test_a_definitive_answer_is_cached(name):
    probe = getattr(ffmpeg_probe, name)
    with patch.object(ffmpeg_probe.subprocess, "run", return_value=OK) as run:
        assert probe() is True
        assert probe() is True
    assert run.call_count == 1


def test_a_missing_binary_is_cached_as_absent():
    with patch.object(ffmpeg_probe.subprocess, "run", side_effect=FileNotFoundError) as run:
        assert ffmpeg_probe.check_ffmpeg() is False
        assert ffmpeg_probe.check_ffmpeg() is False
    assert run.call_count == 1
