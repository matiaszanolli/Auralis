# -*- coding: utf-8 -*-

"""
Phase 7C: End-to-End Integration and Validation Tests

Validates all Phase 7C components working together in realistic scenarios.
Tests complete workflows from audio feature analysis to final strategy decision.

Integration Test Categories:
  1. Full workflow simulations (3 tests)
  2. Edge cases and error handling (3 tests)
  3. Real-world music genre scenarios (3 tests)
  4. Performance and consistency (2 tests)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.fingerprint.confidence_scorer import ConfidenceScorer
from auralis.analysis.fingerprint.feature_adaptive_sampler import FeatureAdaptiveSampler
from auralis.analysis.fingerprint.runtime_strategy_manager import RuntimeStrategyManager
from auralis.analysis.fingerprint.strategy_selector import (
    AdaptiveStrategySelector,
    ProcessingMode,
    StrategyPreference,
)


class TestFullWorkflowSimulations:
    """Test complete end-to-end workflows"""

    def test_standard_pop_vocal_workflow(self):
        """
        Standard pop/vocal track workflow:
        - Harmonic-rich content
        - Medium length (~3 min = 180s)
        - Expects: CQT-optimized sampling with high confidence
        """
        manager = RuntimeStrategyManager()

        # Simulate pop vocal audio features
        audio_features = {
            "harmonic_energy": 0.85,
            "percussive_energy": 0.40,
            "rms_energy": 0.65,
        }

        # Get adaptive sampling params
        strategy_name, interval = manager.get_adaptive_sampling_params(audio_features)
        assert strategy_name == "cqt"
        assert interval == 12.0  # CQT-optimized interval

        # Simulate sampled and full-track analysis
        sampled_features = {
            "spectral_centroid": 2500.0,
            "spectral_bandwidth": 1000.0,
            "temporal_centroid": 120.0,
            "harmonic_energy": 0.85,
            "pitch_mean": 350.0,
            "pitch_stability": 0.92,
            "percussive_energy": 0.40,
            "rms_energy": 0.65,
        }

        full_track_features = {
            "spectral_centroid": 2530.0,  # 1.2% difference
            "spectral_bandwidth": 1010.0,  # 1% difference
            "temporal_centroid": 122.0,   # 1.7% difference
            "harmonic_energy": 0.86,      # 1.2% difference
            "pitch_mean": 352.0,          # 0.6% difference
            "pitch_stability": 0.93,      # 1.1% difference
            "percussive_energy": 0.41,    # 2.5% difference
            "rms_energy": 0.66,           # 1.5% difference
        }

        strategy_used, result, exec_result = manager.select_and_execute_strategy(
            audio_features=audio_features,
            audio_length_s=180.0,
            processing_mode=ProcessingMode.INTERACTIVE,
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        # Verify results
        assert strategy_used == "sampling"
        assert result["confidence_tier"] == "HIGH"
        assert result["validation_required"] is False

    def test_bass_heavy_percussion_workflow(self):
        """
        Bass-heavy/percussion-heavy workflow:
        - Percussive-dominant content
        - Medium-long track (~5 min = 300s)
        - Expects: Temporal-optimized sampling with acceptable confidence
        """
        manager = RuntimeStrategyManager()

        audio_features = {
            "harmonic_energy": 0.35,
            "percussive_energy": 0.80,
            "rms_energy": 0.70,
        }

        strategy_name, interval = manager.get_adaptive_sampling_params(audio_features)
        assert strategy_name == "temporal"
        assert interval == 20.0  # Standard/temporal interval

        # Slightly different percussive analysis (harder to capture precisely)
        sampled_features = {
            "spectral_centroid": 350.0,
            "spectral_bandwidth": 200.0,
            "temporal_centroid": 80.0,
            "harmonic_energy": 0.35,
            "pitch_mean": 100.0,
            "pitch_stability": 0.60,
            "percussive_energy": 0.80,
            "dynamic_range": 20.0,
            "rms_energy": 0.70,
        }

        full_track_features = {
            "spectral_centroid": 380.0,   # 8.6% difference
            "spectral_bandwidth": 220.0,  # 10% difference
            "temporal_centroid": 88.0,    # 10% difference
            "harmonic_energy": 0.32,      # 8.6% difference
            "pitch_mean": 95.0,           # 5% difference
            "pitch_stability": 0.58,      # 3.3% difference
            "percussive_energy": 0.82,    # 2.5% difference
            "dynamic_range": 22.0,        # 10% difference
            "rms_energy": 0.72,           # 2.9% difference
        }

        strategy_used, result, exec_result = manager.select_and_execute_strategy(
            audio_features=audio_features,
            audio_length_s=300.0,
            processing_mode=ProcessingMode.LIBRARY_SCAN,
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        # Percussive content has more variation, expect ACCEPTABLE
        assert strategy_used == "sampling"
        assert result["confidence_tier"] in ["ACCEPTABLE", "HIGH"]

    def test_low_energy_sparse_audio_workflow(self):
        """
        Low-energy/sparse audio workflow:
        - Quiet, sparse content (e.g., spoken word, ambient)
        - Expects: Extended interval sampling due to low energy
        """
        manager = RuntimeStrategyManager()

        audio_features = {
            "harmonic_energy": 0.25,
            "percussive_energy": 0.20,
            "rms_energy": 0.15,  # Low energy
        }

        strategy_name, interval = manager.get_adaptive_sampling_params(audio_features)
        assert strategy_name == "extended"
        assert interval == manager.feature_sampler.extended_interval_s


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error conditions"""

    def test_very_short_track_always_uses_fulltrack(self):
        """Very short tracks should always use full-track"""
        manager = RuntimeStrategyManager()

        # Short track (20 seconds)
        strategy = manager.strategy_selector.select_strategy(
            audio_length_s=20.0,
            mode=ProcessingMode.LIBRARY_SCAN,
        )

        assert strategy == "full-track"  # Even with LIBRARY_SCAN mode

    def test_zero_length_audio_handling(self):
        """Zero or negative length should be handled gracefully"""
        manager = RuntimeStrategyManager()

        strategy = manager.strategy_selector.select_strategy(
            audio_length_s=0.0,
        )

        assert strategy == "full-track"

    def test_missing_audio_features_fallback(self):
        """Missing audio features should degrade gracefully"""
        manager = RuntimeStrategyManager()

        # Empty feature dict
        strategy_name, interval = manager.get_adaptive_sampling_params({})

        # Should still return a valid strategy with defaults
        assert strategy_name in ["standard", "cqt", "temporal", "extended", "adaptive"]
        assert interval > 0


