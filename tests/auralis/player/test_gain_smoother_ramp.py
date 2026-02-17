"""
Tests for AdaptiveGainSmoother per-sample ramp output (issue #2209)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The original implementation returned a single float from process(), ignoring
num_samples.  The fix generates a per-sample exponential gain ramp so that
gain changes are sample-accurate and chunk boundaries are click-free.

Acceptance criteria (from issue):
 - num_samples parameter is used to generate a smooth gain ramp
 - No audible clicks at chunk boundaries during gain changes

Test plan:
 - Gain 0.5 → 1.0 with num_samples=1024: output is monotonically increasing
   ramp with no discontinuities between consecutive samples
 - Steady-state (current == target): returns constant array at target gain
 - Release (1.0 → 0.5, slower alpha): ramp is monotonically decreasing
 - Zero-length chunk: returns empty array without error
 - State continuity: final gain of chunk N == initial gain of chunk N+1
 - Stereo broadcast: level_matcher applies ramp correctly to 2-D audio
"""

import numpy as np
import pytest

from auralis.player.realtime.gain_smoother import AdaptiveGainSmoother
from auralis.player.config import PlayerConfig
from auralis.player.realtime.level_matcher import RealtimeLevelMatcher


# ---------------------------------------------------------------------------
# AdaptiveGainSmoother unit tests
# ---------------------------------------------------------------------------

class TestAdaptiveGainSmootherRamp:
    """Verify per-sample gain ramp output (issue #2209)."""

    def test_process_returns_array_not_scalar(self):
        """process() must return a NumPy ndarray, not a float."""
        smoother = AdaptiveGainSmoother(attack_alpha=0.01)
        smoother.current_gain = 0.5
        smoother.set_target(1.0)
        result = smoother.process(1024)
        assert isinstance(result, np.ndarray), (
            "process() must return np.ndarray for per-sample ramp (issue #2209)"
        )

    def test_process_correct_length(self):
        """Returned array must have exactly num_samples elements."""
        smoother = AdaptiveGainSmoother(attack_alpha=0.01)
        smoother.current_gain = 0.5
        smoother.set_target(1.0)
        for n in [1, 128, 1024, 4096]:
            assert len(smoother.process(n)) == n, f"Expected {n} samples in output"

    def test_attack_ramp_is_monotonically_increasing(self):
        """Attack ramp (0.5 → 1.0) must be strictly increasing sample-by-sample."""
        smoother = AdaptiveGainSmoother(attack_alpha=0.01, release_alpha=0.001)
        smoother.current_gain = 0.5
        smoother.set_target(1.0)
        ramp = smoother.process(1024)

        diffs = np.diff(ramp)
        assert np.all(diffs >= 0), (
            "Attack gain ramp must be non-decreasing (no clicks, issue #2209). "
            f"Min diff = {diffs.min():.6f}"
        )

    def test_attack_ramp_starts_above_initial_gain(self):
        """First sample must be above current_gain (transition has begun)."""
        smoother = AdaptiveGainSmoother(attack_alpha=0.01)
        smoother.current_gain = 0.5
        smoother.set_target(1.0)
        ramp = smoother.process(1024)
        assert ramp[0] > 0.5, "First sample must already move toward target"

    def test_attack_ramp_stays_below_target(self):
        """Gain must not overshoot the target for an attack ramp."""
        smoother = AdaptiveGainSmoother(attack_alpha=0.01)
        smoother.current_gain = 0.5
        smoother.set_target(1.0)
        ramp = smoother.process(1024)
        assert np.all(ramp <= 1.0 + 1e-6), "Gain must not exceed target"

    def test_release_ramp_is_monotonically_decreasing(self):
        """Release ramp (1.0 → 0.5) must be strictly decreasing."""
        smoother = AdaptiveGainSmoother(attack_alpha=0.01, release_alpha=0.005)
        smoother.current_gain = 1.0
        smoother.set_target(0.5)
        ramp = smoother.process(1024)

        diffs = np.diff(ramp)
        assert np.all(diffs <= 0), (
            "Release gain ramp must be non-increasing (issue #2209). "
            f"Max diff = {diffs.max():.6f}"
        )

    def test_steady_state_returns_constant_array(self):
        """When current_gain == target_gain, output must be constant."""
        smoother = AdaptiveGainSmoother()
        smoother.current_gain = 0.8
        smoother.set_target(0.8)
        ramp = smoother.process(512)
        assert np.all(ramp == pytest.approx(0.8)), (
            "Steady-state must return constant array at current_gain"
        )

    def test_zero_length_chunk_returns_empty(self):
        """process(0) must return an empty array without raising."""
        smoother = AdaptiveGainSmoother(attack_alpha=0.01)
        smoother.current_gain = 0.5
        smoother.set_target(1.0)
        result = smoother.process(0)
        assert isinstance(result, np.ndarray)
        assert len(result) == 0

    def test_state_continuity_across_chunks(self):
        """Final gain of chunk N must equal initial gain of chunk N+1.

        Without this, a step discontinuity occurs at every chunk boundary —
        exactly the audible click the fix is meant to eliminate.
        """
        smoother = AdaptiveGainSmoother(attack_alpha=0.02)
        smoother.current_gain = 0.0
        smoother.set_target(1.0)

        chunk1 = smoother.process(512)
        # State was advanced to chunk1[-1]; capture it before next call
        state_after_chunk1 = smoother.current_gain

        chunk2 = smoother.process(512)

        # The first sample of chunk2 must continue from where chunk1 ended
        assert chunk2[0] == pytest.approx(state_after_chunk1 * (1 - smoother.attack_alpha)
                                          + smoother.target_gain * smoother.attack_alpha,
                                          rel=1e-4), (
            "Chunk boundary must be continuous: chunk2[0] must follow chunk1[-1]"
        )

        # No discontinuity at the boundary itself
        boundary_jump = abs(float(chunk2[0]) - float(chunk1[-1]))
        assert boundary_jump < 0.01, (
            f"Gain discontinuity at chunk boundary: {boundary_jump:.6f} "
            "(audible click, issue #2209)"
        )

    def test_output_dtype_is_float32(self):
        """Gain ramp must be float32 to match audio pipeline dtype."""
        smoother = AdaptiveGainSmoother(attack_alpha=0.01)
        smoother.current_gain = 0.5
        smoother.set_target(1.0)
        ramp = smoother.process(1024)
        assert ramp.dtype == np.float32, f"Expected float32, got {ramp.dtype}"


