# -*- coding: utf-8 -*-

"""
Phase 7C: Runtime Strategy Manager Tests

Comprehensive tests for runtime strategy execution and fallback mechanisms.

Test Categories:
  1. Strategy selection and execution (3 tests)
  2. Fallback logic (3 tests)
  3. Adaptive sampling parameters (2 tests)
  4. Statistics tracking (2 tests)
  5. Configuration (2 tests)
  6. Integration tests (2 tests)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.fingerprint.runtime_strategy_manager import (
    ExecutionResult,
    RuntimeStrategyManager,
    create_default_strategy_manager,
)
from auralis.analysis.fingerprint.strategy_selector import (
    ProcessingMode,
    StrategyPreference,
)


class TestStrategySelectionAndExecution:
    """Test strategy selection and execution logic"""

    def test_high_confidence_uses_sampling(self):
        """High confidence should result in sampling"""
        manager = RuntimeStrategyManager()

        audio_features = {"harmonic_energy": 0.8, "percussive_energy": 0.2}
        sampled_features = {
            "spectral_centroid": 2000.0,
            "spectral_bandwidth": 500.0,
            "temporal_centroid": 100.0,
            "harmonic_energy": 0.8,
            "pitch_mean": 440.0,
            "pitch_stability": 0.95,
            "percussive_energy": 0.2,
            "rms_energy": 0.6,
        }
        full_track_features = sampled_features.copy()  # Identical = high confidence

        strategy, result, exec_result = manager.select_and_execute_strategy(
            audio_features=audio_features,
            audio_length_s=100.0,
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        assert strategy == "sampling"
        assert exec_result == ExecutionResult.SUCCESS
        assert result["confidence_tier"] == "HIGH"

    def test_acceptable_confidence_uses_sampling_with_validation(self):
        """Acceptable confidence should result in sampling with validation flag"""
        manager = RuntimeStrategyManager()

        audio_features = {"harmonic_energy": 0.75, "percussive_energy": 0.25}
        sampled_features = {
            "spectral_centroid": 2000.0,
            "harmonic_energy": 0.75,
            "pitch_mean": 440.0,
            "rms_energy": 0.5,
            "percussive_energy": 0.25,
        }
        full_track_features = {
            "spectral_centroid": 2200.0,  # 10% difference
            "harmonic_energy": 0.70,      # 6.7% difference
            "pitch_mean": 460.0,          # 4.5% difference
            "rms_energy": 0.55,           # 10% difference
            "percussive_energy": 0.30,    # 20% difference
        }

        strategy, result, exec_result = manager.select_and_execute_strategy(
            audio_features=audio_features,
            audio_length_s=100.0,
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        assert strategy == "sampling"
        assert exec_result == ExecutionResult.PARTIAL
        assert result["validation_required"] is True
        assert result["confidence_tier"] == "ACCEPTABLE"

    def test_no_confidence_data_uses_strategy_selection(self):
        """Without confidence data, should use initial strategy selection"""
        manager = RuntimeStrategyManager()

        audio_features = {"harmonic_energy": 0.8, "percussive_energy": 0.2}
        sampled_features = {
            "spectral_centroid": 2000.0,
            "harmonic_energy": 0.8,
        }

        strategy, result, exec_result = manager.select_and_execute_strategy(
            audio_features=audio_features,
            audio_length_s=100.0,  # >= 60s -> sampling
            sampled_features=sampled_features,
        )

        assert strategy == "sampling"
        assert exec_result == ExecutionResult.SUCCESS
        assert result["confidence_score"] is None


class TestFallbackLogic:
    """Test fallback mechanisms"""

    def test_low_confidence_falls_back_to_fulltrack(self):
        """Low confidence should fallback to full-track"""
        manager = RuntimeStrategyManager()

        audio_features = {"harmonic_energy": 0.3, "percussive_energy": 0.7}
        sampled_features = {
            "spectral_centroid": 1000.0,
            "harmonic_energy": 0.3,
            "pitch_mean": 220.0,
            "rms_energy": 0.4,
            "percussive_energy": 0.7,
        }
        full_track_features = {
            "spectral_centroid": 5000.0,   # 80% difference (very high)
            "harmonic_energy": 0.7,        # 57% difference
            "pitch_mean": 880.0,           # 75% difference
            "rms_energy": 0.9,             # 55% difference
            "percussive_energy": 0.3,      # 57% difference
        }

        strategy, result, exec_result = manager.select_and_execute_strategy(
            audio_features=audio_features,
            audio_length_s=100.0,
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        assert strategy == "full-track"
        assert exec_result == ExecutionResult.FALLBACK
        assert result["confidence_tier"] == "LOW"

    def test_fallback_includes_original_strategy_info(self):
        """Fallback should preserve original strategy selection"""
        manager = RuntimeStrategyManager()

        sampled_features = {
            "spectral_centroid": 1000.0,
            "harmonic_energy": 0.3,
            "pitch_mean": 220.0,
            "rms_energy": 0.4,
            "percussive_energy": 0.7,
        }
        full_track_features = {
            "spectral_centroid": 5000.0,
            "harmonic_energy": 0.7,
            "pitch_mean": 880.0,
            "rms_energy": 0.9,
            "percussive_energy": 0.3,
        }

        strategy, result, exec_result = manager.select_and_execute_strategy(
            audio_features={},
            audio_length_s=100.0,  # >= 60s -> initial strategy is sampling
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        assert result["original_strategy"] == "sampling"  # Initial selection
        assert strategy == "full-track"  # But fell back
        assert "sampled_available" in result

    def test_validation_required_flag(self):
        """ACCEPTABLE confidence should set validation flag"""
        manager = RuntimeStrategyManager()

        sampled_features = {
            "spectral_centroid": 2000.0,
            "harmonic_energy": 0.75,
            "pitch_mean": 440.0,
            "rms_energy": 0.5,
            "percussive_energy": 0.25,
        }
        full_track_features = {
            "spectral_centroid": 2150.0,
            "harmonic_energy": 0.72,
            "pitch_mean": 450.0,
            "rms_energy": 0.52,
            "percussive_energy": 0.28,
        }

        strategy, result, exec_result = manager.select_and_execute_strategy(
            audio_features={},
            audio_length_s=100.0,
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        validation_required = manager.should_validate_results(result["confidence_score"])

        assert validation_required or result.get("validation_required", False)


class TestAdaptiveSamplingParameters:
    """Test adaptive sampling parameter selection"""

    def test_harmonic_rich_audio_optimization(self):
        """Harmonic-rich audio should return CQT-optimized parameters"""
        manager = RuntimeStrategyManager()

        audio_features = {
            "harmonic_energy": 0.85,
            "percussive_energy": 0.30,
            "rms_energy": 0.6,
        }

        strategy, interval = manager.get_adaptive_sampling_params(audio_features)

        assert strategy == "cqt"
        assert interval == manager.feature_sampler.cqt_interval_s

    def test_mixed_content_uses_standard(self):
        """Mixed content should use standard parameters"""
        manager = RuntimeStrategyManager()

        audio_features = {
            "harmonic_energy": 0.55,
            "percussive_energy": 0.50,
            "rms_energy": 0.6,
        }

        strategy, interval = manager.get_adaptive_sampling_params(audio_features)

        assert strategy == "standard"
        assert interval == manager.feature_sampler.standard_interval_s


class TestStatisticsTracking:
    """Test execution statistics tracking"""

    def test_successful_sampling_increments_stats(self):
        """Successful sampling should increment appropriate counter"""
        manager = RuntimeStrategyManager()

        sampled_features = {
            "spectral_centroid": 2000.0,
            "spectral_bandwidth": 500.0,
            "temporal_centroid": 100.0,
            "harmonic_energy": 0.8,
            "pitch_mean": 440.0,
            "pitch_stability": 0.95,
            "percussive_energy": 0.2,
            "rms_energy": 0.6,
        }

        manager.select_and_execute_strategy(
            audio_features={},
            audio_length_s=100.0,
            sampled_features=sampled_features,
            full_track_features=sampled_features.copy(),
        )

        stats = manager.get_execution_stats()

        assert stats["total_attempts"] == 1
        assert stats["successful_sampling"] >= 1

    def test_fallback_increments_fallback_counter(self):
        """Fallback should increment fallback counter"""
        manager = RuntimeStrategyManager()

        sampled_features = {
            "spectral_centroid": 1000.0,
            "harmonic_energy": 0.3,
            "pitch_mean": 220.0,
            "rms_energy": 0.4,
            "percussive_energy": 0.7,
        }
        full_track_features = {
            "spectral_centroid": 5000.0,
            "harmonic_energy": 0.7,
            "pitch_mean": 880.0,
            "rms_energy": 0.9,
            "percussive_energy": 0.3,
        }

        manager.select_and_execute_strategy(
            audio_features={},
            audio_length_s=100.0,
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        stats = manager.get_execution_stats()

        assert stats["fallback_to_fulltrack"] == 1


class TestConfiguration:
    """Test configuration options"""

    def test_set_user_preference(self):
        """Should be able to set user preference"""
        manager = RuntimeStrategyManager()

        manager.set_user_preference(StrategyPreference.QUALITY)

        assert manager.strategy_selector.user_preference == StrategyPreference.QUALITY

    def test_set_fallback_thresholds(self):
        """Should be able to configure fallback thresholds"""
        manager = RuntimeStrategyManager()

        manager.set_fallback_thresholds(
            high_confidence=0.95, acceptable_confidence=0.80
        )

        assert manager.confidence_scorer.high_confidence_threshold == 0.95
        assert manager.confidence_scorer.acceptable_confidence_threshold == 0.80


class TestIntegration:
    """Integration tests for runtime strategy manager"""

    def test_default_manager_factory(self):
        """Default manager factory should work correctly"""
        manager = create_default_strategy_manager()

        assert manager is not None
        assert manager.strategy_selector is not None
        assert manager.confidence_scorer is not None
        assert manager.feature_sampler is not None

    def test_complete_workflow(self):
        """Complete workflow: select, execute, assess, decide"""
        manager = RuntimeStrategyManager()

        # Step 1: Get adaptive sampling params
        audio_features = {
            "harmonic_energy": 0.8,
            "percussive_energy": 0.2,
            "rms_energy": 0.6,
        }

        strategy, interval = manager.get_adaptive_sampling_params(audio_features)
        assert strategy == "cqt"  # Harmonic-rich

        # Step 2: Execute with sampling and full-track
        sampled_features = {
            "spectral_centroid": 2000.0,
            "harmonic_energy": 0.80,
            "pitch_mean": 440.0,
            "pitch_stability": 0.95,
            "rms_energy": 0.6,
            "percussive_energy": 0.2,
        }
        full_track_features = {
            "spectral_centroid": 2020.0,
            "harmonic_energy": 0.81,
            "pitch_mean": 441.0,
            "pitch_stability": 0.96,
            "rms_energy": 0.61,
            "percussive_energy": 0.19,
        }

        strategy_used, result, exec_result = manager.select_and_execute_strategy(
            audio_features=audio_features,
            audio_length_s=300.0,
            processing_mode=ProcessingMode.INTERACTIVE,
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        # Step 3: Verify decision
        assert strategy_used in ["sampling", "full-track"]
        assert exec_result in [
            ExecutionResult.SUCCESS,
            ExecutionResult.PARTIAL,
            ExecutionResult.FALLBACK,
        ]
        assert result["confidence_score"] is not None

        # Step 4: Check stats
        stats = manager.get_execution_stats()
        assert stats["total_attempts"] == 1


if __name__ == "__main__":
    # Run with: pytest tests/test_phase_7c_runtime_strategy_manager.py -v
    pytest.main([__file__, "-v", "-s"])