class TestRealWorldMusicGenres:
    """Test with realistic music genre feature profiles"""

    def test_acoustic_folk_workflow(self):
        """
        Acoustic/folk music:
        - Primarily harmonic (acoustic guitar, vocals)
        - Expects: CQT-optimized, high confidence
        """
        manager = RuntimeStrategyManager()

        # Acoustic folk characteristics
        sampled_features = {
            "spectral_centroid": 1800.0,
            "spectral_bandwidth": 800.0,
            "temporal_centroid": 110.0,
            "harmonic_energy": 0.75,
            "pitch_mean": 200.0,
            "pitch_stability": 0.88,
            "percussive_energy": 0.25,
            "rms_energy": 0.55,
        }

        full_track_features = sampled_features.copy()  # Nearly identical

        strategy_used, result, _ = manager.select_and_execute_strategy(
            audio_features={"harmonic_energy": 0.75, "percussive_energy": 0.25},
            audio_length_s=240.0,
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        assert strategy_used == "sampling"
        assert result["confidence_tier"] == "HIGH"

    def test_electronic_dance_workflow(self):
        """
        Electronic/dance music:
        - Balanced harmonic and percussive
        - Expects: Standard 20s interval, acceptable confidence
        """
        manager = RuntimeStrategyManager()

        sampled_features = {
            "spectral_centroid": 3000.0,
            "spectral_bandwidth": 2000.0,
            "temporal_centroid": 60.0,
            "harmonic_energy": 0.60,
            "pitch_mean": 150.0,
            "pitch_stability": 0.70,
            "percussive_energy": 0.65,
            "rms_energy": 0.75,
        }

        full_track_features = {
            "spectral_centroid": 3100.0,
            "spectral_bandwidth": 2100.0,
            "temporal_centroid": 62.0,
            "harmonic_energy": 0.58,
            "pitch_mean": 148.0,
            "pitch_stability": 0.68,
            "percussive_energy": 0.67,
            "rms_energy": 0.73,
        }

        strategy_name, interval = manager.get_adaptive_sampling_params(
            {"harmonic_energy": 0.60, "percussive_energy": 0.65}
        )

        assert strategy_name == "standard"
        assert interval == 20.0

    def test_classical_orchestral_workflow(self):
        """
        Classical/orchestral music:
        - Complex harmonic content
        - Dynamic range: low to high throughout
        - Expects: May need validation due to complexity
        """
        manager = RuntimeStrategyManager()

        sampled_features = {
            "spectral_centroid": 2200.0,
            "spectral_bandwidth": 3000.0,  # Wide spectrum
            "temporal_centroid": 150.0,
            "harmonic_energy": 0.70,
            "pitch_mean": 250.0,
            "pitch_stability": 0.75,
            "percussive_energy": 0.35,
            "dynamic_range": 40.0,  # Large dynamic range
            "rms_energy": 0.50,
        }

        full_track_features = {
            "spectral_centroid": 2350.0,   # 6.8% difference
            "spectral_bandwidth": 3200.0,  # 6.7% difference
            "temporal_centroid": 160.0,    # 6.7% difference
            "harmonic_energy": 0.68,       # 2.9% difference
            "pitch_mean": 260.0,           # 4% difference
            "pitch_stability": 0.73,       # 2.7% difference
            "percussive_energy": 0.37,     # 5.7% difference
            "dynamic_range": 42.0,         # 5% difference
            "rms_energy": 0.48,            # 4% difference
        }

        strategy_used, result, _ = manager.select_and_execute_strategy(
            audio_features={
                "harmonic_energy": 0.70,
                "percussive_energy": 0.35,
            },
            audio_length_s=600.0,  # Long classical piece
            sampled_features=sampled_features,
            full_track_features=full_track_features,
        )

        assert strategy_used in ["sampling", "full-track"]
        assert result["confidence_score"] is not None


class TestPerformanceAndConsistency:
    """Test performance characteristics and consistency"""

    def test_multiple_invocations_consistent(self):
        """Multiple calls with same inputs should yield consistent results"""
        manager = RuntimeStrategyManager()

        audio_features = {
            "harmonic_energy": 0.80,
            "percussive_energy": 0.30,
            "rms_energy": 0.60,
        }

        # Call multiple times
        results = []
        for _ in range(5):
            strategy, interval = manager.get_adaptive_sampling_params(audio_features)
            results.append((strategy, interval))

        # All results should be identical
        assert all(r == results[0] for r in results)
        assert results[0] == ("cqt", 12.0)

    def test_execution_statistics_accumulate(self):
        """Execution statistics should accumulate correctly"""
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

        # Execute 10 times
        for i in range(10):
            manager.select_and_execute_strategy(
                audio_features={},
                audio_length_s=100.0 + (i * 10),
                sampled_features=sampled_features,
                full_track_features=sampled_features.copy(),
            )

        stats = manager.get_execution_stats()

        assert stats["total_attempts"] == 10
        assert stats["sampling_rate_%"] > 0
        assert stats["error_rate_%"] == 0  # No errors


if __name__ == "__main__":
    # Run with: pytest tests/test_phase_7c_integration.py -v
    pytest.main([__file__, "-v", "-s"])
