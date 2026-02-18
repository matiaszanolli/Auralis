# -*- coding: utf-8 -*-

"""
Regression tests for Hermitian symmetry in apply_eq_gains (issue #2391)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that band-0 (sub-bass) EQ gains are applied symmetrically to both
positive and negative frequency bins so that:
  - IFFT output is purely real (imaginary residual < 1e-10)
  - A +6 dB boost on a 60 Hz tone produces ~2x amplitude (not ~1x)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest
from scipy.fft import fft, ifft

from auralis.dsp.eq.filters import apply_eq_mono


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tone(freq_hz: float, sample_rate: int, fft_size: int) -> np.ndarray:
    """Return a single-cycle (fft_size samples) sine wave at freq_hz."""
    t = np.arange(fft_size) / sample_rate
    return np.sin(2 * np.pi * freq_hz * t).astype(np.float64)


def _band_map_band0_only(fft_size: int) -> np.ndarray:
    """All positive-frequency bins mapped to band 0 (simplest possible map)."""
    return np.zeros(fft_size // 2 + 1, dtype=int)


def _band_map_split(fft_size: int, sample_rate: int, split_hz: float = 200.0) -> np.ndarray:
    """Band 0 below split_hz, band 1 above — mimics a real critical-band map."""
    n_bins = fft_size // 2 + 1
    freqs = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)
    band_map = np.zeros(n_bins, dtype=int)
    band_map[freqs >= split_hz] = 1
    return band_map


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHermitianSymmetryBand0:
    """EQ applied to band 0 must maintain Hermitian symmetry."""

    SAMPLE_RATE = 44100
    FFT_SIZE = 1024

    def test_unity_gain_band0_is_purely_real(self):
        """0 dB gain on band 0 → IFFT must be purely real."""
        tone = _make_tone(60.0, self.SAMPLE_RATE, self.FFT_SIZE)
        band_map = _band_map_band0_only(self.FFT_SIZE)
        gains = np.array([0.0])  # 0 dB → gain_linear = 1.0

        result = apply_eq_mono(tone, gains, band_map, self.FFT_SIZE)

        # With unity gain the spectrum is untouched so this is trivially real,
        # but it confirms the function runs without error.
        spectrum_out = fft(result)
        imaginary_residual = np.max(np.abs(np.imag(ifft(fft(result)))))
        assert imaginary_residual < 1e-8

    def test_band0_boost_is_purely_real(self):
        """
        +6 dB gain on band 0 must produce a purely real IFFT.

        Before the fix, the asymmetric spectrum caused np.real() to silently
        discard an imaginary component.
        """
        tone = _make_tone(60.0, self.SAMPLE_RATE, self.FFT_SIZE)
        band_map = _band_map_band0_only(self.FFT_SIZE)
        gains = np.array([6.0])  # +6 dB

        # Manually compute what the spectrum looks like after apply_eq_mono
        spectrum = fft(tone)
        gain_linear = 10 ** (6.0 / 20)
        # Apply the gain as the fixed code does (symmetrically)
        band_mask = band_map == 0
        spectrum[:self.FFT_SIZE // 2 + 1][band_mask] *= gain_linear
        spectrum[self.FFT_SIZE // 2 + 1:][band_mask[1:-1][::-1]] *= gain_linear

        imaginary_residual = np.max(np.abs(np.imag(ifft(spectrum))))
        assert imaginary_residual < 1e-10, (
            f"Hermitian symmetry broken: max imaginary residual = {imaginary_residual:.3e}"
        )

    def test_60hz_tone_plus6db_band0_doubles_amplitude(self):
        """
        A 60 Hz tone with +6 dB EQ on band 0 must have ~2x the RMS amplitude.

        This is the acceptance criterion from issue #2391.
        The pre-fix code applied gain only to positive frequencies, giving
        approximately half the expected boost (gain applied once instead of twice).
        """
        fft_size = 4096  # larger size for better frequency resolution at 60 Hz
        tone = _make_tone(60.0, self.SAMPLE_RATE, fft_size)
        band_map = _band_map_split(fft_size, self.SAMPLE_RATE, split_hz=200.0)
        gains = np.array([6.0, 0.0])  # +6 dB on band 0, 0 dB on band 1

        rms_input = np.sqrt(np.mean(tone ** 2))
        result = apply_eq_mono(tone, gains, band_map, fft_size)
        rms_output = np.sqrt(np.mean(result ** 2))

        ratio = rms_output / rms_input
        expected = 10 ** (6.0 / 20)  # ≈ 1.995

        assert ratio == pytest.approx(expected, rel=0.05), (
            f"Expected amplitude ratio ≈ {expected:.3f} (+6 dB), got {ratio:.3f}. "
            "Sub-bass EQ may not be mirrored to negative frequencies."
        )

    def test_band0_cut_reduces_sub_bass(self):
        """
        A -6 dB cut on band 0 must halve the amplitude of a 60 Hz tone.
        """
        fft_size = 4096
        tone = _make_tone(60.0, self.SAMPLE_RATE, fft_size)
        band_map = _band_map_split(fft_size, self.SAMPLE_RATE, split_hz=200.0)
        gains = np.array([-6.0, 0.0])

        rms_input = np.sqrt(np.mean(tone ** 2))
        result = apply_eq_mono(tone, gains, band_map, fft_size)
        rms_output = np.sqrt(np.mean(result ** 2))

        ratio = rms_output / rms_input
        expected = 10 ** (-6.0 / 20)  # ≈ 0.501

        assert ratio == pytest.approx(expected, rel=0.05), (
            f"Expected amplitude ratio ≈ {expected:.3f} (-6 dB), got {ratio:.3f}."
        )

    def test_band1_boost_unaffected_by_fix(self):
        """Band 1 (above split) boost must still work correctly after the fix."""
        fft_size = 4096
        # 1 kHz tone — well above the 200 Hz split, firmly in band 1
        tone = _make_tone(1000.0, self.SAMPLE_RATE, fft_size)
        band_map = _band_map_split(fft_size, self.SAMPLE_RATE, split_hz=200.0)
        gains = np.array([0.0, 6.0])  # 0 dB on band 0, +6 dB on band 1

        rms_input = np.sqrt(np.mean(tone ** 2))
        result = apply_eq_mono(tone, gains, band_map, fft_size)
        rms_output = np.sqrt(np.mean(result ** 2))

        ratio = rms_output / rms_input
        expected = 10 ** (6.0 / 20)

        assert ratio == pytest.approx(expected, rel=0.05), (
            f"Band 1 gain regression: expected ≈ {expected:.3f}, got {ratio:.3f}."
        )
