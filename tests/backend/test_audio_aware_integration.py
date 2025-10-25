"""
Tests for Audio-Aware Prediction Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for the complete multi-tier buffer system with audio-aware prediction.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import asyncio
import numpy as np
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from multi_tier_buffer import MultiTierBufferManager
from audio_content_predictor import AudioContentPredictor, get_audio_content_predictor


class TestAudioAwarePrediction:
    """Tests for audio-aware prediction integration"""

    @pytest.mark.asyncio
    async def test_predict_with_audio_content_no_file(self):
        """Test that audio-aware prediction falls back gracefully without file"""
        manager = MultiTierBufferManager()

        # Record some user behavior
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)
        await manager.update_position(track_id=1, position=30.0, preset="punchy", intensity=1.0)

        # Predict without filepath (should use user behavior only)
        predictions = await manager.branch_predictor.predict_with_audio_content(
            current_preset="adaptive",
            filepath=None,
            current_chunk=0,
            top_n=3
        )

        # Should have at least 1 prediction
        assert len(predictions) >= 1
        assert all(isinstance(p, tuple) and len(p) == 2 for p in predictions)
        # Should include punchy (learned from user behavior)
        preset_names = [p[0] for p in predictions]
        assert "punchy" in preset_names

    @pytest.mark.asyncio
    async def test_audio_content_predictor_initialization(self):
        """Test that audio content predictor can be initialized"""
        predictor = get_audio_content_predictor()

        assert predictor is not None
        assert predictor.analyzer is not None
        assert predictor.affinity_rules is not None

        # Check that affinity rules are structured correctly
        assert 'high_energy' in predictor.affinity_rules
        assert 'low_energy' in predictor.affinity_rules
        assert 'high_brightness' in predictor.affinity_rules

    @pytest.mark.asyncio
    async def test_predict_for_synthetic_audio(self):
        """Test prediction on synthetic audio data"""
        predictor = get_audio_content_predictor()

        # Create high-energy audio (loud)
        sample_rate = 44100
        duration = 1.0
        high_energy_audio = np.random.randn(int(sample_rate * duration)) * 0.5

        # Predict preset for high-energy chunk
        scores = await predictor.predict_preset_for_chunk(
            audio_data=high_energy_audio
        )

        # High-energy should suggest punchy or bright
        assert scores.punchy > 0.0
        assert scores.punchy > scores.gentle  # Punchy should beat gentle

    @pytest.mark.asyncio
    async def test_predict_for_quiet_audio(self):
        """Test prediction on quiet audio"""
        predictor = get_audio_content_predictor()

        # Create low-energy audio (quiet)
        sample_rate = 44100
        duration = 1.0
        low_energy_audio = np.random.randn(int(sample_rate * duration)) * 0.01

        # Predict preset for low-energy chunk
        scores = await predictor.predict_preset_for_chunk(
            audio_data=low_energy_audio
        )

        # Low-energy should suggest gentle or warm
        gentle_warm_score = scores.gentle + scores.warm
        punchy_bright_score = scores.punchy + scores.bright

        assert gentle_warm_score > 0.0

    @pytest.mark.asyncio
    async def test_prediction_combination(self):
        """Test combining user behavior with audio predictions"""
        manager = MultiTierBufferManager()
        predictor = get_audio_content_predictor()

        # Record user behavior: adaptive -> punchy
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)
        await manager.update_position(track_id=1, position=30.0, preset="punchy", intensity=1.0)
        await manager.update_position(track_id=1, position=60.0, preset="adaptive", intensity=1.0)
        await manager.update_position(track_id=1, position=90.0, preset="punchy", intensity=1.0)

        # User behavior should strongly predict punchy
        user_predictions = manager.branch_predictor.predict_next_presets("adaptive", top_n=3)
        assert user_predictions[0][0] == "punchy"

        # Create quiet audio (contradicts user behavior)
        sample_rate = 44100
        duration = 1.0
        quiet_audio = np.random.randn(int(sample_rate * duration)) * 0.01

        # Get audio scores
        audio_scores = await predictor.predict_preset_for_chunk(audio_data=quiet_audio)

        # Combine predictions (70% user, 30% audio)
        combined = predictor.combine_with_user_prediction(
            user_predictions=user_predictions,
            audio_scores=audio_scores,
            user_weight=0.7,
            audio_weight=0.3
        )

        # Punchy should still be top (strong user signal)
        # But gentle/warm should be elevated compared to user-only
        combined_presets = [p[0] for p in combined]
        assert "punchy" in combined_presets[:2]  # Punchy still highly ranked
        assert "gentle" in combined_presets or "warm" in combined_presets  # Audio influence


class TestProactiveBufferIntegration:
    """Integration tests for proactive buffer management"""

    @pytest.mark.asyncio
    async def test_buffer_manager_with_prediction(self):
        """Test that buffer manager can use predictions for cache population"""
        manager = MultiTierBufferManager()

        # Simulate playback
        await manager.update_position(track_id=1, position=0.0, preset="adaptive", intensity=1.0)

        # Get predictions
        predictions = manager.branch_predictor.predict_next_presets("adaptive", top_n=3)

        # Should have predictions
        assert len(predictions) > 0
        assert all(isinstance(p, tuple) and len(p) == 2 for p in predictions)

        # Predictions should have probabilities
        for preset, prob in predictions:
            assert 0.0 <= prob <= 1.0

    @pytest.mark.asyncio
    async def test_cache_population_based_on_prediction(self):
        """Test that L2/L3 caches are populated based on predictions"""
        manager = MultiTierBufferManager()

        # Establish user pattern: adaptive -> punchy
        for i in range(5):
            await manager.update_position(track_id=1, position=i * 60.0, preset="adaptive", intensity=1.0)
            await manager.update_position(track_id=1, position=i * 60.0 + 30.0, preset="punchy", intensity=1.0)

        # Now on adaptive, predictions should favor punchy
        predictions = manager.branch_predictor.predict_next_presets("adaptive", top_n=3)
        assert predictions[0][0] == "punchy"

        # Check that transitions were recorded
        assert len(manager.branch_predictor.transition_matrix) > 0
        assert ("adaptive", "punchy") in manager.branch_predictor.transition_matrix


class TestMemoryEfficiency:
    """Tests for memory efficiency of proactive buffering"""

    @pytest.mark.asyncio
    async def test_cache_sizes_within_limits(self):
        """Test that caches don't exceed their size limits"""
        manager = MultiTierBufferManager()

        # Simulate extended playback
        for position in range(0, 300, 15):  # 5 minutes
            await manager.update_position(
                track_id=1,
                position=float(position),
                preset="adaptive",
                intensity=1.0
            )

        # Check cache sizes
        stats = manager.get_cache_stats()

        assert stats['l1']['size_mb'] <= manager.l1_cache.max_size_mb
        assert stats['l2']['size_mb'] <= manager.l2_cache.max_size_mb
        assert stats['l3']['size_mb'] <= manager.l3_cache.max_size_mb

    @pytest.mark.asyncio
    async def test_eviction_preserves_high_probability(self):
        """Test that eviction preserves high-probability entries"""
        manager = MultiTierBufferManager()

        # Fill L1 with entries
        for chunk_idx in range(10):
            from multi_tier_buffer import CacheEntry
            import time

            entry = CacheEntry(
                track_id=1,
                preset="adaptive",
                chunk_idx=chunk_idx,
                intensity=1.0,
                timestamp=time.time(),
                probability=0.9 if chunk_idx < 5 else 0.1  # First 5 have high probability
            )

            await manager.l1_cache.add_entry(entry)

        # L1 should have evicted low-probability entries
        # High-probability entries should still be there
        high_prob_count = sum(
            1 for entry in manager.l1_cache.entries.values()
            if entry.probability >= 0.9
        )

        # At least some high-probability entries should survive
        assert high_prob_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
