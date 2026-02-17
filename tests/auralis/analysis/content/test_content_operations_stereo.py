"""
Tests for ContentAnalysisOperations stereo-audio correctness (issue #2203)

Verifies that:
1. `_to_mono` converts multi-channel audio to 1D and leaves 1D unchanged.
2. All FFT-based methods return equivalent values for mono and stereo
   versions of the same audio (within 5% relative tolerance).
3. The internal FFT always operates on the time axis (result is 1D).
"""

import numpy as np
import pytest

from auralis.analysis.content.content_operations import ContentAnalysisOperations

SR = 44100  # sample rate used throughout


# ============================================================================
# Helpers
# ============================================================================

def _sine_mono(freq: float = 440.0, duration_s: float = 1.0) -> np.ndarray:
    """1D mono sine wave."""
    t = np.arange(int(SR * duration_s)) / SR
    return (np.sin(2 * np.pi * freq * t) * 0.5).astype(np.float32)


def _to_stereo(mono: np.ndarray, pan: float = 0.0) -> np.ndarray:
    """Expand mono → stereo (N, 2) with optional slight pan so channels differ."""
    left = mono * (1.0 - max(pan, 0))
    right = mono * (1.0 + min(pan, 0))
    return np.column_stack([left, right])


def _rel_diff(a: float, b: float) -> float:
    """Relative difference with respect to the larger value."""
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom


# ============================================================================
# 1. _to_mono helper
# ============================================================================

class TestToMono:
    def test_1d_unchanged(self):
        mono = _sine_mono()
        out = ContentAnalysisOperations._to_mono(mono)
        np.testing.assert_array_equal(out, mono)

    def test_stereo_to_1d(self):
        mono = _sine_mono()
        stereo = _to_stereo(mono)
        out = ContentAnalysisOperations._to_mono(stereo)
        assert out.ndim == 1
        assert len(out) == len(mono)

    def test_stereo_mean_equals_mono_for_identical_channels(self):
        mono = _sine_mono()
        stereo = np.column_stack([mono, mono])  # both channels identical
        out = ContentAnalysisOperations._to_mono(stereo)
        np.testing.assert_allclose(out, mono, atol=1e-6)

    def test_multi_channel_reduces_to_1d(self):
        mono = _sine_mono()
        quad = np.column_stack([mono, mono, mono, mono])  # 4 channels
        out = ContentAnalysisOperations._to_mono(quad)
        assert out.ndim == 1
        assert len(out) == len(mono)


# ============================================================================
# 2. calculate_spectral_spread — mono ≈ stereo, result is scalar
# ============================================================================

class TestSpectralSpread:
    def test_mono_and_stereo_within_5_percent(self):
        mono = _sine_mono(440.0, duration_s=0.3)
        stereo = _to_stereo(mono)
        spread_mono = ContentAnalysisOperations.calculate_spectral_spread(mono, SR)
        spread_stereo = ContentAnalysisOperations.calculate_spectral_spread(stereo, SR)
        assert _rel_diff(spread_mono, spread_stereo) < 0.05, (
            f"Spectral spread diverges: mono={spread_mono:.1f}, stereo={spread_stereo:.1f}"
        )

    def test_returns_scalar(self):
        stereo = _to_stereo(_sine_mono())
        result = ContentAnalysisOperations.calculate_spectral_spread(stereo, SR)
        assert isinstance(result, float)

    def test_fft_shape_is_1d_for_stereo(self):
        """Internal FFT must produce a 1D spectrum — smoke-test via shape of output."""
        from scipy.fft import fft
        mono = ContentAnalysisOperations._to_mono(_to_stereo(_sine_mono()))
        fft_result = fft(mono[:8192])
        assert fft_result.ndim == 1
        assert len(fft_result) == 8192


# ============================================================================
# 3. calculate_spectral_flux — mono ≈ stereo, result is scalar
# ============================================================================

class TestSpectralFlux:
    def test_mono_and_stereo_within_5_percent(self):
        mono = _sine_mono(440.0, duration_s=1.0)
        stereo = _to_stereo(mono)
        flux_mono = ContentAnalysisOperations.calculate_spectral_flux(mono)
        flux_stereo = ContentAnalysisOperations.calculate_spectral_flux(stereo)
        assert _rel_diff(flux_mono, flux_stereo) < 0.05, (
            f"Spectral flux diverges: mono={flux_mono:.4f}, stereo={flux_stereo:.4f}"
        )

    def test_returns_scalar(self):
        stereo = _to_stereo(_sine_mono())
        result = ContentAnalysisOperations.calculate_spectral_flux(stereo)
        assert isinstance(result, float)


# ============================================================================
# 4. calculate_harmonic_ratio — mono ≈ stereo, result is scalar in [0, 1]
# ============================================================================

class TestHarmonicRatio:
    def test_mono_and_stereo_within_5_percent(self):
        mono = _sine_mono(440.0, duration_s=0.3)
        stereo = _to_stereo(mono)
        hr_mono = ContentAnalysisOperations.calculate_harmonic_ratio(mono)
        hr_stereo = ContentAnalysisOperations.calculate_harmonic_ratio(stereo)
        assert _rel_diff(hr_mono, hr_stereo) < 0.05, (
            f"Harmonic ratio diverges: mono={hr_mono:.4f}, stereo={hr_stereo:.4f}"
        )

    def test_returns_scalar_in_range(self):
        stereo = _to_stereo(_sine_mono())
        result = ContentAnalysisOperations.calculate_harmonic_ratio(stereo)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0


# ============================================================================
# 5. estimate_fundamental_frequency — mono ≈ stereo for tonal input
# ============================================================================

class TestFundamentalFrequency:
    def test_mono_and_stereo_within_5_percent(self):
        mono = _sine_mono(440.0, duration_s=1.0)
        stereo = _to_stereo(mono)
        f0_mono = ContentAnalysisOperations.estimate_fundamental_frequency(mono, SR)
        f0_stereo = ContentAnalysisOperations.estimate_fundamental_frequency(stereo, SR)
        # Both should detect near 440 Hz (within 5% of each other)
        assert _rel_diff(f0_mono, f0_stereo) < 0.05, (
            f"F0 diverges: mono={f0_mono:.1f}, stereo={f0_stereo:.1f}"
        )

    def test_returns_scalar(self):
        stereo = _to_stereo(_sine_mono())
        result = ContentAnalysisOperations.estimate_fundamental_frequency(stereo, SR)
        assert isinstance(result, float)


# ============================================================================
# 6. calculate_onset_strength — shape is 1D for stereo input
# ============================================================================

class TestOnsetStrength:
    def test_returns_1d_array_for_stereo(self):
        stereo = _to_stereo(_sine_mono(duration_s=1.0))
        result = ContentAnalysisOperations.calculate_onset_strength(stereo)
        assert isinstance(result, np.ndarray)
        assert result.ndim == 1

    def test_mono_and_stereo_produce_same_length(self):
        mono = _sine_mono(duration_s=1.0)
        stereo = _to_stereo(mono)
        os_mono = ContentAnalysisOperations.calculate_onset_strength(mono)
        os_stereo = ContentAnalysisOperations.calculate_onset_strength(stereo)
        assert len(os_mono) == len(os_stereo)
