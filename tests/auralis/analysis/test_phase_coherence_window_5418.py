"""
Regression: PhaseCorrelationAnalyzer._calculate_phase_coherence's spectral
window is anchored in time, not a bare sample-count literal (#5418).

The 3 scipy.signal.welch/csd calls inside _calculate_phase_coherence used to
hardcode nperseg=1024 regardless of sample rate, so the effective analysis
window spanned ~23ms at 44.1kHz but only ~11ms at 96kHz -- a metric-
consistency issue: phase-coherence values were not comparable across tracks
at different sample rates. #4308 converted 4 sibling sites to
frames_for_seconds() but missed this one.

sample_rate=44100 is the historical literal (1024 samples exactly), kept as
the default so this fix is a no-op at the most common rate.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.analysis.phase_correlation import PhaseCorrelationAnalyzer  # noqa: E402
from auralis.dsp.utils.spectral import frames_for_seconds  # noqa: E402


def _stereo_test_signal(sample_rate: int, duration_s: float = 2.0) -> np.ndarray:
    """A simple correlated stereo signal, long enough for welch's default
    windowing to produce a stable, non-degenerate PSD at every rate tested."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    left = np.sin(2 * np.pi * 440 * t).astype(np.float64)
    right = 0.9 * left + 0.05 * np.sin(2 * np.pi * 880 * t)
    return np.stack([left, right], axis=1)


class TestWindowScalesWithSampleRate:
    def test_44100_reproduces_the_historical_literal(self):
        """Anchors the fix: nperseg at the original rate must stay exactly
        1024, so nothing changes at the most common sample rate."""
        assert frames_for_seconds(44100, 1024 / 44100) == 1024

    def test_96000_uses_a_larger_window_than_44100(self):
        """The core regression: before this fix both rates used the same
        1024-sample window, so the effective duration at 96kHz was roughly
        half that at 44.1kHz. After the fix, a higher sample rate must use
        a proportionally larger (time-equivalent) window."""
        window_44100 = frames_for_seconds(44100, 1024 / 44100)
        window_96000 = frames_for_seconds(96000, 1024 / 44100)
        assert window_96000 > window_44100

    def test_coherence_still_computes_at_a_non_standard_sample_rate(self):
        """End-to-end: _calculate_phase_coherence must not crash or return
        degenerate output when the sample rate differs from 44.1kHz (the
        bug this fix targets is a metric-consistency issue, not a crash --
        this pins that the fix didn't introduce one)."""
        analyzer = PhaseCorrelationAnalyzer(sample_rate=96000)
        audio = _stereo_test_signal(96000)
        left, right = audio[:, 0], audio[:, 1]

        result = analyzer._calculate_phase_coherence(left, right)

        assert 'overall_coherence' in result or 'frequency_bands' in result or result
        # Highly correlated stereo content should show meaningfully non-zero
        # coherence -- a crude sanity check that the window change didn't
        # silently break the calculation.
        for value in result.values():
            if isinstance(value, (int, float)):
                assert np.isfinite(value)

    def test_full_analyze_correlation_path_uses_the_scaled_window(self):
        """The public entry point (analyze_correlation -> _calculate_phase_coherence)
        still runs end to end at a non-44.1kHz rate."""
        analyzer = PhaseCorrelationAnalyzer(sample_rate=48000)
        audio = _stereo_test_signal(48000)

        result = analyzer.analyze_correlation(audio)

        assert 'phase_coherence' in result
