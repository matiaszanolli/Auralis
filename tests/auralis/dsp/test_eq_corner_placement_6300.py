"""EQ corners land where they are configured, at every sample rate (#6300).

``ParallelEQUtilities`` and ``adjust_stereo_width_multiband`` clamped each corner
with ``max(0.01, f / nyquist)``. ``0.01 * nyquist`` is 220.5 Hz at 44.1 kHz and
960 Hz at 192 kHz, so the offline chain's 60/120/150/200 Hz corners all acted at
220 Hz, and the widener's 300 Hz "lows stay mono" edge moved up at >= 88.2 kHz.
#4211 fixed the same floor for the sub-bass HP only.

Measurement: the filters run zero-phase (``sosfiltfilt``), so a sine comes out
in phase with a scalar gain. An order-2 Butterworth through filtfilt has
``|H|^2 = 0.5`` exactly at its corner, so the parallel shelf/band's share
``w(f) = (gain(f) - 1) / (g - 1)`` crosses 0.5 at the corner: bracketing that
crossing between 0.98 fc and 1.02 fc pins the corner to within 2 %.
"""

from __future__ import annotations

import numpy as np
import pytest

from auralis.core.dsp.parallel_eq import ParallelEQUtilities
from auralis.dsp.utils.filters import normalized_corner
from auralis.dsp.utils.stereo import adjust_stereo_width_multiband

BOOST_DB = 6.0
G = 10 ** (BOOST_DB / 20)


def _sine(freq_hz: float, sr: int, seconds: float = 2.0) -> np.ndarray:
    t = np.arange(int(sr * seconds)) / sr
    return np.stack([np.sin(2 * np.pi * freq_hz * t)] * 2).astype(np.float64)


def _gain(out: np.ndarray, x: np.ndarray, sr: int) -> float:
    mid = slice(sr // 2, -sr // 2)  # skip the filtfilt edge transients
    return float(np.sqrt(np.mean(out[0, mid] ** 2) / np.mean(x[0, mid] ** 2)))


def _share(apply, freq_hz: float, sr: int) -> float:
    """The filtered band's weight in the parallel sum at ``freq_hz`` (0..1)."""
    x = _sine(freq_hz, sr)
    return (_gain(apply(x), x, sr) - 1.0) / (G - 1.0)


@pytest.mark.parametrize("sr", [44100, 48000, 96000])
@pytest.mark.parametrize("fc", [60.0, 120.0])
def test_low_shelf_corner_lands_on_the_requested_frequency(sr, fc):
    def apply(x):
        return ParallelEQUtilities.apply_low_shelf_boost(x, BOOST_DB, fc, sr)

    assert _share(apply, 0.98 * fc, sr) > 0.5 > _share(apply, 1.02 * fc, sr)


@pytest.mark.parametrize("sr", [44100, 48000, 96000])
@pytest.mark.parametrize("low_hz,high_hz", [(150.0, 400.0), (200.0, 800.0)])
def test_bandpass_low_edge_lands_on_the_requested_frequency(sr, low_hz, high_hz):
    def apply(x):
        return ParallelEQUtilities.apply_bandpass_boost(x, BOOST_DB, low_hz, high_hz, sr)

    assert _share(apply, 0.98 * low_hz, sr) < 0.5 < _share(apply, 1.02 * low_hz, sr)


def test_sixty_hz_cut_leaves_the_bass_body_alone_at_44k1():
    """The audit's probe: a -6 dB cut 'at 60 Hz' took 5.3 dB off 120 Hz."""
    sr = 44100
    x = _sine(120.0, sr)
    cut = ParallelEQUtilities.apply_low_shelf_boost(x, -6.0, 60.0, sr)
    assert 20 * np.log10(_gain(cut, x, sr)) > -0.5


def _side_gain(freq_hz: float, sr: int) -> float:
    side = _sine(freq_hz, sr)[0]
    x = np.stack([side, -side], axis=1)  # pure side, [samples, 2] as the widener takes
    out = adjust_stereo_width_multiband(x, 1.0, sr)
    out_side = (out[:, 0] - out[:, 1]) / 2.0
    return _gain(out_side[np.newaxis], side[np.newaxis], sr)


@pytest.mark.parametrize("sr", [88200, 96000, 192000])
def test_widener_low_mid_edge_does_not_move_with_the_sample_rate(sr):
    """At 96 kHz the old floor put the 300 Hz edge at 480 Hz: 400 Hz got 1.12x
    widening where 44.1 kHz gives 1.40x."""
    for freq_hz in (400.0, 600.0):
        assert _side_gain(freq_hz, sr) == pytest.approx(_side_gain(freq_hz, 44100), abs=0.02)


def test_normalized_corner_only_clamps_for_stability():
    assert normalized_corner(60.0, 44100) == pytest.approx(60.0 / 22050)
    assert normalized_corner(20.0, 192000) == pytest.approx(20.0 / 96000)  # well under 0.01
    assert normalized_corner(0.0, 44100) == 1e-4
    assert normalized_corner(30000.0, 44100) == 0.99
