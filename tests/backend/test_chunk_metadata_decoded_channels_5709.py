"""
Regression: stream metadata advertises the channel count the chunks carry (#5709)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``load_audio_metadata`` stored the container's channel count, but a file that
libsndfile cannot open (.m4a/.aac/.wma) is converted through FFmpeg, which folds
anything wider than stereo to two channels. ``audio_stream_start.channels`` then
said 6 while every chunk was 2-channel, and the client deinterleaved garbage.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import chunk_metadata
from core.chunk_metadata import load_audio_metadata

from auralis.io.loaders.ffmpeg_command import build_ffmpeg_cmd
from auralis.io.processing import decoded_channel_count
from auralis.io.unified_loader import load_audio

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _encode_m4a(path: Path, channels: int, layout: str) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration=1:sample_rate=44100,pan={layout}|{'|'.join(f'c{i}=c0' for i in range(channels))}",
         "-c:a", "aac", str(path)],
        check=True,
    )


@pytest.mark.parametrize("native,expected", [(1, 1), (2, 2), (3, 2), (6, 2), (8, 2)])
def test_decoded_channel_count_is_the_downmix_rule(native, expected):
    assert decoded_channel_count(native) == expected


@pytest.mark.parametrize("native", [1, 2, 6])
def test_the_ffmpeg_command_downmixes_exactly_when_the_rule_changes_the_count(native):
    argv = build_ffmpeg_cmd("in.m4a", Path("out.wav"), 44100, native, None, None)

    assert ("-ac" in argv) == (decoded_channel_count(native) != native)


@needs_ffmpeg
def test_a_six_channel_m4a_advertises_two_channels_and_decodes_to_two(tmp_path):
    source = tmp_path / "surround.m4a"
    _encode_m4a(source, 6, "5.1")

    decoded, _ = load_audio(str(source))

    assert load_audio_metadata(str(source)).channels == 2
    assert decoded.shape[1] == 2


@needs_ffmpeg
def test_a_stereo_m4a_is_unchanged(tmp_path):
    source = tmp_path / "stereo.m4a"
    _encode_m4a(source, 2, "stereo")

    assert load_audio_metadata(str(source)).channels == 2


@needs_ffmpeg
def test_a_mono_m4a_stays_mono(tmp_path):
    source = tmp_path / "mono.m4a"
    _encode_m4a(source, 1, "mono")

    assert load_audio_metadata(str(source)).channels == 1


def test_a_native_multichannel_wav_keeps_its_own_count(tmp_path):
    source = tmp_path / "surround.wav"
    sf.write(source, np.zeros((4410, 6), dtype=np.float32), 44100)

    assert load_audio_metadata(str(source)).channels == 6


def test_the_probe_decides_by_what_libsndfile_can_open(tmp_path):
    source = tmp_path / "x.wav"
    sf.write(source, np.zeros((4410, 6), dtype=np.float32), 44100)

    with patch.object(chunk_metadata, "can_seek_natively", return_value=False):
        assert load_audio_metadata(str(source)).channels == 2
