"""
DynamicsProcessor Compressor Settings Inter-Job Reset Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #5000, the DynamicsProcessor sibling of #4811's
brick-wall limiter defect: ``_adapt_to_content()`` mutates
``compressor.settings.{threshold_db, ratio, makeup_gain_db}`` in place on
every chunk in ADAPTIVE mode, and ``adaptation_state`` (current_lufs,
current_lra, target_threshold, target_ratio) similarly drifts — but
``DynamicsProcessor.reset()`` only cleared the compressor's envelope state
(gain_follower/previous_gain/lookahead), never ``compressor.settings`` or
``adaptation_state``. A pooled/cached ``HybridProcessor``'s second job
inherited the first job's converged compressor settings instead of starting
from the configured defaults.
"""

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.dsp.advanced_dynamics import DynamicsMode, DynamicsProcessor
from auralis.dsp.dynamics import CompressorSettings, DynamicsSettings


def _loud_electronic_content_info() -> dict:
    """content_info that _adapt_to_content maps to aggressive settings
    (threshold=-20.0, ratio=6.0) far from the CompressorSettings defaults
    (threshold=-18.0, ratio=4.0)."""
    return {
        'genre_info': {'primary': 'electronic'},
        'dynamic_range': 8.0,       # < 10 -> lighter adjustment branch
        'energy_level': 'high',     # -2.0 dB threshold adjustment
        'estimated_lufs': -8.0,
    }


@pytest.mark.regression
class TestDynamicsProcessorCompressorReset:
    def test_reset_restores_compressor_settings_and_adaptation_state(self):
        """Driving _adapt_to_content away from defaults and calling reset()
        must restore threshold_db/ratio/makeup_gain_db and adaptation_state
        to their post-__init__ values (mirrors the audit's own repro)."""
        settings = DynamicsSettings(mode=DynamicsMode.ADAPTIVE, sample_rate=44100)
        processor = DynamicsProcessor(settings)

        baseline_threshold = processor.compressor.settings.threshold_db
        baseline_ratio = processor.compressor.settings.ratio
        baseline_makeup_gain = processor.compressor.settings.makeup_gain_db
        baseline_adaptation_state = processor.adaptation_state.copy()

        audio = np.random.default_rng(0).standard_normal((4096, 2)).astype(np.float32) * 0.3
        content_info = _loud_electronic_content_info()

        # Drive adaptation across several chunks so smooth_parameter_transition
        # converges well away from the defaults (single-chunk movement is
        # deliberately gradual and wouldn't exercise the bug convincingly).
        for _ in range(20):
            processor.process(audio, content_info=content_info)

        assert processor.compressor.settings.threshold_db != baseline_threshold, (
            "Test setup did not move the compressor away from defaults — "
            "cannot verify the reset"
        )
        assert processor.compressor.settings.ratio != baseline_ratio
        assert processor.adaptation_state['current_lufs'] != baseline_adaptation_state['current_lufs']

        processor.reset()

        assert processor.compressor.settings.threshold_db == baseline_threshold
        assert processor.compressor.settings.ratio == baseline_ratio
        assert processor.compressor.settings.makeup_gain_db == baseline_makeup_gain
        assert processor.adaptation_state == baseline_adaptation_state

    def test_reset_is_a_noop_for_non_adaptive_defaults(self):
        """Sanity check: reset() on a freshly-constructed processor that never
        adapted must not change anything (no false-positive drift)."""
        processor = DynamicsProcessor(DynamicsSettings(mode=DynamicsMode.ADAPTIVE))
        threshold = processor.compressor.settings.threshold_db
        ratio = processor.compressor.settings.ratio
        state = processor.adaptation_state.copy()

        processor.reset()

        assert processor.compressor.settings.threshold_db == threshold
        assert processor.compressor.settings.ratio == ratio
        assert processor.adaptation_state == state

    def test_second_pooled_job_does_not_inherit_first_jobs_compressor_settings(self):
        """Simulates two offline jobs sharing one pooled HybridProcessor, the
        way processing_engine.py's inter-job reset block does — job 2's
        compressor settings (and therefore its output) must match a
        fresh-processor baseline, not the drifted settings job 1 converged
        the shared processor's compressor to.
        """
        config = UnifiedConfig()
        processor = HybridProcessor(config)
        dynamics_processor = processor.dynamics_manager.dynamics_processor

        baseline_threshold = dynamics_processor.compressor.settings.threshold_db
        baseline_ratio = dynamics_processor.compressor.settings.ratio

        loud_audio = np.ones((8192, 2), dtype=np.float32) * 0.9
        for _ in range(20):
            dynamics_processor.process(loud_audio, content_info=_loud_electronic_content_info())

        assert dynamics_processor.compressor.settings.threshold_db != baseline_threshold, (
            "Test setup did not engage content adaptation — cannot verify the reset"
        )

        # Inter-job reset, exactly as processing_engine._execute_job performs it.
        processor.reset_dynamics()
        processor.reset_psychoacoustic_eq()
        processor.reset_limiter()

        assert dynamics_processor.compressor.settings.threshold_db == baseline_threshold
        assert dynamics_processor.compressor.settings.ratio == baseline_ratio

        rng = np.random.default_rng(0)
        quiet_track = (rng.standard_normal((4096, 2)) * 0.05).astype(np.float32)

        job2_output = processor.process(quiet_track.copy())

        baseline_processor = HybridProcessor(UnifiedConfig())
        baseline_output = baseline_processor.process(quiet_track.copy())

        np.testing.assert_allclose(job2_output, baseline_output, rtol=1e-5, atol=1e-6)
