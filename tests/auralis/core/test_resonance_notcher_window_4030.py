"""
ResonanceNotcher PSD window scales with sample rate (#4030).

A fixed N=16384 made the PSD frequency resolution sample-rate-dependent
(~1.35 Hz/bin at 22 kHz vs ~5.9 Hz/bin at 96 kHz). The window is now anchored in
time (RESONANCE_FFT_WINDOW_SECONDS), reproducing N=16384 at 44.1 kHz while
keeping resolution from degrading at higher rates.
"""

import numpy as np

from auralis.core.dsp.resonance_notcher import (
    RESONANCE_FFT_WINDOW_SECONDS,
    ResonanceNotcher,
)


def _signal(sample_rate, duration=3.0, freq=500.0):
    rng = np.random.RandomState(0)
    n = int(sample_rate * duration)
    t = np.arange(n) / sample_rate
    noise = rng.randn(n) * 0.01
    tone = 0.5 * np.sin(2 * np.pi * freq * t)  # narrow, prominent resonance
    return (noise + tone).astype(np.float32)


def test_window_seconds_reproduces_16384_at_44100():
    """The historical 44.1 kHz path must be unchanged (N == 16384)."""
    sr = 44100
    target = int(RESONANCE_FFT_WINDOW_SECONDS * sr)
    n = max(4096, 1 << (target - 1).bit_length())
    assert n == 16384


def test_detects_planted_resonance_across_sample_rates():
    for sr in (44100, 48000):
        notches = ResonanceNotcher.detect(_signal(sr), sr)
        freqs = [notch.freq_hz for notch in notches]
        assert any(abs(f - 500.0) < 30.0 for f in freqs), f"sr={sr} -> {freqs}"
