"""MasteringFingerprint measures the body of the track, not its first 90 s (#6143)

windows.py says the library fingerprint and the mastering fingerprint must share their analysis
window (a start-of-track window biases loudness by up to 9 dB on ambient intros, #4595). The
mastering side shared only the length and still read from t=0.
"""

import numpy as np
import pytest
import soundfile as sf

from auralis.analysis.fingerprint.body_window import body_window_offset_s
from auralis.analysis.mastering_fingerprint import MasteringFingerprint

SR = 22050


@pytest.fixture
def quiet_intro_then_loud_body(tmp_path):
    """200 s file: a -40 dBFS first half, a -10 dBFS second half."""
    t = np.arange(100 * SR) / SR
    tone = np.sin(2 * np.pi * 440 * t)
    quiet = 10 ** (-40 / 20) * tone * np.sqrt(2)
    loud = 10 ** (-10 / 20) * tone * np.sqrt(2)
    path = tmp_path / "ambient_intro.wav"
    sf.write(path, np.concatenate([quiet, loud]).astype(np.float32), SR, subtype="FLOAT")
    return path


def test_body_offset_matches_the_25d_placement(quiet_intro_then_loud_body):
    # 200 s track: 50 % = 100 s, and a 90 s window starting there still fits.
    assert body_window_offset_s(quiet_intro_then_loud_body) == pytest.approx(100.0, abs=0.01)


def test_body_offset_is_zero_when_the_duration_is_unreadable(tmp_path):
    assert body_window_offset_s(tmp_path / "missing.wav") == 0.0


def test_loudness_comes_from_the_body_not_the_intro(quiet_intro_then_loud_body):
    fp = MasteringFingerprint.from_audio_file(str(quiet_intro_then_loud_body), sr=SR)

    assert fp is not None
    # A head window would read the -40 dBFS intro; the body is the -10 dBFS half.
    assert fp.loudness_dbfs == pytest.approx(-10.0, abs=1.0)
