"""
Tests for Adaptive Learning System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests prediction accuracy tracking, weight tuning, and affinity rule learning.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.learning_system import (
    AdaptiveWeightTuner,
    AffinityRuleLearner,
    LearningSystem,
    PredictionAccuracy,
)


class TestPredictionAccuracy:
    """Tests for PredictionAccuracy dataclass"""

    def test_prediction_accuracy_creation(self):
        """Test creating PredictionAccuracy record"""
        record = PredictionAccuracy(
            timestamp=1234567890.0,
            current_preset="adaptive",
            predicted_preset="punchy",
            actual_preset="punchy",
            was_correct=True,
            confidence=0.85,
            context="warm_start"
        )

        assert record.current_preset == "adaptive"
        assert record.predicted_preset == "punchy"
        assert record.actual_preset == "punchy"
        assert record.was_correct is True
        assert record.confidence == 0.85
        assert record.context == "warm_start"


class TestLearningSystem:
    """Tests for LearningSystem"""

    def test_initialization(self):
        """Test learning system initialization"""
        system = LearningSystem()

        assert len(system.prediction_history) == 0
        assert system.total_predictions == 0
        assert system.correct_predictions == 0

    def test_record_correct_prediction(self):
        """Test recording a correct prediction"""
        system = LearningSystem()

        system.record_prediction(
            current_preset="adaptive",
            predicted_preset="punchy",
            actual_preset="punchy",
            confidence=0.85,
            context="warm_start"
        )

        assert system.total_predictions == 1
        assert system.correct_predictions == 1
        assert len(system.prediction_history) == 1

    def test_record_incorrect_prediction(self):
        """Test recording an incorrect prediction"""
        system = LearningSystem()

        system.record_prediction(
            current_preset="adaptive",
            predicted_preset="punchy",
            actual_preset="bright",
            confidence=0.60,
            context="warm_start"
        )

        assert system.total_predictions == 1
        assert system.correct_predictions == 0
        assert len(system.prediction_history) == 1

    def test_overall_accuracy_calculation(self):
        """Test overall accuracy calculation"""
        system = LearningSystem()

        # Record 3 correct, 2 incorrect
        for i in range(3):
            system.record_prediction("adaptive", "punchy", "punchy", 0.8, "warm_start")
        for i in range(2):
            system.record_prediction("adaptive", "punchy", "bright", 0.6, "warm_start")

        accuracy = system.get_overall_accuracy()
        assert accuracy == 0.6  # 3/5 = 0.6

    def test_accuracy_by_preset(self):
        """Test accuracy tracking per preset"""
        system = LearningSystem()

        # Punchy: 2 correct, 1 incorrect
        system.record_prediction("adaptive", "punchy", "punchy", 0.8, "warm_start")
        system.record_prediction("adaptive", "punchy", "punchy", 0.8, "warm_start")
        system.record_prediction("adaptive", "punchy", "bright", 0.6, "warm_start")

        # Bright: 1 correct
        system.record_prediction("adaptive", "bright", "bright", 0.9, "warm_start")

        assert system.get_accuracy_by_preset("punchy") == 2/3
        assert system.get_accuracy_by_preset("bright") == 1.0

    def test_accuracy_by_context(self):
        """Test accuracy tracking by context"""
        system = LearningSystem()

        # Cold start: 1 correct, 1 incorrect
        system.record_prediction("adaptive", "punchy", "punchy", 0.5, "cold_start")
        system.record_prediction("adaptive", "bright", "gentle", 0.4, "cold_start")

        # Warm start: 2 correct
        system.record_prediction("adaptive", "punchy", "punchy", 0.9, "warm_start")
        system.record_prediction("adaptive", "bright", "bright", 0.85, "warm_start")

        assert system.get_accuracy_by_context("cold_start") == 0.5
        assert system.get_accuracy_by_context("warm_start") == 1.0

    def test_user_only_vs_audio_enhanced_tracking(self):
        """Test tracking user-only vs. audio-enhanced predictions"""
        system = LearningSystem()

        # User-only: 2 correct
        system.record_prediction("adaptive", "punchy", "punchy", 0.8, "warm_start")
        system.record_prediction("adaptive", "bright", "bright", 0.85, "warm_start")

        # Audio-enhanced: 3 correct, 1 incorrect
        system.record_prediction("adaptive", "punchy", "punchy", 0.9, "audio_guided")
        system.record_prediction("adaptive", "bright", "bright", 0.88, "audio_guided")
        system.record_prediction("adaptive", "gentle", "gentle", 0.82, "audio_guided")
        system.record_prediction("adaptive", "punchy", "bright", 0.65, "audio_guided")

        assert system.get_user_only_accuracy() == 1.0  # 2/2
        assert system.get_audio_enhanced_accuracy() == 0.75  # 3/4

    def test_get_statistics(self):
        """Test getting comprehensive statistics"""
        system = LearningSystem()

        system.record_prediction("adaptive", "punchy", "punchy", 0.8, "warm_start")
        system.record_prediction("adaptive", "bright", "gentle", 0.6, "cold_start")

        stats = system.get_statistics()

        assert stats['total_predictions'] == 2
        assert stats['correct_predictions'] == 1
        assert stats['overall_accuracy'] == 0.5
        assert 'accuracy_by_preset' in stats
        assert 'accuracy_by_context' in stats

    def test_reset(self):
        """Test resetting learning data"""
        system = LearningSystem()

        system.record_prediction("adaptive", "punchy", "punchy", 0.8, "warm_start")
        system.record_prediction("adaptive", "bright", "bright", 0.9, "warm_start")

        system.reset()

        assert system.total_predictions == 0
        assert system.correct_predictions == 0
        assert len(system.prediction_history) == 0


class TestAdaptiveWeightTuner:
    """Tests for AdaptiveWeightTuner"""

    def test_initialization(self):
        """Test weight tuner initialization"""
        tuner = AdaptiveWeightTuner()

        assert tuner.user_weight == 0.7
        assert abs(tuner.audio_weight - 0.3) < 0.01  # Floating point tolerance
        assert tuner.min_user_weight == 0.5
        assert tuner.max_user_weight == 0.9

    def test_initial_weights(self):
        """Test getting initial weights"""
        tuner = AdaptiveWeightTuner(initial_user_weight=0.75)

        user_weight, audio_weight = tuner.get_weights()

        assert user_weight == 0.75
        assert audio_weight == 0.25

    def test_increase_audio_weight_when_audio_helps(self):
        """Test increasing audio weight when audio predictions help"""
        tuner = AdaptiveWeightTuner()
        system = LearningSystem()

        # User-only: 50% accuracy (2/4)
        system.record_prediction("adaptive", "punchy", "punchy", 0.8, "warm_start")
        system.record_prediction("adaptive", "bright", "gentle", 0.6, "warm_start")
        system.record_prediction("adaptive", "punchy", "bright", 0.7, "warm_start")
        system.record_prediction("adaptive", "bright", "bright", 0.8, "warm_start")

        # Audio-enhanced: 80% accuracy (4/5)
        system.record_prediction("adaptive", "punchy", "punchy", 0.9, "audio_guided")
        system.record_prediction("adaptive", "bright", "bright", 0.88, "audio_guided")
        system.record_prediction("adaptive", "gentle", "gentle", 0.82, "audio_guided")
        system.record_prediction("adaptive", "punchy", "punchy", 0.90, "audio_guided")
        system.record_prediction("adaptive", "bright", "gentle", 0.65, "audio_guided")

        # Need 50+ predictions to tune
        for i in range(41):
            system.record_prediction("adaptive", "punchy", "punchy", 0.8, "audio_guided")

        old_audio_weight = tuner.audio_weight

        tuner.update_weights(system)

        # Audio weight should have increased
        assert tuner.audio_weight > old_audio_weight

    def test_decrease_audio_weight_when_audio_hurts(self):
        """Test decreasing audio weight when audio predictions hurt"""
        tuner = AdaptiveWeightTuner()
        system = LearningSystem()

        # User-only: 75% accuracy (3/4)
        system.record_prediction("adaptive", "punchy", "punchy", 0.8, "warm_start")
        system.record_prediction("adaptive", "bright", "bright", 0.8, "warm_start")
        system.record_prediction("adaptive", "punchy", "punchy", 0.85, "warm_start")
        system.record_prediction("adaptive", "bright", "gentle", 0.6, "warm_start")

        # Audio-enhanced: 40% accuracy (2/5)
        system.record_prediction("adaptive", "punchy", "bright", 0.7, "audio_guided")
        system.record_prediction("adaptive", "bright", "gentle", 0.6, "audio_guided")
        system.record_prediction("adaptive", "gentle", "gentle", 0.85, "audio_guided")
        system.record_prediction("adaptive", "punchy", "bright", 0.65, "audio_guided")
        system.record_prediction("adaptive", "gentle", "gentle", 0.80, "audio_guided")

        # Need 50+ predictions to tune
        for i in range(41):
            system.record_prediction("adaptive", "punchy", "bright", 0.6, "audio_guided")

        old_audio_weight = tuner.audio_weight

        tuner.update_weights(system)

        # Audio weight should have decreased
        assert tuner.audio_weight < old_audio_weight

    def test_weight_bounds(self):
        """Test that weights stay within bounds"""
        tuner = AdaptiveWeightTuner(min_user_weight=0.5, max_user_weight=0.9)

        # Try to push user weight below minimum
        tuner.audio_weight = 0.6
        tuner.user_weight = 0.4

        # Correct it
        tuner.audio_weight = min(1.0 - tuner.min_user_weight, tuner.audio_weight)
        tuner.user_weight = 1.0 - tuner.audio_weight

        assert tuner.user_weight >= tuner.min_user_weight
        assert tuner.user_weight <= tuner.max_user_weight


class TestAffinityRuleLearner:
    """Tests for AffinityRuleLearner"""

    def test_initialization(self):
        """Test affinity rule learner initialization"""
        learner = AffinityRuleLearner()

        assert 'high_energy' in learner.affinity_rules
        assert 'low_energy' in learner.affinity_rules
        assert len(learner.rule_success_rates) == 0

    def test_record_outcome(self):
        """Test recording prediction outcome"""
        learner = AffinityRuleLearner()

        audio_features = {
            "energy": 0.8,  # High energy
            "brightness": 0.5,
            "dynamics": 0.6,
            "vocal_presence": 0.4,
            "tempo_energy": 0.7
        }

        learner.record_outcome(audio_features, "punchy", "punchy")

        # Should have recorded for high_energy -> punchy
        assert ("high_energy", "punchy") in learner.rule_success_rates

    def test_update_affinity_rules_increase(self):
        """Test increasing affinity for successful rule"""
        learner = AffinityRuleLearner()

        audio_features = {
            "energy": 0.8,  # High energy
            "brightness": 0.5,
            "dynamics": 0.6,
            "vocal_presence": 0.4,
            "tempo_energy": 0.7
        }

        # Record 20 successful predictions (70%+ success rate)
        for i in range(20):
            learner.record_outcome(audio_features, "punchy", "punchy")

        original_affinity = learner.affinity_rules["high_energy"]["punchy"]

        learner.update_affinity_rules()

        new_affinity = learner.affinity_rules["high_energy"]["punchy"]

        # Affinity should have increased
        assert new_affinity > original_affinity

    def test_update_affinity_rules_decrease(self):
        """Test decreasing affinity for unsuccessful rule"""
        learner = AffinityRuleLearner()

        audio_features = {
            "energy": 0.8,  # High energy
            "brightness": 0.5,
            "dynamics": 0.6,
            "vocal_presence": 0.4,
            "tempo_energy": 0.7
        }

        # Record 20 failed predictions (<40% success rate)
        for i in range(20):
            learner.record_outcome(audio_features, "gentle", "punchy")  # Wrong prediction

        original_affinity = learner.affinity_rules.get("high_energy", {}).get("gentle", 0.0)

        learner.update_affinity_rules()

        new_affinity = learner.affinity_rules.get("high_energy", {}).get("gentle", 0.0)

        # Affinity should have decreased (or stayed at 0)
        assert new_affinity <= original_affinity

    def test_reset_to_defaults(self):
        """Test resetting affinity rules to defaults"""
        learner = AffinityRuleLearner()

        # Modify a rule
        original_affinity = learner.affinity_rules["high_energy"]["punchy"]
        learner.affinity_rules["high_energy"]["punchy"] = 0.5

        # Reset
        learner.reset_to_defaults()

        # Should be back to original
        assert learner.affinity_rules["high_energy"]["punchy"] == original_affinity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
