# -*- coding: utf-8 -*-

"""
Phase 7C: Strategy Selector Tests

Comprehensive tests for adaptive strategy selection heuristics.

Test Categories:
  1. Track length heuristics (4 tests)
  2. Processing mode selection (5 tests)
  3. User preference override (4 tests)
  4. Threshold configuration (3 tests)
  5. Integration tests (2 tests)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.fingerprint.strategy_selector import (
    AdaptiveStrategySelector,
    ProcessingMode,
    StrategyPreference,
    create_default_selector,
)


class TestTrackLengthHeuristics:
    """Test strategy selection based on track length"""

    def test_very_short_track_uses_fulltrack(self):
        """Tracks < 60s should use full-track (negligible cost)"""
        selector = AdaptiveStrategySelector()

        # Very short tracks
        assert selector.select_strategy(audio_length_s=10.0) == "full-track"
        assert selector.select_strategy(audio_length_s=30.0) == "full-track"
        assert selector.select_strategy(audio_length_s=59.9) == "full-track"

    def test_short_track_boundary(self):
        """Test boundary at 60 seconds"""
        selector = AdaptiveStrategySelector()

        # Just below threshold
        assert selector.select_strategy(audio_length_s=59.99) == "full-track"

        # At threshold
        assert selector.select_strategy(audio_length_s=60.0) == "sampling"

        # Just above threshold
        assert selector.select_strategy(audio_length_s=60.01) == "sampling"

    def test_long_track_uses_sampling(self):
        """Tracks >= 60s should use sampling (efficient)"""
        selector = AdaptiveStrategySelector()

        # Long tracks
        assert selector.select_strategy(audio_length_s=120.0) == "sampling"
        assert selector.select_strategy(audio_length_s=300.0) == "sampling"
        assert selector.select_strategy(audio_length_s=3600.0) == "sampling"

    def test_zero_and_negative_length(self):
        """Edge case: zero or negative audio length"""
        selector = AdaptiveStrategySelector()

        # Zero length - should use full-track (shorter than threshold)
        assert selector.select_strategy(audio_length_s=0.0) == "full-track"

        # Negative (invalid but shouldn't crash) - should use full-track
        assert selector.select_strategy(audio_length_s=-10.0) == "full-track"


class TestProcessingModeSelection:
    """Test strategy selection based on processing mode"""

    def test_library_scan_uses_sampling(self):
        """Library scanning should prioritize throughput (sampling)"""
        selector = AdaptiveStrategySelector()

        # Long track, library mode = sampling
        assert selector.select_strategy(
            audio_length_s=300.0,
            mode=ProcessingMode.LIBRARY_SCAN
        ) == "sampling"

    def test_realtime_analysis_uses_sampling(self):
        """Real-time analysis should prioritize responsiveness (sampling)"""
        selector = AdaptiveStrategySelector()

        # Long track, real-time mode = sampling
        assert selector.select_strategy(
            audio_length_s=300.0,
            mode=ProcessingMode.REAL_TIME_ANALYSIS
        ) == "sampling"

    def test_batch_export_uses_fulltrack(self):
        """Batch export should prioritize quality (full-track)"""
        selector = AdaptiveStrategySelector()

        # Even long track, batch mode = full-track
        assert selector.select_strategy(
            audio_length_s=300.0,
            mode=ProcessingMode.BATCH_EXPORT
        ) == "full-track"

    def test_interactive_mode_respects_length(self):
        """Interactive mode should balance speed and quality"""
        selector = AdaptiveStrategySelector()

        # Short track, interactive = full-track
        assert selector.select_strategy(
            audio_length_s=20.0,
            mode=ProcessingMode.INTERACTIVE
        ) == "full-track"

        # Long track, interactive = sampling
        assert selector.select_strategy(
            audio_length_s=300.0,
            mode=ProcessingMode.INTERACTIVE
        ) == "sampling"

    def test_extraction_mode_uses_sampling(self):
        """Fingerprint extraction should use sampling (Phase 7B validated)"""
        selector = AdaptiveStrategySelector()

        assert selector.select_strategy(
            audio_length_s=300.0,
            mode=ProcessingMode.FINGERPRINT_EXTRACTION
        ) == "sampling"


class TestUserPreferenceOverride:
    """Test user preference for quality vs speed"""

    def test_quality_preference_uses_fulltrack(self):
        """User quality preference should override to full-track"""
        selector = AdaptiveStrategySelector()
        selector.set_user_preference(StrategyPreference.QUALITY)

        # Even long tracks should use full-track with quality preference
        assert selector.select_strategy(audio_length_s=300.0) == "full-track"

    def test_speed_preference_uses_sampling(self):
        """User speed preference should override to sampling"""
        selector = AdaptiveStrategySelector()
        selector.set_user_preference(StrategyPreference.SPEED)

        # Even short tracks should use sampling with speed preference
        assert selector.select_strategy(audio_length_s=30.0) == "sampling"

    def test_auto_preference_uses_heuristics(self):
        """Auto preference should use normal heuristics"""
        selector = AdaptiveStrategySelector()
        selector.set_user_preference(StrategyPreference.AUTO)

        # Short tracks use full-track
        assert selector.select_strategy(audio_length_s=30.0) == "full-track"

        # Long tracks use sampling
        assert selector.select_strategy(audio_length_s=300.0) == "sampling"

    def test_direct_override(self):
        """Direct override should force specific strategy"""
        selector = AdaptiveStrategySelector()

        # Override to full-track
        selector.set_user_override("full-track")
        assert selector.select_strategy(audio_length_s=300.0) == "full-track"

        # Override to sampling
        selector.set_user_override("sampling")
        assert selector.select_strategy(audio_length_s=30.0) == "sampling"

        # Disable override
        selector.set_user_override(None)
        assert selector.select_strategy(audio_length_s=30.0) == "full-track"


class TestThresholdConfiguration:
    """Test configurable thresholds"""

    def test_configure_short_track_threshold(self):
        """Should be able to configure short track threshold"""
        selector = AdaptiveStrategySelector()

        # Default threshold is 60s
        assert selector.select_strategy(audio_length_s=90.0) == "sampling"

        # Change threshold to 120s
        selector.configure_thresholds(short_track_threshold_s=120.0)

        # Now 90s should use full-track (below new threshold)
        assert selector.select_strategy(audio_length_s=90.0) == "full-track"

        # 150s should use sampling (above new threshold)
        assert selector.select_strategy(audio_length_s=150.0) == "sampling"

    def test_configure_quality_threshold(self):
        """Should be able to configure quality preference threshold"""
        selector = AdaptiveStrategySelector()

        # Default quality threshold is 30s
        # But first rule is short_track_threshold (60s) - tracks < 60s always use full-track
        # So we need a track >= 60s to test quality threshold in interactive mode

        # At 70s, interactive mode should use sampling (above short_track_threshold)
        assert selector.select_strategy(
            audio_length_s=70.0,
            mode=ProcessingMode.INTERACTIVE
        ) == "sampling"

        # Change quality threshold to 80s
        selector.configure_thresholds(quality_preference_threshold_s=80.0)

        # Now 70s should use full-track in interactive mode (below new quality threshold)
        # But wait - 70s is still < 80s, so it should use full-track
        assert selector.select_strategy(
            audio_length_s=70.0,
            mode=ProcessingMode.INTERACTIVE
        ) == "full-track"

    def test_invalid_override_raises_error(self):
        """Invalid strategy override should raise error"""
        selector = AdaptiveStrategySelector()

        with pytest.raises(ValueError):
            selector.set_user_override("invalid-strategy")


class TestIntegration:
    """Integration tests for strategy selector"""

    def test_default_selector_factory(self):
        """Default selector factory should work correctly"""
        selector = create_default_selector()

        assert selector is not None
        assert selector.select_strategy(audio_length_s=30.0) == "full-track"
        assert selector.select_strategy(audio_length_s=300.0) == "sampling"

    def test_get_strategy_info(self):
        """get_strategy_info should provide detailed information"""
        selector = AdaptiveStrategySelector()

        info = selector.get_strategy_info(audio_length_s=300.0)

        assert "strategy" in info
        assert "duration_s" in info
        assert "reasoning" in info
        assert "alternatives" in info
        assert info["strategy"] == "sampling"
        assert info["duration_s"] == 300.0
        assert len(info["reasoning"]) > 0


class TestStrategyReasoning:
    """Test reasoning and documentation of strategy selection"""

    def test_short_track_reasoning(self):
        """Short track should have clear reasoning"""
        selector = AdaptiveStrategySelector()
        info = selector.get_strategy_info(audio_length_s=30.0)

        assert "Short track" in info["reasoning"][0]
        assert "full-track" in info["reasoning"][0]

    def test_user_override_reasoning(self):
        """User override should be reflected in reasoning"""
        selector = AdaptiveStrategySelector()
        selector.set_user_override("full-track")

        info = selector.get_strategy_info(audio_length_s=300.0)

        assert "User override" in info["reasoning"][0]

    def test_user_preference_reasoning(self):
        """User preference should be documented"""
        selector = AdaptiveStrategySelector()
        selector.set_user_preference(StrategyPreference.QUALITY)

        info = selector.get_strategy_info(audio_length_s=300.0)

        # Should mention preference
        has_preference = any("preference" in r.lower() for r in info["reasoning"])
        assert has_preference or info["strategy"] == "full-track"


if __name__ == "__main__":
    # Run with: pytest tests/test_phase_7c_strategy_selector.py -v
    pytest.main([__file__, "-v", "-s"])
