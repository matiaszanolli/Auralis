"""
Regression tests for gain-loss race in ParallelEQProcessor — issue #2448.

Before the fix, _process_bands_parallel and _process_band_groups_parallel only
retained the last thread's result, so only 1 out of N band gains was applied.
This caused amplitude modulation because the effective EQ response varied per chunk.

Acceptance criteria:
  - Amplitude envelope variance of a 1 kHz sine < 0.1 %  (Hilbert envelope)
  - +6 dB across all 26 bands produces ~2x RMS  (all gains actually applied)
  - Parallel and sequential paths produce numerically identical output

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest
from scipy.signal import hilbert

from auralis.dsp.eq.parallel_eq_processor import ParallelEQConfig, ParallelEQProcessor

SAMPLE_RATE = 44100
FFT_SIZE = 4096


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_1khz_sine(n_samples: int) -> np.ndarray:
    t = np.arange(n_samples) / SAMPLE_RATE
    return np.sin(2 * np.pi * 1000.0 * t).astype(np.float64)


def _make_multiband_map(fft_size: int, n_bands: int) -> np.ndarray:
    """Distribute FFT bins evenly across n_bands."""
    num_bins = fft_size // 2 + 1
    band_map = np.zeros(num_bins, dtype=int)
    bins_per_band = num_bins // n_bands
    for b in range(n_bands):
        band_map[b * bins_per_band:(b + 1) * bins_per_band] = b
    # Last band absorbs any remainder
    band_map[(n_bands - 1) * bins_per_band:] = n_bands - 1
    return band_map


def _envelope_variance_pct(signal: np.ndarray, edge_trim: float = 0.05) -> float:
    """
    Measure amplitude-envelope variance via Hilbert transform.

    Trims edge_trim fraction from each end to avoid boundary artefacts,
    then returns the coefficient of variation (std/mean * 100) of the
    instantaneous amplitude.
    """
    envelope = np.abs(hilbert(signal))
    trim = max(1, int(len(envelope) * edge_trim))
    interior = envelope[trim:-trim]
    return float((interior.std() / interior.mean()) * 100)


def _parallel_processor() -> ParallelEQProcessor:
    """Default config: parallel enabled, band grouping enabled (was the broken path)."""
    return ParallelEQProcessor(ParallelEQConfig(
        enable_parallel=True,
        use_band_grouping=True,
        min_bands_for_parallel=8,
    ))


def _sequential_processor() -> ParallelEQProcessor:
    return ParallelEQProcessor(ParallelEQConfig(enable_parallel=False))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParallelEQGainAccumulation:
    """
    ParallelEQProcessor must apply ALL band gains, not just the last thread's.
    """

    def test_unity_gain_amplitude_variance_below_0_1_percent(self):
        """
        0 dB through the parallel path must not introduce amplitude modulation.

        Before the fix, even unity gain could produce tremolo because the merge
        loop overwrote spectrum_copy on every iteration, leaving whichever band
        happened to be last with its single-band copy as the final result.
        """
        processor = _parallel_processor()
        audio = _make_1khz_sine(FFT_SIZE)
        gains = np.zeros(26)
        freq_to_band_map = _make_multiband_map(FFT_SIZE, 26)

        result = processor.apply_eq_gains_parallel(audio, gains, freq_to_band_map, FFT_SIZE)
        assert result.shape == audio.shape

        var_pct = _envelope_variance_pct(result)
        assert var_pct < 0.1, (
            f"Amplitude variance = {var_pct:.3f}% — expected < 0.1%. "
            "Gain-loss race condition may still be present in parallel path."
        )

    def test_unity_gain_rms_preserved(self):
        """With 0 dB gain, output RMS must match input within 1%."""
        processor = _parallel_processor()
        audio = _make_1khz_sine(FFT_SIZE)
        gains = np.zeros(26)
        freq_to_band_map = _make_multiband_map(FFT_SIZE, 26)

        result = processor.apply_eq_gains_parallel(audio, gains, freq_to_band_map, FFT_SIZE)

        rms_in = np.sqrt(np.mean(audio ** 2))
        rms_out = np.sqrt(np.mean(result ** 2))
        assert rms_out == pytest.approx(rms_in, rel=0.01), (
            f"RMS ratio = {rms_out / rms_in:.4f}, expected ≈ 1.0"
        )

    def test_positive_6db_gain_applied_to_all_bands(self):
        """
        +6 dB across all 26 bands must produce ~2× amplitude, not 1×.

        Before the fix, only the last band's +6 dB survived the merge loop.
        If the 1 kHz sine maps to an earlier band the output is unchanged
        (ratio ≈ 1.0 instead of ≈ 2.0), directly exposing the bug.
        """
        processor = _parallel_processor()
        audio = _make_1khz_sine(FFT_SIZE)
        gains = np.full(26, 6.0)          # +6 dB everywhere → 2× linear
        freq_to_band_map = _make_multiband_map(FFT_SIZE, 26)

        result = processor.apply_eq_gains_parallel(audio, gains, freq_to_band_map, FFT_SIZE)

        rms_in = np.sqrt(np.mean(audio ** 2))
        rms_out = np.sqrt(np.mean(result ** 2))
        ratio = rms_out / rms_in
        assert ratio == pytest.approx(2.0, rel=0.05), (
            f"RMS ratio = {ratio:.4f}, expected ≈ 2.0 (+6 dB). "
            "If ≈ 1.0, only 1 band's gain was applied (race condition still present)."
        )

    def test_stereo_all_gains_applied_to_both_channels(self):
        """Stereo parallel path must also apply all gains (not just last band)."""
        processor = _parallel_processor()
        mono = _make_1khz_sine(FFT_SIZE)
        audio_stereo = np.column_stack([mono, mono])
        gains = np.full(26, 6.0)
        freq_to_band_map = _make_multiband_map(FFT_SIZE, 26)

        result = processor.apply_eq_gains_parallel(audio_stereo, gains, freq_to_band_map, FFT_SIZE)

        assert result.shape == audio_stereo.shape
        for ch in range(2):
            rms_in = np.sqrt(np.mean(audio_stereo[:, ch] ** 2))
            rms_out = np.sqrt(np.mean(result[:, ch] ** 2))
            ratio = rms_out / rms_in
            assert ratio == pytest.approx(2.0, rel=0.05), (
                f"Channel {ch}: RMS ratio = {ratio:.4f}, expected ≈ 2.0"
            )

    def test_parallel_matches_sequential_output(self):
        """
        Parallel path must produce numerically identical output to the sequential
        fallback for the same input, gains, and freq_to_band_map.
        """
        # Mixed gains spanning all 26 bands
        gains = np.array([float(i) for i in range(-12, 14)])  # -12 to +13 dB
        freq_to_band_map = _make_multiband_map(FFT_SIZE, 26)
        audio = _make_1khz_sine(FFT_SIZE)

        out_parallel = _parallel_processor().apply_eq_gains_parallel(
            audio, gains, freq_to_band_map, FFT_SIZE
        )
        out_sequential = _sequential_processor().apply_eq_gains_parallel(
            audio, gains, freq_to_band_map, FFT_SIZE
        )

        np.testing.assert_allclose(
            out_parallel, out_sequential, rtol=1e-10,
            err_msg="Parallel and sequential EQ paths must produce identical output."
        )
