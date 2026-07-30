"""Regression tests for degenerate-length input guards (#4996).

estimate_thd / estimate_fundamental_frequency slice a "middle section"
(len//4 : 3*len//4) before calling np.fft.rfft with no explicit `n=`; for
len(audio) in {0, 1} that slice is empty and rfft raises ValueError.
PhaseCorrelationAnalyzer._calculate_phase_correlation calls
scipy.signal.hilbert on a possibly-empty array, which also raises ValueError.

None of these had a reachable unmitigated crash path (every current caller
enforces a sufficiently long window upstream), but the shared utility
functions had no defense of their own. This file verifies the added guards
return the documented sentinel instead of crashing, and that normal-length
callers are unaffected.
"""

import numpy as np
import pytest

from auralis.analysis.quality_assessors.utilities.estimation_ops import EstimationOperations
from auralis.analysis.phase_correlation import PhaseCorrelationAnalyzer

SR = 44100


def _sine(seconds: float, freq: float = 440.0, sr: int = SR) -> np.ndarray:
    t = np.arange(int(seconds * sr)) / sr
    return np.sin(2 * np.pi * freq * t).astype(np.float64)


class TestEstimateThdDegenerateInput:
    @pytest.mark.parametrize("n", [0, 1])
    def test_degenerate_length_returns_sentinel_not_raise(self, n):
        audio = np.zeros(n, dtype=np.float64)
        assert EstimationOperations.estimate_thd(audio) == 0.0

    def test_normal_length_unaffected(self):
        audio = _sine(1.0)
        thd = EstimationOperations.estimate_thd(audio)
        assert isinstance(thd, float)
        assert thd >= 0.0


class TestEstimateFundamentalFrequencyDegenerateInput:
    @pytest.mark.parametrize("n", [0, 1])
    def test_degenerate_length_returns_sentinel_not_raise(self, n):
        audio = np.zeros(n, dtype=np.float64)
        freq, idx = EstimationOperations.estimate_fundamental_frequency(audio, sr=SR)
        assert freq == 0.0
        assert idx == 0

    def test_normal_length_unaffected(self):
        audio = _sine(1.0, freq=440.0)
        freq, idx = EstimationOperations.estimate_fundamental_frequency(audio, sr=SR)
        assert freq > 0.0
        assert idx > 0


class TestPhaseCorrelationDegenerateInput:
    @pytest.mark.parametrize("n", [0, 1])
    def test_degenerate_length_returns_sentinel_not_raise(self, n):
        pc = PhaseCorrelationAnalyzer(sample_rate=SR)
        left = np.zeros(n, dtype=np.float64)
        right = np.zeros(n, dtype=np.float64)
        result = pc._calculate_phase_correlation(left, right)
        assert isinstance(result, float)

    def test_normal_length_unaffected(self):
        pc = PhaseCorrelationAnalyzer(sample_rate=SR)
        left = _sine(1.0, freq=440.0)
        right = _sine(1.0, freq=440.0)
        result = pc._calculate_phase_correlation(left, right)
        assert result > 0.9  # identical signals correlate strongly
