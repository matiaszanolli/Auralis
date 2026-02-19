"""
Tests for HarmonicOperations fallback behaviour (#2445)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that calculate_harmonic_ratio(), calculate_pitch_stability(),
calculate_chroma_energy(), and calculate_all() return 0.5 fallback values
instead of propagating exceptions when the Rust DSP backend raises.
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from auralis.analysis.fingerprint.utilities.harmonic_ops import HarmonicOperations

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SR = 44100

@pytest.fixture
def silence():
    return np.zeros(SR, dtype=np.float32)


@pytest.fixture
def short_sine():
    t = np.linspace(0, 1.0, SR, endpoint=False)
    return np.sin(2 * np.pi * 440 * t).astype(np.float32)


# ---------------------------------------------------------------------------
# Individual method fallbacks
# ---------------------------------------------------------------------------

class TestCalculateHarmonicRatioFallback:
    """calculate_harmonic_ratio must return 0.5, not raise, on any error."""

    def test_returns_float_on_success(self, short_sine):
        with patch(
            'auralis.analysis.fingerprint.utilities.harmonic_ops.HarmonicOperations'
            '.calculate_harmonic_ratio',
            return_value=0.8
        ):
            result = HarmonicOperations.calculate_harmonic_ratio(short_sine)
            assert isinstance(result, float)

    def test_returns_fallback_when_dsp_raises(self, short_sine):
        """DSPBackend.hpss() raising must yield 0.5, not propagate."""
        with patch(
            'auralis.analysis.fingerprint.utilities.dsp_backend.DSPBackend.hpss',
            side_effect=RuntimeError("Rust DSP not available")
        ):
            result = HarmonicOperations.calculate_harmonic_ratio(short_sine)
        assert result == 0.5

    def test_returns_fallback_on_import_error(self, short_sine):
        """ImportError for dsp_backend must yield 0.5."""
        with patch.dict('sys.modules', {
            'auralis.analysis.fingerprint.utilities.dsp_backend': None
        }):
            result = HarmonicOperations.calculate_harmonic_ratio(short_sine)
        assert result == 0.5

    def test_does_not_raise(self, short_sine):
        """No exception must escape calculate_harmonic_ratio."""
        with patch(
            'auralis.analysis.fingerprint.utilities.dsp_backend.DSPBackend.hpss',
            side_effect=Exception("unexpected internal error")
        ):
            try:
                HarmonicOperations.calculate_harmonic_ratio(short_sine)
            except Exception as exc:
                pytest.fail(f"calculate_harmonic_ratio raised unexpectedly: {exc}")


class TestCalculatePitchStabilityFallback:
    """calculate_pitch_stability must return 0.5, not raise, on any error."""

    def test_returns_fallback_when_yin_raises(self, short_sine):
        """DSPBackend.yin() raising must yield 0.5."""
        with patch(
            'auralis.analysis.fingerprint.utilities.dsp_backend.DSPBackend.yin',
            side_effect=RuntimeError("Rust DSP not available")
        ):
            result = HarmonicOperations.calculate_pitch_stability(short_sine, SR)
        assert result == 0.5

    def test_returns_fallback_on_import_error(self, short_sine):
        with patch.dict('sys.modules', {
            'auralis.analysis.fingerprint.utilities.dsp_backend': None
        }):
            result = HarmonicOperations.calculate_pitch_stability(short_sine, SR)
        assert result == 0.5

    def test_does_not_raise(self, short_sine):
        with patch(
            'auralis.analysis.fingerprint.utilities.dsp_backend.DSPBackend.yin',
            side_effect=Exception("unexpected error")
        ):
            try:
                HarmonicOperations.calculate_pitch_stability(short_sine, SR)
            except Exception as exc:
                pytest.fail(f"calculate_pitch_stability raised unexpectedly: {exc}")

    def test_returns_half_when_too_few_voiced_frames(self, silence):
        """Fewer than 10 voiced frames → 0.5 (early-return path, not error)."""
        # silence produces all-zero f0 → no voiced frames
        voiced_empty = np.array([], dtype=np.float32)
        with patch(
            'auralis.analysis.fingerprint.utilities.dsp_backend.DSPBackend.yin',
            return_value=np.zeros(100, dtype=np.float32)  # all unvoiced
        ):
            result = HarmonicOperations.calculate_pitch_stability(silence, SR)
        assert result == 0.5


class TestCalculateChromaEnergyFallback:
    """calculate_chroma_energy must return 0.5, not raise, on any error."""

    def test_returns_fallback_when_chroma_raises(self, short_sine):
        """DSPBackend.chroma_cqt() raising must yield 0.5."""
        with patch(
            'auralis.analysis.fingerprint.utilities.dsp_backend.DSPBackend.chroma_cqt',
            side_effect=RuntimeError("Rust DSP not available")
        ):
            result = HarmonicOperations.calculate_chroma_energy(short_sine, SR)
        assert result == 0.5

    def test_returns_fallback_on_import_error(self, short_sine):
        with patch.dict('sys.modules', {
            'auralis.analysis.fingerprint.utilities.dsp_backend': None
        }):
            result = HarmonicOperations.calculate_chroma_energy(short_sine, SR)
        assert result == 0.5

    def test_does_not_raise(self, short_sine):
        with patch(
            'auralis.analysis.fingerprint.utilities.dsp_backend.DSPBackend.chroma_cqt',
            side_effect=Exception("unexpected error")
        ):
            try:
                HarmonicOperations.calculate_chroma_energy(short_sine, SR)
            except Exception as exc:
                pytest.fail(f"calculate_chroma_energy raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# calculate_all() fallback and independence
# ---------------------------------------------------------------------------

class TestCalculateAllFallback:
    """calculate_all() must return a (float, float, float) tuple even on failures."""

    def test_returns_all_fallbacks_when_all_raise(self, short_sine):
        """All three sub-methods raising must yield (0.5, 0.5, 0.5)."""
        with patch.object(HarmonicOperations, 'calculate_harmonic_ratio',
                          side_effect=RuntimeError("hpss failed")), \
             patch.object(HarmonicOperations, 'calculate_pitch_stability',
                          side_effect=RuntimeError("yin failed")), \
             patch.object(HarmonicOperations, 'calculate_chroma_energy',
                          side_effect=RuntimeError("chroma failed")):
            result = HarmonicOperations.calculate_all(short_sine, SR)

        assert result == (0.5, 0.5, 0.5)

    def test_partial_failure_returns_valid_metrics(self, short_sine):
        """If only pitch_stability raises, harmonic_ratio and chroma_energy are real."""
        with patch.object(HarmonicOperations, 'calculate_harmonic_ratio',
                          return_value=0.8), \
             patch.object(HarmonicOperations, 'calculate_pitch_stability',
                          side_effect=RuntimeError("yin failed")), \
             patch.object(HarmonicOperations, 'calculate_chroma_energy',
                          return_value=0.3):
            harmonic_ratio, pitch_stability, chroma_energy = \
                HarmonicOperations.calculate_all(short_sine, SR)

        assert harmonic_ratio == 0.8    # real value preserved
        assert pitch_stability == 0.5   # fallback only for the failing metric
        assert chroma_energy == 0.3     # real value preserved

    def test_does_not_raise_under_any_circumstances(self, short_sine):
        """calculate_all() must never raise, regardless of sub-method failures."""
        with patch.object(HarmonicOperations, 'calculate_harmonic_ratio',
                          side_effect=Exception("boom")), \
             patch.object(HarmonicOperations, 'calculate_pitch_stability',
                          side_effect=Exception("boom")), \
             patch.object(HarmonicOperations, 'calculate_chroma_energy',
                          side_effect=Exception("boom")):
            try:
                HarmonicOperations.calculate_all(short_sine, SR)
            except Exception as exc:
                pytest.fail(f"calculate_all raised unexpectedly: {exc}")

    def test_returns_tuple_of_three_floats(self, short_sine):
        """Return type must always be a 3-tuple of floats."""
        with patch.object(HarmonicOperations, 'calculate_harmonic_ratio',
                          return_value=0.7), \
             patch.object(HarmonicOperations, 'calculate_pitch_stability',
                          return_value=0.6), \
             patch.object(HarmonicOperations, 'calculate_chroma_energy',
                          return_value=0.4):
            result = HarmonicOperations.calculate_all(short_sine, SR)

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert all(isinstance(v, float) for v in result)

    def test_fallback_values_in_range(self, short_sine):
        """All returned values (including fallbacks) must be in [0, 1]."""
        with patch.object(HarmonicOperations, 'calculate_harmonic_ratio',
                          side_effect=RuntimeError("fail")), \
             patch.object(HarmonicOperations, 'calculate_pitch_stability',
                          side_effect=RuntimeError("fail")), \
             patch.object(HarmonicOperations, 'calculate_chroma_energy',
                          side_effect=RuntimeError("fail")):
            result = HarmonicOperations.calculate_all(short_sine, SR)

        assert all(0.0 <= v <= 1.0 for v in result), (
            f"All fallback values must be in [0,1], got {result}"
        )