# ---------------------------------------------------------------------------
# RealtimeLevelMatcher integration: gain broadcast over stereo audio
# ---------------------------------------------------------------------------

class TestLevelMatcherGainBroadcast:
    """Verify that the per-sample ramp is applied correctly to 2-D audio."""

    def _make_matcher(self) -> RealtimeLevelMatcher:
        config = PlayerConfig()
        matcher = RealtimeLevelMatcher(config)
        # Enable level matching with a synthetic reference
        ref = np.full(512, 0.5, dtype=np.float32)
        matcher.set_reference_audio(ref)
        return matcher

    def test_stereo_output_shape_preserved(self):
        """Stereo audio (samples, 2) must keep its shape after processing."""
        matcher = self._make_matcher()
        audio = np.ones((1024, 2), dtype=np.float32) * 0.3
        out = matcher.process(audio)
        assert out.shape == (1024, 2), (
            f"Shape changed: expected (1024, 2), got {out.shape}"
        )

    def test_mono_output_shape_preserved(self):
        """Mono audio (samples,) must keep its shape after processing."""
        matcher = self._make_matcher()
        audio = np.ones(1024, dtype=np.float32) * 0.3
        out = matcher.process(audio)
        assert out.shape == (1024,), (
            f"Shape changed: expected (1024,), got {out.shape}"
        )

    def test_stereo_channels_gain_equal(self):
        """Same gain ramp must be applied to both channels (L/R balance kept)."""
        matcher = self._make_matcher()
        # Identical signal on both channels: ratio must remain 1.0 after processing
        audio = np.ones((1024, 2), dtype=np.float32) * 0.3
        out = matcher.process(audio)
        # Channel ratio should be 1.0 at every sample
        ratio = out[:, 0] / (out[:, 1] + 1e-9)
        assert np.allclose(ratio, 1.0, atol=1e-5), (
            "Gain ramp must be applied identically to L and R channels"
        )
