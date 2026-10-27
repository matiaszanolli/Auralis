"""Regression test: PsychoacousticEQ band gain does not depend on tonality (#5703)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_calculate_target_gains` halved a band's gain when its mean FFT level was
below its own peak minus 20 dB. That asks "does this band hold a partial far
above its average" — tonality, not masking by a neighbour — so the same
target curve was applied at full strength on noisy frames and at half strength
on tonal ones (white noise: 0 bands halved; a 110 Hz harmonic series: 15),
flipping frame to frame on mixed material.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest

from auralis.dsp.eq.psychoacoustic_eq import EQSettings, PsychoacousticEQ

SR = 44100
FFT = 4096


def _eq() -> PsychoacousticEQ:
    return PsychoacousticEQ(EQSettings(sample_rate=SR, fft_size=FFT))


def _noise(seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (0.2 * rng.standard_normal(FFT)).astype(np.float32)


def _harmonics(seed: int = 2) -> np.ndarray:
    t = np.arange(FFT) / SR
    tones = sum(np.sin(2 * np.pi * 110.0 * h * t) / h for h in range(1, 40))
    rng = np.random.default_rng(seed)
    return (0.1 * tones + 0.002 * rng.standard_normal(FFT)).astype(np.float32)


def _target_curve(eq: PsychoacousticEQ) -> np.ndarray:
    return np.linspace(-6.0, 6.0, len(eq.critical_bands))


def test_target_gains_are_the_weighted_curve_whatever_the_frame():
    eq = _eq()
    curve = _target_curve(eq)
    expected = np.clip(
        curve * np.array([b.weight for b in eq.critical_bands]), -12.0, 12.0
    )

    np.testing.assert_allclose(eq._calculate_target_gains(curve), expected)


@pytest.mark.parametrize("frame", [_noise, _harmonics], ids=["noise", "harmonic-series"])
def test_adaptive_gain_is_identical_for_noisy_and_tonal_frames(frame):
    curve = _target_curve(_eq())
    reference = _eq().calculate_adaptive_gains(_eq().analyze_spectrum(_noise()), curve)

    eq = _eq()
    gains = eq.calculate_adaptive_gains(eq.analyze_spectrum(frame()), curve)

    np.testing.assert_allclose(gains, reference)


def test_alternating_tonal_and_noisy_frames_give_a_steady_gain():
    """No frame-to-frame halving: with a fixed curve the smoothed gain only
    moves monotonically toward the target, it never flips with the texture."""
    eq = _eq()
    curve = _target_curve(eq)
    target = eq._calculate_target_gains(curve)

    previous = np.abs(target)  # distance of current_gains (0) from target
    for n in range(40):
        frame = _noise(n) if n % 2 == 0 else _harmonics(n)
        gains = eq.calculate_adaptive_gains(eq.analyze_spectrum(frame), curve)
        distance = np.abs(target - gains)
        assert np.all(distance <= previous + 1e-9), f"frame {n} moved away from target"
        previous = distance

    np.testing.assert_allclose(gains, target, atol=0.05 * np.abs(target).max())


def test_analysis_no_longer_reports_masking_thresholds():
    result = _eq().analyze_spectrum(_harmonics())

    assert "masking_thresholds" not in result
    assert set(result) == {"magnitude_db", "band_energies", "spectrum"}
