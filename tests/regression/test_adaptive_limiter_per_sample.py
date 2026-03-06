"""
AdaptiveLimiter Per-Sample Gain Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #2681:
AdaptiveLimiter must apply per-sample gain reduction, not a single
scalar for the entire chunk. A single scalar over-attenuates quiet
passages when a loud transient exists anywhere in the chunk.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.limiter import AdaptiveLimiter
from auralis.dsp.dynamics.settings import LimiterSettings


@pytest.mark.regression
class TestAdaptiveLimiterPerSampleGain:
    """Regression tests for per-sample gain in AdaptiveLimiter (#2681)."""

    def _make_limiter(self, threshold_db=-6.0):
        settings = LimiterSettings(
            threshold_db=threshold_db,
            oversampling=1,
            isr_enabled=False,
            lookahead_ms=5.0,
        )
        return AdaptiveLimiter(settings, sample_rate=44100)

    def test_quiet_regions_not_attenuated_by_distant_transient(self):
        """
        A loud transient in the middle of a chunk must not cause
        gain reduction in quiet regions far from the transient.
        """
        limiter = self._make_limiter(threshold_db=-6.0)
        sr = 44100
        audio = np.ones((sr, 2)) * 0.1  # quiet at 0.1 (~-20 dBFS)
        audio[sr // 2:sr // 2 + 100, :] = 0.9  # loud transient

        result, _ = limiter.process(audio)

        # Skip lookahead delay samples (filled with zeros from the delay buffer)
        lookahead = limiter.lookahead_samples
        quiet_before = result[lookahead:sr // 4]
        assert np.allclose(quiet_before, 0.1, atol=0.02), (
            f"Quiet region over-attenuated: max={np.max(np.abs(quiet_before)):.4f}, "
            f"expected ~0.1"
        )

        # Quiet region after the transient should recover
        quiet_after = result[3 * sr // 4:]
        assert np.max(np.abs(quiet_after)) > 0.08, (
            f"Quiet region after transient over-attenuated: "
            f"max={np.max(np.abs(quiet_after)):.4f}"
        )

    def test_transient_is_limited(self):
        """The loud transient itself should be gain-reduced."""
        limiter = self._make_limiter(threshold_db=-6.0)
        threshold_linear = 10 ** (-6.0 / 20)
        sr = 44100
        audio = np.zeros((sr, 2))
        audio[sr // 2:sr // 2 + 200, :] = 0.9

        result, info = limiter.process(audio)

        transient_peak = np.max(np.abs(result[sr // 2:sr // 2 + 200]))
        # Should be reduced (though exact level depends on attack/release)
        assert transient_peak < 0.9, "Transient was not limited at all"

    def test_mono_per_sample_gain(self):
        """Per-sample gain works for mono audio too."""
        limiter = self._make_limiter(threshold_db=-6.0)
        sr = 44100
        audio = np.ones(sr) * 0.1
        audio[sr // 2:sr // 2 + 100] = 0.9

        result, _ = limiter.process(audio)

        quiet_before = np.max(np.abs(result[:sr // 4]))
        assert quiet_before > 0.08, (
            f"Mono quiet region over-attenuated: {quiet_before:.4f}"
        )

    def test_sample_count_preserved(self):
        """Output must have same number of samples as input."""
        limiter = self._make_limiter()
        audio = np.random.RandomState(42).randn(44100, 2).astype(np.float64) * 0.5

        result, _ = limiter.process(audio)

        assert result.shape == audio.shape, (
            f"Shape mismatch: {result.shape} != {audio.shape}"
        )
