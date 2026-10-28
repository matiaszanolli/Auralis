"""The ffmpeg temp WAV can be RF64 (#5566).

A plain RIFF has a 32-bit size field; the decode budget admits up to 6 GiB of float32, so past 4 GiB
the size wrapped and libsndfile read only the wrapped frame count - the track was silently truncated.
`-rf64 auto` keeps small files plain RIFF and switches to RF64 when needed.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import soundfile as sf

from auralis.io.loaders.ffmpeg_command import build_ffmpeg_cmd


def test_the_command_asks_for_rf64_auto_before_the_output_path():
    cmd = build_ffmpeg_cmd("/music/in.m4a", Path("/tmp/out.wav"), 44100, 2, None, None)

    assert cmd[cmd.index("-rf64") + 1] == "auto"
    assert cmd.index("-rf64") < cmd.index("/tmp/out.wav")  # an output option, not an input one


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_ffmpeg_accepts_the_flag_and_small_output_stays_readable(tmp_path):
    source = tmp_path / "in.flac"
    sf.write(str(source), [[0.1, 0.1]] * 4410, 44100)
    out = tmp_path / "out.wav"

    cmd = build_ffmpeg_cmd(str(source), out, 44100, 2, None, None)
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert sf.info(str(out)).frames == 4410
    assert out.read_bytes()[:4] == b"RIFF"  # small files are not forced to RF64
