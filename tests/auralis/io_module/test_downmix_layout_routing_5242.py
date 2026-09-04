"""Non-canonical multichannel layouts use FFmpeg metadata (#5242)."""

import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from auralis.io import loader as player_loader
from auralis.io.loaders import ffmpeg_loader, soundfile_loader

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _file_info(channels: int) -> SimpleNamespace:
    return SimpleNamespace(
        duration=0.001,
        samplerate=48_000,
        channels=channels,
        frames=48,
    )


@pytest.mark.parametrize("channels", [4, 5, 7])
def test_player_loader_routes_unknown_layout_before_native_decode(
    channels: int, monkeypatch
) -> None:
    expected = np.full((48, 2), 0.25, dtype=np.float32)
    ffmpeg_decode = Mock(return_value=(expected, 48_000))
    native_decode = Mock()
    warnings: list[str] = []

    monkeypatch.setattr(player_loader.sf, "info", lambda _path: _file_info(channels))
    monkeypatch.setattr(player_loader.sf, "read", native_decode)
    monkeypatch.setattr(player_loader, "load_with_ffmpeg", ffmpeg_decode)
    monkeypatch.setattr(player_loader, "warning", warnings.append)

    audio, sample_rate = player_loader.load("surround.wav")

    ffmpeg_decode.assert_called_once_with(player_loader.Path("surround.wav"))
    native_decode.assert_not_called()
    assert audio is expected
    assert sample_rate == 48_000
    assert str(channels) in warnings[0]
    assert "canonical 5.1/7.1" in warnings[0]


@pytest.mark.parametrize("channels", [4, 5, 7])
def test_soundfile_loader_routes_unknown_layout_before_native_decode(
    channels: int, monkeypatch, tmp_path
) -> None:
    source = tmp_path / "surround.wav"
    source.write_bytes(b"not-a-wave-file")
    expected = np.full((48, 2), 0.25, dtype=np.float32)
    ffmpeg_decode = Mock(return_value=(expected, 48_000))
    native_decode = Mock()
    warnings: list[str] = []

    monkeypatch.setattr(
        soundfile_loader.sf, "info", lambda _path: _file_info(channels)
    )
    monkeypatch.setattr(soundfile_loader.sf, "read", native_decode)
    monkeypatch.setattr(ffmpeg_loader, "load_with_ffmpeg", ffmpeg_decode)
    monkeypatch.setattr(soundfile_loader, "warning", warnings.append)

    audio, sample_rate = soundfile_loader.load_with_soundfile(source)

    ffmpeg_decode.assert_called_once_with(source)
    native_decode.assert_not_called()
    assert audio is expected
    assert sample_rate == 48_000
    assert str(channels) in warnings[0]
    assert "canonical 5.1/7.1" in warnings[0]


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not available")
@pytest.mark.parametrize(
    ("channels", "layout", "expression"),
    [
        (4, "quad", "0|0|0.25|0"),       # back-left is channel 2
        (5, "5.0", "0|0|0|0.25|0"),      # back-left is channel 3
        (7, "6.1", "0|0|0|0|0|0.25|0"),  # side-left is channel 5
    ],
)
def test_layout_metadata_routes_left_surround_to_left_output(
    channels: int, layout: str, expression: str, tmp_path
) -> None:
    """Real layout-tagged files retain the surround channel's side."""
    source = tmp_path / f"layout-{channels}.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"aevalsrc={expression}:d=0.1:s=48000:c={layout}",
            "-c:a",
            "pcm_f32le",
            "-y",
            str(source),
        ],
        check=True,
        capture_output=True,
    )

    audio, sample_rate = soundfile_loader.load_with_soundfile(source)

    assert sample_rate == 48_000
    assert float(np.max(np.abs(audio[:, 0]))) > 0.01
    assert float(np.max(np.abs(audio[:, 1]))) < 1e-5
