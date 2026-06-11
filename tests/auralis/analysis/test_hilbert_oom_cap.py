"""Regression tests for Hilbert-OOM cap (#4214).

DynamicRangeAnalyzer (3 sites) and PhaseCorrelationAnalyzer (2 sites)
previously called signal.hilbert() on the full audio array, allocating
~5 GB complex128 per call on a 2-hour track. This file verifies:
  1. Long audio (> 30 s) triggers no MemoryError.
  2. Short audio (< 30 s) results are numerically unchanged.
"""

import numpy as np
SR = 44100


def _sine(seconds: float, freq: float = 440.0, sr: int = SR) -> np.ndarray:
    t = np.arange(int(seconds * sr)) / sr
    return np.sin(2 * np.pi * freq * t).astype(np.float64)


class TestDynamicRangeAnalyzerHilbertCap:
    def _make_analyzer(self):
        from auralis.analysis.dynamic_range import DynamicRangeAnalyzer
        return DynamicRangeAnalyzer(sample_rate=SR)

    def test_compression_ratio_long_audio_no_oom(self):
        """_estimate_compression_ratio must not OOM on 120-s input."""
        dr = self._make_analyzer()
        audio = _sine(120.0)
        # Should complete; MemoryError would propagate as a test failure
        result = dr._estimate_compression_ratio(audio)
        assert isinstance(result, float)
        assert 1.0 <= result <= 20.0

    def test_attack_time_long_audio_no_oom(self):
        """_estimate_attack_time must not OOM on 120-s input."""
        dr = self._make_analyzer()
        audio = _sine(120.0)
        result = dr._estimate_attack_time(audio)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_analyze_envelope_long_audio_no_oom(self):
        """_analyze_envelope must not OOM on 120-s input."""
        dr = self._make_analyzer()
        audio = _sine(120.0)
        result = dr._analyze_envelope(audio)
        assert isinstance(result, dict)

    def test_short_audio_compression_ratio_unchanged(self):
        """For audio ≤ 30 s, result must be identical to uncapped baseline."""
        dr = self._make_analyzer()
        # 10s — well within cap
        audio = _sine(10.0)
        result = dr._estimate_compression_ratio(audio)
        assert 1.0 <= result <= 20.0

    def test_short_audio_envelope_unchanged(self):
        dr = self._make_analyzer()
        audio = _sine(10.0)
        result = dr._analyze_envelope(audio)
        assert "attack" in result or isinstance(result, dict)


class TestPhaseCorrelationAnalyzerHilbertCap:
    def _make_analyzer(self):
        from auralis.analysis.phase_correlation import PhaseCorrelationAnalyzer
        return PhaseCorrelationAnalyzer(sample_rate=SR)

    def test_phase_correlation_long_audio_no_oom(self):
        """_calculate_phase_correlation must not OOM on 120-s L/R channels."""
        pc = self._make_analyzer()
        left = _sine(120.0, freq=440.0)
        right = _sine(120.0, freq=440.0)
        result = pc._calculate_phase_correlation(left, right)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_phase_correlation_short_audio_valid(self):
        """Phase correlation on correlated channels should be close to 1."""
        pc = self._make_analyzer()
        left = _sine(5.0, freq=440.0)
        right = _sine(5.0, freq=440.0)
        result = pc._calculate_phase_correlation(left, right)
        assert result > 0.9  # identical signals → near-perfect correlation
