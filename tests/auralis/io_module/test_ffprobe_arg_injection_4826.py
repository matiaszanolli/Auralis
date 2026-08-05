"""
Regression test: ffprobe path argument isolated with '--' (#4826)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both ffprobe invocations passed the file path as the last, bare positional
argument with no `--` end-of-options marker. A filename beginning with `-`
(legal on Linux/macOS) could be parsed by ffprobe as an option instead of
the input path. Both call sites now insert '--' immediately before the
path argument.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from auralis.io import unified_loader
from auralis.io.loaders import ffmpeg_loader


def test_probe_audio_isolates_path_with_double_dash():
    """ffmpeg_loader._probe_audio must place '--' immediately before the path."""
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="{}"))
    with patch.object(ffmpeg_loader.subprocess, "run", mock_run):
        ffmpeg_loader._probe_audio(Path("-show_entries"))

    cmd = mock_run.call_args[0][0]
    assert cmd[-2:] == ["--", "-show_entries"], cmd


def test_get_info_with_ffprobe_isolates_path_with_double_dash():
    """unified_loader._get_info_with_ffprobe must place '--' immediately before the path."""
    probe_json = (
        '{"streams": [{"codec_type": "audio", "sample_rate": "44100", "channels": 2}], '
        '"format": {"duration": "1.0"}}'
    )
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout=probe_json))
    with patch.object(unified_loader, "check_ffprobe", return_value=True), \
         patch.object(unified_loader.subprocess, "run", mock_run):
        unified_loader._get_info_with_ffprobe(Path("-show_entries"))

    cmd = mock_run.call_args[0][0]
    assert cmd[-2:] == ["--", "-show_entries"], cmd
