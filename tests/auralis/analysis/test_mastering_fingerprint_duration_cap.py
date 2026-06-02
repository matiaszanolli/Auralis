"""
Regression test: MasteringFingerprint.from_audio_file() caps decode at 90 s (#4116)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`from_audio_file()` used to call `librosa.load(..., mono=False)` with no
`duration=` cap, decoding an entire multi-hour file into RAM (~14 GB for 6 h
stereo) and risking an OOM-kill on first playback of an uncached track. It now
passes `duration=90.0`, matching every other fingerprint path.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

from unittest.mock import patch

import numpy as np

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
    """Whatever the file length, the requested decode duration is fixed at 90 s."""
    fake = _fake_stereo(5.0)
    with patch(
        "auralis.analysis.mastering_fingerprint.librosa.load",
        return_value=(fake, 44100),
    ) as mock_load:
        MasteringFingerprint.from_audio_file("six_hour_audiobook.mp3")

    _, kwargs = mock_load.call_args
    assert kwargs["duration"] == 90.0
