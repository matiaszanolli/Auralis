"""
7-band frequency analysis applies a Hann window (#4136).

The 7 band percentages were computed from a rectangular-window FFT while the
spectral features used a Hann-windowed STFT — leakage inflated high-frequency
band energy on transient-rich audio, making the two groups inconsistent. The
band FFT is now Hann-windowed (locally, leaving the shared FFT for dynamics).
"""

import numpy as np

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer

BANDS = [
    "sub_bass_pct", "bass_pct", "low_mid_pct", "mid_pct",
    "upper_mid_pct", "presence_pct", "air_pct",
]


def _analyzer():
    return AudioFingerprintAnalyzer()


def _tone(freq, sr=44100, dur=2.0, amp=0.5):
    t = np.arange(int(sr * dur)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_band_percentages_sum_to_one():
    fp = _analyzer().analyze(_tone(1000), 44100)
    total = sum(fp[b] for b in BANDS)
    assert abs(total - 1.0) < 1e-6  # window applied uniformly -> ratios still sum to 1


def test_high_frequency_tone_lands_in_air_band():
    fp = _analyzer().analyze(_tone(10000), 44100)  # 10 kHz -> air (6-20 kHz)
    assert fp["air_pct"] > 0.5
    assert fp["sub_bass_pct"] < 0.05


def test_band_analysis_is_deterministic():
    sig = _tone(2500)
    fp1 = _analyzer().analyze(sig, 44100)
    fp2 = _analyzer().analyze(sig, 44100)
    for b in BANDS:
        assert abs(fp1[b] - fp2[b]) < 1e-9
