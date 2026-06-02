"""
Regression test: loader.load() preserves ModuleError diagnostic codes (#4114)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`loader.load()` wrapped its whole body in `except Exception -> RuntimeError`,
flattening structured ModuleError raises (ERROR_FFMPEG_TIMEOUT,
ERROR_TRUNCATED_FILE, …) from the loaders and erasing their diagnostic codes on
the player load path. It now passes ModuleError through unchanged (sibling of
the #3695 fix in ffmpeg_loader.py / soundfile_loader.py).

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from unittest.mock import patch

import pytest

from auralis.io.loader import load
from auralis.utils.logging import Code, ModuleError


def test_moduleerror_propagates_unchanged():
    """A ModuleError raised inside load() keeps its type and diagnostic code."""
    err = ModuleError(f"{Code.ERROR_FFMPEG_TIMEOUT}: ffmpeg timed out")
    with patch("auralis.io.loader.load_with_ffmpeg", side_effect=err):
        with pytest.raises(ModuleError) as exc_info:
            load("track.mp3")  # .mp3 routes through the FFmpeg loader

    # Type preserved (not re-wrapped to RuntimeError) and code intact.
    assert str(Code.ERROR_FFMPEG_TIMEOUT) in str(exc_info.value)


def test_truncated_file_code_preserved():
    err = ModuleError(f"{Code.ERROR_TRUNCATED_FILE}: only 2% complete")
    with patch("auralis.io.loader.load_with_ffmpeg", side_effect=err):
        with pytest.raises(ModuleError) as exc_info:
            load("track.opus")

    assert str(Code.ERROR_TRUNCATED_FILE) in str(exc_info.value)


def test_non_moduleerror_still_wraps_in_runtimeerror():
    """Plain exceptions still surface as RuntimeError with context."""
    with patch("auralis.io.loader.load_with_ffmpeg", side_effect=ValueError("bad data")):
        with pytest.raises(RuntimeError) as exc_info:
            load("track.mp3")

    assert not isinstance(exc_info.value, ModuleError)
    assert "Failed to load" in str(exc_info.value)
    assert "bad data" in str(exc_info.value)
