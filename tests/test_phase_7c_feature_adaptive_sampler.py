# -*- coding: utf-8 -*-

"""
Phase 7C: Feature-Adaptive Sampler Tests

Comprehensive tests for feature-level sampling strategy selection.

Test Categories:
  1. Strategy selection based on feature energy (4 tests)
  2. Adaptive interval computation (3 tests)
  3. Feature stability analysis (3 tests)
  4. Threshold configuration (2 tests)
  5. Integration tests (2 tests)
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.fingerprint.feature_adaptive_sampler import (
    FeatureAdaptiveSampler,
    SamplingStrategy,
    create_default_adaptive_sampler,
)


class TestStrategySelectionByFeatures:
    """Test sampling strategy selection based on audio characteristics"""

    def test_harmonic_rich_uses_cqt_optimized(self):
        """Harmonic-rich audio should use CQT-optimized sampling"""
        sampler = FeatureAdaptiveSampler()

        features = {
            "harmonic_energy": 0.85,  # High harmonic content
            "percussive_energy": 0.30,
            "rms_energy": 0.6,
        }

        strategy, interval, reasoning = sampler.select_sampling_strategy(features)

        assert strategy == SamplingStrategy.CQT_OPTIMIZED
        assert interval == sampler.cqt_interval_s
        assert "harmonic" in reasoning.lower()

    def test_percussive_heavy_uses_temporal_optimized(self):
        """Percussive-heavy audio should use temporal-optimized sampling"""
        sampler = FeatureAdaptiveSampler()

        features = {
            "harmonic_energy": 0.30,
            "percussive_energy": 0.85,  # High percussive content
            "rms_energy": 0.6,
        }

        strategy, interval, reasoning = sampler.select_sampling_strategy(features)

        assert strategy == SamplingStrategy.TEMPORAL_OPTIMIZED
        assert interval == sampler.temporal_interval_s
        assert "percussive" in reasoning.lower()

    def test_mixed_content_uses_standard(self):
        """Mixed content should use standard 20s interval"""
        sampler = FeatureAdaptiveSampler()

        features = {
            "harmonic_energy": 0.60,
            "percussive_energy": 0.55,
            "rms_energy": 0.6,
        }

        strategy, interval, reasoning = sampler.select_sampling_strategy(features)

        assert strategy == SamplingStrategy.STANDARD
        assert interval == sampler.standard_interval_s
        assert "mixed" in reasoning.lower()

    def test_low_energy_uses_extended(self):
        """Low energy audio should use extended intervals"""
        sampler = FeatureAdaptiveSampler()

        features = {
            "harmonic_energy": 0.40,
            "percussive_energy": 0.35,
            "rms_energy": 0.15,  # Low energy
        }

        strategy, interval, reasoning = sampler.select_sampling_strategy(features)

        assert strategy == SamplingStrategy.EXTENDED
        assert interval == sampler.extended_interval_s
        assert "low energy" in reasoning.lower()


class TestAdaptiveIntervalComputation:
    """Test adaptive interval calculation based on stability"""

    def test_stable_features_extend_interval(self):
        """Stable features should allow longer intervals"""
        sampler = FeatureAdaptiveSampler()

        base_interval = 20.0
        feature_stability = 0.95  # Very stable
        audio_length = 300.0

        interval = sampler.get_adaptive_interval(
            base_interval, feature_stability, audio_length
        )

        # High stability should increase interval slightly (up to 1.2x)
        assert interval > base_interval
        assert interval <= base_interval * 1.2

    def test_unstable_features_tighten_interval(self):
        """Unstable features should require shorter intervals"""
        sampler = FeatureAdaptiveSampler()

        base_interval = 20.0
        feature_stability = 0.3  # Unstable
        audio_length = 300.0

        interval = sampler.get_adaptive_interval(
            base_interval, feature_stability, audio_length
        )

        # Low stability should decrease interval (down to 0.8x)
        assert interval < base_interval
        assert interval >= base_interval * 0.8

    def test_adaptive_interval_respects_audio_length(self):
        """Adaptive interval should never exceed 80% of audio length"""
        sampler = FeatureAdaptiveSampler()

        base_interval = 20.0
        feature_stability = 1.0  # Perfect stability
        audio_length = 10.0  # Very short

        interval = sampler.get_adaptive_interval(
            base_interval, feature_stability, audio_length
        )

        # Should clamp to reasonable bounds
        assert interval <= audio_length * 0.8
        assert interval >= 5.0  # Minimum bound


class TestFeatureStabilityAnalysis:
    """Test feature stability analysis for adaptive sampling"""

    def test_consistent_features_returns_stable(self):
        """Consistent feature values should indicate stability"""
        sampler = FeatureAdaptiveSampler()

        # Three chunks with very similar features
        chunks = [
            {
                "spectral_centroid": 2000.0,
                "harmonic_energy": 0.8,
                "percussive_energy": 0.2,
            },
            {
                "spectral_centroid": 2010.0,
                "harmonic_energy": 0.81,
                "percussive_energy": 0.19,
            },
            {
                "spectral_centroid": 2005.0,
                "harmonic_energy": 0.79,
                "percussive_energy": 0.21,
            },
        ]

        should_adapt, details = sampler.should_use_adaptive_intervals(
            chunks, stability_threshold=0.80
        )

        # Stable features -> no adaptive intervals needed
        assert bool(should_adapt) is False
        assert details["coefficient_of_variation"] < 0.80

    def test_unstable_features_recommends_adaptation(self):
        """Unstable feature values should recommend adaptive intervals"""
        sampler = FeatureAdaptiveSampler()

        # Five chunks with highly variable features (more extreme variation)
        chunks = [
            {
                "spectral_centroid": 500.0,
                "harmonic_energy": 0.1,
                "percussive_energy": 0.9,
            },
            {
                "spectral_centroid": 4000.0,
                "harmonic_energy": 0.95,
                "percussive_energy": 0.05,
            },
            {
                "spectral_centroid": 1000.0,
                "harmonic_energy": 0.2,
                "percussive_energy": 0.8,
            },
            {
                "spectral_centroid": 3500.0,
                "harmonic_energy": 0.9,
                "percussive_energy": 0.1,
            },
            {
                "spectral_centroid": 2000.0,
                "harmonic_energy": 0.5,
                "percussive_energy": 0.5,
            },
        ]

        should_adapt, details = sampler.should_use_adaptive_intervals(
            chunks, stability_threshold=0.50
        )

        # Unstable features -> adaptive intervals recommended
        assert bool(should_adapt) is True
        assert details["coefficient_of_variation"] > 0.50

    def test_insufficient_chunks_returns_error(self):
        """Insufficient chunks should return error"""
        sampler = FeatureAdaptiveSampler()

        chunks = [{"spectral_centroid": 2000.0}]  # Only 1 chunk

        should_adapt, details = sampler.should_use_adaptive_intervals(chunks)

        assert should_adapt is False
        assert "error" in details


class TestThresholdConfiguration:
    """Test configurable energy thresholds"""

    def test_configure_harmonic_threshold(self):
        """Should be able to configure harmonic energy threshold"""
        sampler = FeatureAdaptiveSampler()

        # Default is 0.70
        assert sampler.harmonic_threshold == 0.70

        # Change to 0.80
        sampler.configure_thresholds(harmonic_threshold=0.80)

        assert sampler.harmonic_threshold == 0.80

        # Audio at 0.75 would be harmonic-rich with old threshold
        # but now be classified as mixed
        features = {
            "harmonic_energy": 0.75,
            "percussive_energy": 0.30,
            "rms_energy": 0.6,
        }

        strategy, _, _ = sampler.select_sampling_strategy(features)

        # Should be STANDARD (mixed) now, not CQT_OPTIMIZED
        assert strategy == SamplingStrategy.STANDARD

    def test_configure_sampling_intervals(self):
        """Should be able to configure sampling intervals"""
        sampler = FeatureAdaptiveSampler()

        # Change CQT interval from 12s to 10s
        sampler.configure_intervals(cqt_s=10.0)

        assert sampler.cqt_interval_s == 10.0

        # Verify it's used in strategy selection
        features = {
            "harmonic_energy": 0.85,
            "percussive_energy": 0.30,
            "rms_energy": 0.6,
        }

        strategy, interval, _ = sampler.select_sampling_strategy(features)

        assert strategy == SamplingStrategy.CQT_OPTIMIZED
        assert interval == 10.0


class TestIntegration:
    """Integration tests for feature-adaptive sampler"""

    def test_default_sampler_factory(self):
        """Default sampler factory should work correctly"""
        sampler = create_default_adaptive_sampler()

        assert sampler is not None
        assert sampler.harmonic_threshold == 0.70
        assert sampler.percussive_threshold == 0.70
        assert sampler.standard_interval_s == 20.0

    def test_complete_adaptive_workflow(self):
        """Complete workflow: analyze features and compute adaptive interval"""
        sampler = FeatureAdaptiveSampler()

        # Analyze audio features
        features = {
            "harmonic_energy": 0.75,
            "percussive_energy": 0.35,
            "rms_energy": 0.65,
        }

        strategy, base_interval, reasoning = sampler.select_sampling_strategy(features)

        # Should select CQT-optimized
        assert strategy == SamplingStrategy.CQT_OPTIMIZED
        assert base_interval == 12.0

        # Analyze chunk stability
        chunks = [
            {
                "spectral_centroid": 2000.0,
                "harmonic_energy": 0.74,
                "percussive_energy": 0.36,
            },
            {
                "spectral_centroid": 2050.0,
                "harmonic_energy": 0.76,
                "percussive_energy": 0.34,
            },
            {
                "spectral_centroid": 2020.0,
                "harmonic_energy": 0.75,
                "percussive_energy": 0.35,
            },
        ]

        should_adapt, details = sampler.should_use_adaptive_intervals(chunks)

        # Very stable features -> no adaptation needed
        assert bool(should_adapt) is False

        # Compute final adaptive interval
        final_interval = sampler.get_adaptive_interval(
            base_interval, feature_stability=0.95, audio_length_s=300.0
        )

        # Should be slightly longer than base due to stability
        assert final_interval >= base_interval


if __name__ == "__main__":
    # Run with: pytest tests/test_phase_7c_feature_adaptive_sampler.py -v
    pytest.main([__file__, "-v", "-s"])
