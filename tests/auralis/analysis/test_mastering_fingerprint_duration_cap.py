"""
Regression test: MasteringFingerprint.from_audio_file() caps decode at 90 s (#4116)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#4890 update: extensions in FFMPEG_FORMATS (mp3/m4a/aac/ogg/wma/opus) no longer
reach librosa.load() at all — they route through load_with_ffmpeg() instead, so
the tests below that assert on librosa.load's call_args now use a
soundfile-native extension (.flac/.wav) that still takes that path. Coverage
for the FFmpeg-routed path lives in TestFFmpegRoutedFormats below.

`from_audio_file()` used to call `librosa.load(..., mono=False)` with no
`duration=` cap, decoding an entire multi-hour file into RAM (~14 GB for 6 h
stereo) and risking an OOM-kill on first playback of an uncached track. It now
passes `duration=90.0`, matching every other fingerprint path.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import shutil
import subprocess
from unittest.mock import patch

import numpy as np
import pytest

from auralis.analysis.mastering_fingerprint import MasteringFingerprint


def _fake_stereo(seconds: float, sr: int = 44100) -> np.ndarray:
    n = int(sr * seconds)
    t = np.arange(n) / sr
    sig = 0.2 * np.sin(2 * np.pi * 220.0 * t)
    return np.stack([sig, sig]).astype(np.float32)  # shape (2, n), mono=False layout


def test_from_audio_file_passes_duration_cap():
    """librosa.load must be called with duration=90.0 (#4116)."""
    fake = _fake_stereo(5.0)
    with patch(
        "auralis.analysis.mastering_fingerprint.librosa.load",
        return_value=(fake, 44100),
    ) as mock_load:
        fp = MasteringFingerprint.from_audio_file("long_dj_mix.flac")

    assert mock_load.call_count == 1
    _, kwargs = mock_load.call_args
    assert kwargs.get("duration") == 90.0, "decode must be capped at 90 s"
    # A valid signal still produces a fingerprint (cap doesn't break extraction).
    assert fp is not None


def test_peak_decode_bounded_independent_of_file_length():
    """Whatever the file length, the requested decode duration is fixed at 90 s.

    .m4a used rather than the original .mp3/.flac split test's extension —
    any soundfile-native extension exercises the direct librosa.load() path;
    .m4a (FFMPEG_FORMATS) would route through load_with_ffmpeg() instead (#4890).
    """
    fake = _fake_stereo(5.0)
    with patch(
        "auralis.analysis.mastering_fingerprint.librosa.load",
        return_value=(fake, 44100),
    ) as mock_load:
        MasteringFingerprint.from_audio_file("six_hour_audiobook.wav")

    _, kwargs = mock_load.call_args
    assert kwargs["duration"] == 90.0


class TestFFmpegRoutedFormats:
    """#4890: m4a/aac/wma (and mp3/ogg/opus) must route through load_with_ffmpeg(),
    never librosa.load() directly — soundfile 0.14.0 can't decode the first
    three, so librosa.load() silently fell through to the audioread backend
    librosa marks for hard removal in 1.0.
    """

    def test_ffmpeg_format_does_not_call_librosa_load_directly(self):
        fake = _fake_stereo(5.0)  # (2, n) at 44100 Hz — already at target sr
        with patch(
            "auralis.io.loaders.load_with_ffmpeg",
            return_value=(fake.T, 44100),  # load_with_ffmpeg returns (samples, channels)
        ) as mock_ffmpeg, patch(
            "auralis.analysis.mastering_fingerprint.librosa.load",
        ) as mock_load:
            fp = MasteringFingerprint.from_audio_file("track.m4a", sr=44100)

        assert mock_ffmpeg.call_count == 1
        mock_load.assert_not_called()
        assert fp is not None

    def test_ffmpeg_decode_is_bounded_to_ninety_seconds(self):
        """The 90 s window is forwarded to ffmpeg itself (-t), so the decode is
        bounded before any buffer exists (#5713) — not cropped afterwards."""
        fake = _fake_stereo(5.0)
        with patch(
            "auralis.io.loaders.load_with_ffmpeg",
            return_value=(fake.T, 44100),
        ) as mock_ffmpeg:
            fp = MasteringFingerprint.from_audio_file("long_track.aac", sr=44100)

        assert fp is not None
        _, kwargs = mock_ffmpeg.call_args
        assert kwargs.get("duration") == 90.0

    def test_ffmpeg_result_longer_than_window_is_still_cropped(self):
        """Safety net: a buffer longer than the window (resampling rounding)
        is sliced to 90 s before analysis."""
        fake = _fake_stereo(120.0)
        seen = {}
        real_stft = __import__("librosa").stft

        def spy_stft(mono, *a, **kw):
            seen["n"] = len(mono)
            return real_stft(mono, *a, **kw)

        with patch(
            "auralis.io.loaders.load_with_ffmpeg",
            return_value=(fake.T, 44100),
        ), patch("auralis.analysis.mastering_fingerprint.librosa.stft", spy_stft):
            fp = MasteringFingerprint.from_audio_file("long_track.aac", sr=44100)

        assert fp is not None
        assert seen["n"] == 90 * 44100

    @pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
    def test_real_ffmpeg_decode_hands_analyzer_at_most_ninety_seconds(self, tmp_path):
        """End to end: a 100 s mp3 reaches the analyzer as <= 90 s of audio."""
        src = tmp_path / "long.mp3"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=100",
             "-ac", "2", str(src)],
            check=True,
        )
        seen = {}
        real_stft = __import__("librosa").stft

        def spy_stft(mono, *a, **kw):
            seen["n"] = len(mono)
            return real_stft(mono, *a, **kw)

        with patch("auralis.analysis.mastering_fingerprint.librosa.stft", spy_stft):
            fp = MasteringFingerprint.from_audio_file(str(src), sr=44100)

        assert fp is not None
        assert 85 * 44100 <= seen["n"] <= 90 * 44100

    @pytest.mark.parametrize("suffix", [".mp3", ".m4a", ".aac", ".ogg", ".wma", ".opus"])
    def test_every_ffmpeg_format_extension_is_routed(self, suffix):
        fake = _fake_stereo(5.0)
        with patch(
            "auralis.io.loaders.load_with_ffmpeg",
            return_value=(fake.T, 44100),
        ) as mock_ffmpeg, patch(
            "auralis.analysis.mastering_fingerprint.librosa.load",
        ) as mock_load:
            MasteringFingerprint.from_audio_file(f"track{suffix}", sr=44100)

        assert mock_ffmpeg.call_count == 1, f"{suffix} did not route through load_with_ffmpeg"
        mock_load.assert_not_called()
