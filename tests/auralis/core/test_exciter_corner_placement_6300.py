"""The harmonic exciter places its corners where configured (#6300 follow-up)

It kept the old ``min(0.99, max(0.01, f / nyquist))`` clamp that #6300 removed from the other
filters, so a corner below 1 % of Nyquist (220 Hz at 44.1 kHz) was silently moved up to it.
Corners now go through ``normalized_corner``.
"""

import numpy as np
import pytest

import auralis.core.dsp.harmonic_exciter as exciter_module
from auralis.core.dsp import HarmonicExciter

SR = 44100


def test_corners_below_the_old_floor_reach_butter_unmoved(monkeypatch: pytest.MonkeyPatch):
    real_butter = exciter_module.butter
    corners: list = []

    def recording_butter(order, wn, **kwargs):
        corners.append(wn)
        return real_butter(order, wn, **kwargs)

    monkeypatch.setattr(exciter_module, "butter", recording_butter)
    audio = (np.random.default_rng(6300).standard_normal((SR // 2, 2)) * 0.1).astype(np.float32)

    out = HarmonicExciter.apply(
        audio, SR, wet_db=-12.0, donor_low_hz=100.0, donor_high_hz=4000.0, hp_cutoff_hz=150.0
    )

    band, high_pass = corners
    assert band[0] == pytest.approx(2 * 100.0 / SR)   # was clamped to 0.01 (220.5 Hz)
    assert band[1] == pytest.approx(2 * 4000.0 / SR)
    assert high_pass == pytest.approx(2 * 150.0 / SR)  # was clamped to 0.01
    assert out.shape == audio.shape and np.isfinite(out).all()
