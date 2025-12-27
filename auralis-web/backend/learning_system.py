"""
Adaptive Learning System for Multi-Tier Buffer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tracks prediction accuracy and adapts system behavior over time.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import copy
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PredictionAccuracy:
    """Tracks a single prediction outcome."""
    timestamp: float
    current_preset: str
    predicted_preset: str
    actual_preset: str
    was_correct: bool
    confidence: float
    context: str  # "cold_start", "warm_start", "audio_guided"
    audio_features: Optional[Dict[str, float]] = None


class LearningSystem:
    """
    Tracks prediction accuracy and learns from outcomes.

    Maintains history of predictions and their outcomes to enable
    adaptive weight tuning and affinity rule learning.
    """

    def __init__(self, max_history: int = 1000):
        """
        Initialize learning system.

        Args:
            max_history: Maximum number of predictions to keep in history
        """
        self.prediction_history: Deque[PredictionAccuracy] = deque(maxlen=max_history)

        # Accuracy tracking by different dimensions
        self.accuracy_by_preset: Dict[str, List[bool]] = defaultdict(list)
        self.accuracy_by_context: Dict[str, List[bool]] = defaultdict(list)

        # For comparing user-only vs. audio-enhanced
        self.user_only_outcomes: List[bool] = []
        self.audio_enhanced_outcomes: List[bool] = []

        # Statistics
        self.total_predictions = 0
        self.correct_predictions = 0

    def record_prediction(
        self,
        current_preset: str,
        predicted_preset: str,
        actual_preset: str,
        confidence: float,
        context: str,
        audio_features: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Record a prediction and its outcome.

        Args:
            current_preset: Preset user was on when prediction was made
            predicted_preset: What we predicted they'd switch to
            actual_preset: What they actually switched to
            confidence: Prediction confidence (0.0-1.0)
            context: "cold_start", "warm_start", or "audio_guided"
            audio_features: Audio features if audio-guided prediction
        """
        was_correct = (predicted_preset == actual_preset)

        # Create record
        record = PredictionAccuracy(
            timestamp=time.time(),
            current_preset=current_preset,
            predicted_preset=predicted_preset,
            actual_preset=actual_preset,
            was_correct=was_correct,
            confidence=confidence,
            context=context,
            audio_features=audio_features
        )

        # Add to history
        self.prediction_history.append(record)

        # Update tracking
        self.accuracy_by_preset[predicted_preset].append(was_correct)
        self.accuracy_by_context[context].append(was_correct)

        # Track user-only vs. audio-enhanced
        if context == "audio_guided":
            self.audio_enhanced_outcomes.append(was_correct)
        else:
            self.user_only_outcomes.append(was_correct)

        # Update statistics
        self.total_predictions += 1
        if was_correct:
            self.correct_predictions += 1

        logger.debug(
            f"Prediction recorded: {current_preset} -> {predicted_preset} "
            f"(actual: {actual_preset}, correct: {was_correct}, "
            f"confidence: {confidence:.2f}, context: {context})"
        )

    def get_overall_accuracy(self) -> float:
        """Get overall prediction accuracy (0.0-1.0)."""
        if self.total_predictions == 0:
            return 0.0
        return self.correct_predictions / self.total_predictions

    def get_accuracy_by_preset(self, preset: str) -> float:
        """Get prediction accuracy for specific preset."""
        outcomes = self.accuracy_by_preset.get(preset, [])
        if not outcomes:
            return 0.0
        return sum(outcomes) / len(outcomes)

    def get_accuracy_by_context(self, context: str) -> float:
        """Get prediction accuracy for specific context."""
        outcomes = self.accuracy_by_context.get(context, [])
        if not outcomes:
            return 0.0
        return sum(outcomes) / len(outcomes)

    def get_user_only_accuracy(self) -> float:
        """Get accuracy for user-behavior-only predictions."""
        if not self.user_only_outcomes:
            return 0.0
        return sum(self.user_only_outcomes) / len(self.user_only_outcomes)

    def get_audio_enhanced_accuracy(self) -> float:
        """Get accuracy for audio-enhanced predictions."""
        if not self.audio_enhanced_outcomes:
            return 0.0
        return sum(self.audio_enhanced_outcomes) / len(self.audio_enhanced_outcomes)

    def get_recent_predictions(self, count: int) -> List[PredictionAccuracy]:
        """Get N most recent predictions."""
        return list(self.prediction_history)[-count:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        return {
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "overall_accuracy": self.get_overall_accuracy(),
            "user_only_accuracy": self.get_user_only_accuracy(),
            "audio_enhanced_accuracy": self.get_audio_enhanced_accuracy(),
            "accuracy_by_preset": {
                preset: self.get_accuracy_by_preset(preset)
                for preset in self.accuracy_by_preset.keys()
            },
            "accuracy_by_context": {
                context: self.get_accuracy_by_context(context)
                for context in self.accuracy_by_context.keys()
            },
        }

    def reset(self) -> None:
        """Reset all learning data."""
        self.prediction_history.clear()
        self.accuracy_by_preset.clear()
        self.accuracy_by_context.clear()
        self.user_only_outcomes.clear()
        self.audio_enhanced_outcomes.clear()
        self.total_predictions = 0
        self.correct_predictions = 0
        logger.info("Learning system reset")


class AdaptiveWeightTuner:
    """
    Dynamically adjusts user/audio weighting based on prediction accuracy.

    Starts with 70% user behavior, 30% audio content, then adapts based
    on which approach produces better predictions.
    """

    def __init__(
        self,
        initial_user_weight: float = 0.7,
        min_user_weight: float = 0.5,
        max_user_weight: float = 0.9,
        adjustment_step: float = 0.05,
        min_samples_for_tuning: int = 50
    ):
        """
        Initialize weight tuner.

        Args:
            initial_user_weight: Starting weight for user behavior (0.0-1.0)
            min_user_weight: Minimum allowed user weight
            max_user_weight: Maximum allowed user weight
            adjustment_step: How much to adjust weights per tuning cycle
            min_samples_for_tuning: Minimum predictions needed before tuning
        """
        self.user_weight = initial_user_weight
        self.audio_weight = 1.0 - initial_user_weight
        self.min_user_weight = min_user_weight
        self.max_user_weight = max_user_weight
        self.adjustment_step = adjustment_step
        self.min_samples_for_tuning = min_samples_for_tuning

        # Track tuning history
        self.tuning_history: List[Tuple[float, float, float]] = []  # (timestamp, user_weight, audio_weight)
        self.last_tuning_time = time.time()

    def update_weights(self, learning_system: LearningSystem) -> None:
        """
        Update weights based on recent prediction accuracy.

        Args:
            learning_system: LearningSystem instance with prediction history
        """
        # Need minimum samples
        if learning_system.total_predictions < self.min_samples_for_tuning:
            logger.debug(
                f"Not enough predictions for tuning "
                f"({learning_system.total_predictions}/{self.min_samples_for_tuning})"
            )
            return

        # Get accuracies
        user_only_accuracy = learning_system.get_user_only_accuracy()
        audio_enhanced_accuracy = learning_system.get_audio_enhanced_accuracy()

        # If we don't have both types of predictions, can't tune
        if user_only_accuracy == 0.0 or audio_enhanced_accuracy == 0.0:
            logger.debug("Need both user-only and audio-enhanced predictions to tune")
            return

        # Calculate improvement threshold (5%)
        improvement_threshold = 0.05

        old_user_weight = self.user_weight
        old_audio_weight = self.audio_weight

        # If audio is significantly helping, increase its weight
        if audio_enhanced_accuracy > user_only_accuracy + improvement_threshold:
            self.audio_weight = min(
                1.0 - self.min_user_weight,
                self.audio_weight + self.adjustment_step
            )
            self.user_weight = 1.0 - self.audio_weight

            logger.info(
                f"Audio helping: increased audio weight "
                f"({old_audio_weight:.2f} -> {self.audio_weight:.2f}). "
                f"Accuracies: user={user_only_accuracy:.2%}, audio={audio_enhanced_accuracy:.2%}"
            )

        # If audio is significantly hurting, decrease its weight
        elif audio_enhanced_accuracy < user_only_accuracy - improvement_threshold:
            self.audio_weight = max(
                1.0 - self.max_user_weight,
                self.audio_weight - self.adjustment_step
            )
            self.user_weight = 1.0 - self.audio_weight

            logger.info(
                f"Audio hurting: decreased audio weight "
                f"({old_audio_weight:.2f} -> {self.audio_weight:.2f}). "
                f"Accuracies: user={user_only_accuracy:.2%}, audio={audio_enhanced_accuracy:.2%}"
            )

        else:
            logger.debug(
                f"Weights unchanged: user={user_only_accuracy:.2%}, "
                f"audio={audio_enhanced_accuracy:.2%}"
            )
            return

        # Record tuning
        self.tuning_history.append((time.time(), self.user_weight, self.audio_weight))
        self.last_tuning_time = time.time()

    def get_weights(self) -> Tuple[float, float]:
        """Get current (user_weight, audio_weight) tuple."""
        return (self.user_weight, self.audio_weight)

    def get_statistics(self) -> Dict[str, Any]:
        """Get tuning statistics."""
        return {
            "user_weight": self.user_weight,
            "audio_weight": self.audio_weight,
            "tuning_count": len(self.tuning_history),
            "last_tuning_time": self.last_tuning_time,
            "tuning_history": self.tuning_history[-10:],  # Last 10 tunings
        }


class AffinityRuleLearner:
    """
    Learns which audio features predict which presets.

    Starts with default affinity rules, then refines them based on
    observed outcomes.
    """

    def __init__(self, default_rules: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize affinity rule learner.

        Args:
            default_rules: Default affinity rules (from audio_content_predictor)
        """
        # Import default rules if not provided
        if default_rules is None:
            from audio_content_predictor import get_audio_content_predictor
            predictor = get_audio_content_predictor()
            default_rules = copy.deepcopy(predictor.affinity_rules)

        self.affinity_rules = copy.deepcopy(default_rules)
        self.original_rules = copy.deepcopy(default_rules)

        # Track success rates for each (feature_condition, preset) pair
        self.rule_success_rates: Dict[Tuple[str, str], List[bool]] = defaultdict(list)

        # Tuning parameters
        self.min_samples_for_update = 20
        self.adjustment_step = 0.05

    def record_outcome(
        self,
        audio_features: Dict[str, float],
        predicted_preset: str,
        actual_preset: str,
    ) -> None:
        """
        Record whether an audio-based prediction was correct.

        Args:
            audio_features: Audio features that led to prediction
            predicted_preset: What we predicted
            actual_preset: What actually happened
        """
        # Determine which feature conditions were active
        active_features = self._get_active_features(audio_features)

        # Record success/failure for each feature-preset pair
        was_correct = (predicted_preset == actual_preset)
        for feature in active_features:
            key = (feature, predicted_preset)
            self.rule_success_rates[key].append(was_correct)

    def _get_active_features(self, audio_features: Dict[str, float]) -> List[str]:
        """Determine which feature conditions are active."""
        active = []

        energy = audio_features.get("energy", 0.0)
        brightness = audio_features.get("brightness", 0.0)
        dynamics = audio_features.get("dynamics", 0.0)
        vocal_presence = audio_features.get("vocal_presence", 0.0)
        tempo_energy = audio_features.get("tempo_energy", 0.0)

        if energy > 0.6:
            active.append("high_energy")
        if energy < 0.4:
            active.append("low_energy")
        if brightness > 0.6:
            active.append("high_brightness")
        if vocal_presence > 0.6:
            active.append("high_vocals")
        if dynamics > 0.6:
            active.append("high_dynamics")
        if dynamics < 0.4:
            active.append("low_dynamics")
        if tempo_energy > 0.6:
            active.append("high_tempo")

        return active

    def update_affinity_rules(self) -> None:
        """Update affinity rules based on observed success rates."""
        updated_count = 0

        for (feature, preset), outcomes in self.rule_success_rates.items():
            if len(outcomes) < self.min_samples_for_update:
                continue  # Need more data

            success_rate = sum(outcomes) / len(outcomes)
            current_affinity = self.affinity_rules.get(feature, {}).get(preset, 0.0)

            # If rule is working well (>70% success), increase affinity
            if success_rate > 0.7:
                new_affinity = min(1.0, current_affinity + self.adjustment_step)
                if feature not in self.affinity_rules:
                    self.affinity_rules[feature] = {}
                self.affinity_rules[feature][preset] = new_affinity
                updated_count += 1

                logger.debug(
                    f"Increased affinity: {feature} -> {preset}: "
                    f"{current_affinity:.2f} -> {new_affinity:.2f} "
                    f"(success rate: {success_rate:.2%})"
                )

            # If rule is failing (<40% success), decrease affinity
            elif success_rate < 0.4:
                new_affinity = max(0.0, current_affinity - self.adjustment_step)
                if feature not in self.affinity_rules:
                    self.affinity_rules[feature] = {}
                self.affinity_rules[feature][preset] = new_affinity
                updated_count += 1

                logger.debug(
                    f"Decreased affinity: {feature} -> {preset}: "
                    f"{current_affinity:.2f} -> {new_affinity:.2f} "
                    f"(success rate: {success_rate:.2%})"
                )

        if updated_count > 0:
            logger.info(f"Updated {updated_count} affinity rules")

    def get_statistics(self) -> Dict[str, Any]:
        """Get affinity rule learning statistics."""
        return {
            "total_rules": len(self.affinity_rules),
            "updated_rules": sum(
                1 for (feature, preset), outcomes in self.rule_success_rates.items()
                if len(outcomes) >= self.min_samples_for_update
            ),
            "rule_success_rates": {
                f"{feature} -> {preset}": {
                    "samples": len(outcomes),
                    "success_rate": sum(outcomes) / len(outcomes) if outcomes else 0.0,
                }
                for (feature, preset), outcomes in self.rule_success_rates.items()
                if len(outcomes) >= self.min_samples_for_update
            },
        }

    def reset_to_defaults(self) -> None:
        """Reset affinity rules to original defaults."""
        self.affinity_rules = copy.deepcopy(self.original_rules)
        self.rule_success_rates.clear()
        logger.info("Affinity rules reset to defaults")


# Singleton instances (optional, for convenience)
_learning_system_instance: Optional[LearningSystem] = None
_weight_tuner_instance: Optional[AdaptiveWeightTuner] = None
_affinity_learner_instance: Optional[AffinityRuleLearner] = None


def get_learning_system() -> LearningSystem:
    """Get global learning system instance."""
    global _learning_system_instance
    if _learning_system_instance is None:
        _learning_system_instance = LearningSystem()
    return _learning_system_instance


def get_weight_tuner() -> AdaptiveWeightTuner:
    """Get global weight tuner instance."""
    global _weight_tuner_instance
    if _weight_tuner_instance is None:
        _weight_tuner_instance = AdaptiveWeightTuner()
    return _weight_tuner_instance


def get_affinity_learner() -> AffinityRuleLearner:
    """Get global affinity learner instance."""
    global _affinity_learner_instance
    if _affinity_learner_instance is None:
        _affinity_learner_instance = AffinityRuleLearner()
    return _affinity_learner_instance
