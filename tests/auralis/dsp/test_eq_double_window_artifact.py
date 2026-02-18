# -*- coding: utf-8 -*-

"""
Regression tests for double-windowing artifact in VectorizedEQProcessor (issue #2389)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before the fix, _apply_eq_mono_vectorized applied a Hanning window both before
the FFT and after the IFFT, producing a w(n)^2 amplitude envelope — squared
Hanning — that modulated output amplitude at ~44100/4096 ≈ 10.8 Hz.

Acceptance criterion: amplitude variance of a 1 kHz sine processed through
VectorizedEQProcessor must be < 0.1 %.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest
from scipy.signal import hilbert

from auralis.dsp.eq.parallel_eq_processor.vectorized_processor import VectorizedEQProcessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_RATE = 44100
FFT_SIZE = 4096


def _make_1khz_sine(n_samples: int) -> np.ndarray:
    t = np.arange(n_samples) / SAMPLE_RATE
    return np.sin(2 * np.pi * 1000.0 * t).astype(np.float64)


def _make_flat_band_map(fft_size: int) -> np.ndarray:
    """All positive-frequency bins mapped to a single band (band 0)."""
    return np.zeros(fft_size // 2 + 1, dtype=int)


def _envelope_variance_pct(signal: np.ndarray, edge_trim: float = 0.05) -> float:
    """
    Measure amplitude envelope variance via Hilbert transform.

    Uses the instantaneous amplitude (|analytic signal|) to detect any
    periodic amplitude modulation independent of the signal's phase or
    frequency. Trims ``edge_trim`` fraction from each end to avoid boundary
    artefacts before computing the coefficient of variation.
    """
    envelope = np.abs(hilbert(signal))
    trim = max(1, int(len(envelope) * edge_trim))
    interior = envelope[trim:-trim]
    return float((interior.std() / interior.mean()) * 100)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVectorizedEQNoAmplitudeModulation:
    """VectorizedEQProcessor must not introduce amplitude modulation."""

    def test_unity_gain_amplitude_variance_below_0_1_percent(self):
        """
        0 dB EQ through VectorizedEQProcessor must produce < 0.1 % amplitude variance.

        The pre-fix code multiplied by the Hanning window twice (before FFT and
        after IFFT), creating a w(n)^2 envelope at ~11 Hz.  The Hilbert envelope
        of the processed sine should be essentially flat after the fix.
        """
        processor = VectorizedEQProcessor()
        audio = _make_1khz_sine(FFT_SIZE)
        gains = np.array([0.0])
        freq_to_band_map = _make_flat_band_map(FFT_SIZE)

        result = processor.apply_eq_gains_vectorized(audio, gains, freq_to_band_map, FFT_SIZE)

        variance_pct = _envelope_variance_pct(result)
        assert variance_pct < 0.1, (
            f"Amplitude variance = {variance_pct:.3f}% — expected < 0.1%. "
            "Double-windowing tremolo artifact may still be present."
        )

    def test_positive_6db_gain_amplitude_variance_below_0_1_percent(self):
        """
        +6 dB EQ must also produce a flat amplitude envelope (no tremolo).
        """
        processor = VectorizedEQProcessor()
        audio = _make_1khz_sine(FFT_SIZE)
        gains = np.array([6.0])
        freq_to_band_map = _make_flat_band_map(FFT_SIZE)

        result = processor.apply_eq_gains_vectorized(audio, gains, freq_to_band_map, FFT_SIZE)

        variance_pct = _envelope_variance_pct(result)
        assert variance_pct < 0.1, (
            f"Amplitude variance = {variance_pct:.3f}% with +6 dB gain — expected < 0.1%."
        )

    def test_unity_gain_output_matches_input_amplitude(self):
        """
        With 0 dB gain, output RMS must match input RMS within 1%.

        Before the fix, w(n)^2 caused the mean amplitude to be attenuated
        (area under squared Hanning < 1), so this also catches the bug.
        """
        processor = VectorizedEQProcessor()
        audio = _make_1khz_sine(FFT_SIZE)
        gains = np.array([0.0])
        freq_to_band_map = _make_flat_band_map(FFT_SIZE)

        result = processor.apply_eq_gains_vectorized(audio, gains, freq_to_band_map, FFT_SIZE)

        rms_in = np.sqrt(np.mean(audio ** 2))
        rms_out = np.sqrt(np.mean(result ** 2))
        ratio = rms_out / rms_in

        assert ratio == pytest.approx(1.0, rel=0.01), (
            f"Unity-gain RMS ratio = {ratio:.4f}, expected ≈ 1.0. "
            "Double-windowing attenuation artifact may still be present."
        )

    def test_stereo_input_no_amplitude_modulation(self):
        """Double-windowing fix must also hold for stereo (2-channel) input."""
        processor = VectorizedEQProcessor()
        mono = _make_1khz_sine(FFT_SIZE)
        audio_stereo = np.column_stack([mono, mono])
        gains = np.array([0.0])
        freq_to_band_map = _make_flat_band_map(FFT_SIZE)

        result = processor.apply_eq_gains_vectorized(
            audio_stereo, gains, freq_to_band_map, FFT_SIZE
        )

        assert result.shape == audio_stereo.shape, (
            f"Output shape {result.shape} != input shape {audio_stereo.shape}"
        )

        for ch in range(result.shape[1]):
            variance_pct = _envelope_variance_pct(result[:, ch])
            assert variance_pct < 0.1, (
                f"Channel {ch}: amplitude variance = {variance_pct:.3f}% — expected < 0.1%."
            )
