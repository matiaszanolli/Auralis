"""
Brick-Wall Limiter Inter-Job Reset Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #4811:
``BrickWallLimiter.current_gain`` persists across ``process()`` calls for
intra-track continuity (#2390), but was never reset between pooled/cached
jobs — a loud track left the limiter deep into gain reduction and the next
track on the same pooled ``HybridProcessor`` started already attenuated by
that leftover gain, baking an audible fade-in into the rendered output.

``HybridProcessor.reset_limiter()`` closes that gap alongside the existing
``reset_dynamics()`` / ``reset_psychoacoustic_eq()`` inter-job resets (#2400).
(A fourth, ``reset_realtime_eq()``, went with the unwired real-time EQ path in
#4873.)
"""

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor


@pytest.mark.regression
class TestBrickWallLimiterInterJobReset:
    def test_reset_limiter_clears_gain_reduction_state(self):
        """Driving the limiter into gain reduction and calling reset_limiter()
        must restore current_gain to 1.0 (mirrors the audit's own repro)."""
        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # A full-scale signal well above the limiter's threshold engages
        # sustained gain reduction.
        loud_audio = np.ones((processor.brick_wall_limiter.lookahead_samples * 4, 2), dtype=np.float32)
        processor.brick_wall_limiter.process(loud_audio)

        assert processor.brick_wall_limiter.current_gain < 1.0, (
            "Test setup did not engage the limiter — cannot verify the reset"
        )

        processor.reset_limiter()

        assert processor.brick_wall_limiter.current_gain == 1.0
        assert processor.brick_wall_limiter.buffer is None
        assert processor.brick_wall_limiter.buffer_pos == 0

    def test_second_job_on_pooled_processor_does_not_inherit_gain_reduction(self):
        """Simulates two offline jobs sharing one pooled processor instance,
        the way processing_engine.py's inter-job reset block does — the
        second job's opening samples must not be pre-attenuated by the first
        job's leftover gain reduction.

        The limiter is driven directly (rather than through a full
        process() call) so the test isolates the inter-job reset contract
        from whatever gain staging the adaptive mastering pipeline applies
        upstream of the limiter for a given input.
        """
        config = UnifiedConfig()
        processor = HybridProcessor(config)

        loud_audio = np.ones((processor.brick_wall_limiter.lookahead_samples * 4, 2), dtype=np.float32)
        processor.brick_wall_limiter.process(loud_audio)
        assert processor.brick_wall_limiter.current_gain < 1.0, (
            "Test setup did not engage the limiter — cannot verify the reset"
        )

        # Inter-job reset, exactly as processing_engine._execute_job performs it.
        processor.reset_dynamics()
        processor.reset_psychoacoustic_eq()
        processor.reset_limiter()

        rng = np.random.default_rng(0)
        quiet_track = (rng.standard_normal((4096, 2)) * 0.05).astype(np.float32)

        # Job 2 on the same processor: a fresh-processor baseline must match.
        job2_output = processor.process(quiet_track.copy())

        baseline_processor = HybridProcessor(UnifiedConfig())
        baseline_output = baseline_processor.process(quiet_track.copy())

        np.testing.assert_allclose(job2_output, baseline_output, rtol=1e-5, atol=1e-6)
