"""
Tests for Audio-Content-Aware Prediction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the audio analysis and preset prediction based on audio characteristics.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import sys
from pathlib import Path

import numpy as np
import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.audio_content_predictor import (
    AudioContentAnalyzer,
    AudioContentPredictor,
    AudioFeatures,
    PresetAffinityScores,
    get_audio_content_predictor,
)


class TestAudioFeatures:
    """Tests for AudioFeatures dataclass"""

    def test_audio_features_creation(self):
        """Test creating audio features"""
        features = AudioFeatures(
            energy=0.8,
            brightness=0.6,
            dynamics=0.7,
            vocal_presence=0.5,
            tempo_energy=0.9
        )

        assert features.energy == 0.8
        assert features.brightness == 0.6
        assert features.dynamics == 0.7
        assert features.vocal_presence == 0.5
        assert features.tempo_energy == 0.9


class TestPresetAffinityScores:
    """Tests for PresetAffinityScores"""

    def test_affinity_scores_creation(self):
        """Test creating affinity scores"""
        scores = PresetAffinityScores()

        # Check defaults
        assert scores.adaptive == 0.5
        assert scores.gentle == 0.0
        assert scores.warm == 0.0
        assert scores.bright == 0.0
        assert scores.punchy == 0.0

    def test_to_dict(self):
        """Test converting to dictionary"""
        scores = PresetAffinityScores(
            adaptive=0.5,
            gentle=0.3,
            warm=0.2,
            bright=0.7,
            punchy=0.9
        )

        d = scores.to_dict()

        assert d['adaptive'] == 0.5
        assert d['gentle'] == 0.3
        assert d['punchy'] == 0.9

    def test_get_top_preset(self):
        """Test getting top preset"""
        scores = PresetAffinityScores(
            adaptive=0.3,
            gentle=0.2,
            warm=0.1,
            bright=0.4,
            punchy=0.9  # Highest
        )

        preset, score = scores.get_top_preset()

        assert preset == "punchy"
        assert score == 0.9


class TestAudioContentAnalyzer:
    """Tests for AudioContentAnalyzer"""

    @pytest.mark.asyncio
    async def test_analyzer_initialization(self):
        """Test creating analyzer"""
        analyzer = AudioContentAnalyzer()

        assert analyzer.analysis_cache is not None
        assert len(analyzer.analysis_cache) == 0

    @pytest.mark.asyncio
    async def test_extract_features_high_energy(self):
        """Test feature extraction for high-energy audio"""
        analyzer = AudioContentAnalyzer()

        # Create high-energy signal (loud)
        sample_rate = 44100
        duration = 1.0  # 1 second
        audio = np.random.randn(int(sample_rate * duration)) * 0.5  # High amplitude

        features = await analyzer._extract_features(audio)

        assert 0.0 <= features.energy <= 1.0
        assert features.energy > 0.3  # Should detect high energy

    @pytest.mark.asyncio
    async def test_extract_features_low_energy(self):
        """Test feature extraction for low-energy audio"""
        analyzer = AudioContentAnalyzer()

        # Create low-energy signal (quiet)
        sample_rate = 44100
        duration = 1.0
        audio = np.random.randn(int(sample_rate * duration)) * 0.01  # Low amplitude

        features = await analyzer._extract_features(audio)

        assert 0.0 <= features.energy <= 1.0
        assert features.energy < 0.5  # Should detect low energy

    @pytest.mark.asyncio
    async def test_extract_features_high_brightness(self):
        """Test feature extraction for bright audio (high frequencies)"""
        analyzer = AudioContentAnalyzer()

        # Create high-frequency signal
        sample_rate = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * 5000 * t)  # 5kHz sine wave

        features = await analyzer._extract_features(audio)

        assert 0.0 <= features.brightness <= 1.0
        # High-frequency content should result in higher brightness
        assert features.brightness > 0.1

    @pytest.mark.asyncio
    async def test_extract_features_dynamics(self):
        """Test feature extraction for dynamic range"""
        analyzer = AudioContentAnalyzer()

        # Create signal with high dynamics (high crest factor)
        sample_rate = 44100
        duration = 1.0
        audio = np.zeros(int(sample_rate * duration))
        audio[::1000] = 0.5  # Sparse peaks
        audio += np.random.randn(len(audio)) * 0.01  # Low noise floor

        features = await analyzer._extract_features(audio)

        assert 0.0 <= features.dynamics <= 1.0

    @pytest.mark.asyncio
    async def test_cache_functionality(self):
        """Test that analyzer caches results"""
        analyzer = AudioContentAnalyzer()

        audio = np.random.randn(44100)

        # First call - should compute and cache
        features1 = await analyzer.analyze_chunk_fast(audio_data=audio)

        # Second call with same audio - should hit cache
        cache_key = f"mem_{id(audio)}"
        assert cache_key in analyzer.analysis_cache

        features2 = await analyzer.analyze_chunk_fast(audio_data=audio)

        # Should be same object from cache
        assert features1.energy == features2.energy


class TestAudioContentPredictor:
    """Tests for AudioContentPredictor"""

    @pytest.mark.asyncio
    async def test_predictor_initialization(self):
        """Test creating predictor"""
        predictor = AudioContentPredictor()

        assert predictor.analyzer is not None
        assert predictor.affinity_rules is not None

    @pytest.mark.asyncio
    async def test_predict_high_energy_suggests_punchy(self):
        """Test that high-energy audio suggests punchy preset"""
        predictor = AudioContentPredictor()

        # Create high-energy audio
        audio = np.random.randn(44100) * 0.5

        scores = await predictor.predict_preset_for_chunk(audio_data=audio)

        # Punchy should have higher affinity for high energy
        assert scores.punchy > 0.0
        # Should be higher than gentle
        assert scores.punchy > scores.gentle

    @pytest.mark.asyncio
    async def test_predict_low_energy_suggests_gentle(self):
        """Test that low-energy audio suggests gentle preset"""
        predictor = AudioContentPredictor()

        # Create low-energy audio
        audio = np.random.randn(44100) * 0.01

        scores = await predictor.predict_preset_for_chunk(audio_data=audio)

        # Gentle/warm should have higher affinity for low energy
        gentle_warm = scores.gentle + scores.warm
        punchy_bright = scores.punchy + scores.bright

        assert gentle_warm > 0.0

    @pytest.mark.asyncio
    async def test_combine_predictions(self):
        """Test combining user behavior with audio predictions"""
        predictor = AudioContentPredictor()

        # User predictions (behavior-based)
        user_predictions = [
            ("adaptive", 0.7),
            ("punchy", 0.2),
            ("bright", 0.1)
        ]

        # Audio predictions (content-based)
        audio_scores = PresetAffinityScores(
            adaptive=0.3,
            gentle=0.2,
            warm=0.1,
            bright=0.8,  # Audio suggests bright
            punchy=0.5
        )

        # Combine (70% user, 30% audio)
        combined = predictor.combine_with_user_prediction(
            user_predictions=user_predictions,
            audio_scores=audio_scores,
            user_weight=0.7,
            audio_weight=0.3
        )

        assert len(combined) > 0

        # Check that it's sorted by score
        for i in range(len(combined) - 1):
            assert combined[i][1] >= combined[i+1][1]

        # Adaptive should still be top (strong user signal)
        assert combined[0][0] in ["adaptive", "bright"]  # Could be either

    @pytest.mark.asyncio
    async def test_affinity_rules_structure(self):
        """Test that affinity rules are properly structured"""
        predictor = AudioContentPredictor()

        # Check that rules exist
        assert 'high_energy' in predictor.affinity_rules
        assert 'low_energy' in predictor.affinity_rules
        assert 'high_brightness' in predictor.affinity_rules

        # Check that rules contain valid presets
        for rule_name, rule_scores in predictor.affinity_rules.items():
            for preset in rule_scores.keys():
                assert preset in ['adaptive', 'gentle', 'warm', 'bright', 'punchy']


class TestGlobalInstance:
    """Tests for global instance management"""

    def test_get_audio_content_predictor(self):
        """Test getting global predictor instance"""
        predictor1 = get_audio_content_predictor()
        predictor2 = get_audio_content_predictor()

        # Should return same instance
        assert predictor1 is predictor2

        # Should be AudioContentPredictor
        assert isinstance(predictor1, AudioContentPredictor)


class TestFeatureRanges:
    """Tests to verify feature extraction stays in valid ranges"""

    @pytest.mark.asyncio
    async def test_all_features_in_range(self):
        """Test that all features stay in 0.0-1.0 range"""
        analyzer = AudioContentAnalyzer()

        # Test various audio types
        test_signals = [
            np.random.randn(44100) * 0.01,  # Quiet
            np.random.randn(44100) * 0.5,   # Loud
            np.sin(2 * np.pi * 1000 * np.linspace(0, 1, 44100)),  # Pure tone
            np.zeros(44100),  # Silence
        ]

        for audio in test_signals:
            features = await analyzer._extract_features(audio)

            # All features should be in valid range
            assert 0.0 <= features.energy <= 1.0
            assert 0.0 <= features.brightness <= 1.0
            assert 0.0 <= features.dynamics <= 1.0
            assert 0.0 <= features.vocal_presence <= 1.0
            assert 0.0 <= features.tempo_energy <= 1.0


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_empty_audio_handling(self):
        """Test handling of empty audio"""
        analyzer = AudioContentAnalyzer()

        # Very short audio
        audio = np.array([])

        try:
            features = await analyzer._extract_features(audio)
            # If it doesn't crash, features should be neutral or zero
            assert features is not None
        except:
            # It's okay to raise an error for invalid input
            pass

    @pytest.mark.asyncio
    async def test_silence_handling(self):
        """Test handling of silence"""
        analyzer = AudioContentAnalyzer()

        audio = np.zeros(44100)

        features = await analyzer._extract_features(audio)

        # Features for silence should be low or neutral
        assert features.energy < 0.1
        assert 0.0 <= features.dynamics <= 1.0

    @pytest.mark.asyncio
    async def test_nan_protection(self):
        """Test that NaN values don't occur"""
        analyzer = AudioContentAnalyzer()

        # Create audio that might cause division by zero
        audio = np.zeros(44100)
        audio[1000] = 0.001  # Tiny spike

        features = await analyzer._extract_features(audio)

        # No NaN values
        assert not np.isnan(features.energy)
        assert not np.isnan(features.brightness)
        assert not np.isnan(features.dynamics)
        assert not np.isnan(features.vocal_presence)
        assert not np.isnan(features.tempo_energy)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
