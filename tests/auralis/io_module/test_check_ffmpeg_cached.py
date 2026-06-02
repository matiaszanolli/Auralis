"""
Regression test: check_ffmpeg() is memoized for the process (#4117)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`check_ffmpeg()` ran `ffmpeg -version` as a subprocess on every call, and
`load_with_ffmpeg` invokes it per file load — so an N-file FFmpeg-routed scan
forked N redundant probes. Availability is constant within a process, so it is
now cached via functools.lru_cache(maxsize=1).

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from unittest.mock import MagicMock, patch

import pytest

from auralis.io.loaders import ffmpeg_loader


@pytest.fixture(autouse=True)
def _clear_cache():
    # Other tests / imports may have populated the cache; start clean and leave
    # it clean so we don't pin a patched result for later tests.
    ffmpeg_loader.check_ffmpeg.cache_clear()
    yield
    ffmpeg_loader.check_ffmpeg.cache_clear()


def test_probe_runs_once_across_many_calls():
    """N calls must spawn exactly one `ffmpeg -version` subprocess (#4117)."""
    with patch.object(ffmpeg_loader.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        results = [ffmpeg_loader.check_ffmpeg() for _ in range(50)]

    assert all(results) is True
    assert mock_run.call_count == 1


def test_cache_clear_forces_reprobe():
    """cache_clear() re-probes (so availability-toggling tests can reset)."""
    with patch.object(ffmpeg_loader.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert ffmpeg_loader.check_ffmpeg() is True
        ffmpeg_loader.check_ffmpeg.cache_clear()
        ffmpeg_loader.check_ffmpeg()

    assert mock_run.call_count == 2


def test_missing_ffmpeg_returns_false():
    with patch.object(ffmpeg_loader.subprocess, "run", side_effect=FileNotFoundError):
        assert ffmpeg_loader.check_ffmpeg() is False
