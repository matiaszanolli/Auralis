# -*- coding: utf-8 -*-

"""
User Preference Learning Framework
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Machine learning system that adapts to user preferences over time

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Intelligent system that learns from user feedback and adjustments
"""

import numpy as np
from typing import Dict, Optional, Any, List
from dataclasses import asdict
from datetime import datetime, timedelta
import json
from pathlib import Path
import threading
from collections import defaultdict, deque

from ..utils.logging import debug, info
from .components import UserAction, UserProfile, PreferencePredictor


class PreferenceLearningEngine:
    """Main engine for learning user preferences"""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path.home() / ".auralis" / "preferences"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Active user profiles
        self.user_profiles: Dict[str, UserProfile] = {}

        # Preference predictors per user
        self.predictors: Dict[str, PreferencePredictor] = {}

        # Action history for analysis
        self.action_history: Dict[str, deque[Any]] = defaultdict(lambda: deque(maxlen=1000))

        # Learning parameters
        self.min_actions_for_learning = 5
        self.confidence_threshold = 0.3

        # Thread safety
        self.lock = threading.RLock()

        debug(f"Preference learning engine initialized at {self.storage_path}")

    def get_or_create_user(self, user_id: str) -> UserProfile:
        """Get existing user profile or create new one"""
        with self.lock:
            if user_id not in self.user_profiles:
                # Try to load from storage
                if self._load_user_profile(user_id):
                    info(f"Loaded user profile: {user_id}")
                else:
                    # Create new profile
                    self.user_profiles[user_id] = UserProfile(
                        user_id=user_id,
                        creation_date=datetime.now(),
                        last_updated=datetime.now()
                    )
                    self.predictors[user_id] = PreferencePredictor()
                    info(f"Created new user profile: {user_id}")

            return self.user_profiles[user_id]

    def record_user_action(self, user_id: str, action: UserAction) -> None:
        """Record a user action for learning"""
        with self.lock:
            profile = self.get_or_create_user(user_id)

            # Add to action history
            self.action_history[user_id].append(action)

            # Update profile statistics
            profile.total_adjustments += 1
            profile.last_updated = datetime.now()

            if action.user_rating is not None:
                # Update average rating
                alpha = 0.1  # Learning rate for rating average
                profile.average_rating = (
                    (1 - alpha) * profile.average_rating +
                    alpha * action.user_rating
                )

            # Extract parameter adjustments for learning
            adjustments = self._calculate_parameter_adjustments(
                action.parameters_before, action.parameters_after
            )

            # Add to predictor training data
            if user_id not in self.predictors:
                self.predictors[user_id] = PreferencePredictor()

            self.predictors[user_id].add_training_sample(
                action.audio_features, adjustments
            )

            # Update preference biases
            self._update_preference_biases(profile, action, adjustments)

            # Update confidence score
            self._update_confidence_score(profile)

            debug(f"Recorded action for user {user_id}: {action.action_type}")

    def _calculate_parameter_adjustments(self, before: Dict[str, float],
                                       after: Dict[str, float]) -> Dict[str, float]:
        """Calculate the difference between before and after parameters"""
        adjustments = {}

        # Calculate differences for all matching keys
        for key in before.keys():
            if key in after:
                adjustments[key] = after[key] - before[key]

        return adjustments

    def _update_preference_biases(self, profile: UserProfile, action: UserAction,
                                adjustments: Dict[str, float]) -> None:
        """Update user preference biases based on action"""

        # Update EQ preferences
        for eq_param in ['bass_boost', 'midrange_clarity', 'treble_enhancement']:
            if eq_param in adjustments:
                current_bias = profile.eq_preferences.get(eq_param, 0.0)
                adjustment = adjustments[eq_param]

                # Weighted average with learning rate
                new_bias = (
                    (1 - profile.learning_rate) * current_bias +
                    profile.learning_rate * adjustment
                )
                profile.eq_preferences[eq_param] = np.clip(new_bias, -6.0, 6.0)

        # Update dynamics preferences
        for dyn_param in ['compression_threshold', 'compression_ratio', 'limiter_threshold']:
            if dyn_param in adjustments:
                current_bias = profile.dynamics_preferences.get(dyn_param, 0.0)
                adjustment = adjustments[dyn_param]

                new_bias = (
                    (1 - profile.learning_rate) * current_bias +
                    profile.learning_rate * adjustment
                )
                profile.dynamics_preferences[dyn_param] = np.clip(new_bias, -6.0, 6.0)

        # Update high-level preferences based on adjustments
        self._update_high_level_preferences(profile, adjustments)

    def _update_high_level_preferences(self, profile: UserProfile,
                                     adjustments: Dict[str, float]) -> None:
        """Update high-level preference indicators"""

        # Brightness preference (based on treble adjustments)
        if 'treble_enhancement' in adjustments:
            treble_adj = adjustments['treble_enhancement']
            profile.brightness_preference = smooth_update(
                profile.brightness_preference,
                np.clip(treble_adj / 3.0, -1.0, 1.0),
                profile.learning_rate
            )

        # Warmth preference (based on bass adjustments)
        if 'bass_boost' in adjustments:
            bass_adj = adjustments['bass_boost']
            profile.warmth_preference = smooth_update(
                profile.warmth_preference,
                np.clip(bass_adj / 3.0, -1.0, 1.0),
                profile.learning_rate
            )

        # Dynamics preference (based on compression adjustments)
        if 'compression_ratio' in adjustments:
            comp_adj = adjustments['compression_ratio']
            # Negative adjustment = more dynamic, positive = more compressed
            dynamics_indicator = -np.clip(comp_adj / 2.0, -1.0, 1.0)
            profile.dynamics_preference = smooth_update(
                profile.dynamics_preference,
                dynamics_indicator,
                profile.learning_rate
            )

    def _update_confidence_score(self, profile: UserProfile) -> None:
        """Update confidence score based on learning history"""

        # Confidence increases with number of actions and consistency
        num_actions = profile.total_adjustments

        if num_actions < self.min_actions_for_learning:
            profile.confidence_score = 0.0
        else:
            # Base confidence from number of actions
            base_confidence = min(num_actions / 50.0, 0.8)  # Max 0.8 from actions

            # Bonus from rating consistency
            rating_bonus = 0.0
            if profile.average_rating > 0:
                # Higher ratings and consistency boost confidence
                rating_normalized = (profile.average_rating - 1.0) / 4.0  # 0-1 scale
                rating_bonus = rating_normalized * 0.2

            profile.confidence_score = min(base_confidence + rating_bonus, 1.0)

    def get_adaptive_parameters(self, user_id: str,
                              audio_features: Dict[str, float],
                              base_parameters: Dict[str, float]) -> Dict[str, float]:
        """Get parameters adapted to user preferences"""

        with self.lock:
            if user_id not in self.user_profiles:
                return base_parameters  # No learning data available

            profile = self.user_profiles[user_id]

            # Only apply learning if we have sufficient confidence
            if profile.confidence_score < self.confidence_threshold:
                return base_parameters

            adapted_params = base_parameters.copy()

            # Apply preference biases
            self._apply_preference_biases(adapted_params, profile)

            # Apply ML predictions if available
            if user_id in self.predictors and self.predictors[user_id].is_trained:
                predictions = self.predictors[user_id].predict_adjustments(audio_features)
                self._apply_predictions(adapted_params, predictions, profile.confidence_score)

            debug(f"Applied user preferences for {user_id} (confidence: {profile.confidence_score:.2f})")
            return adapted_params

    def _apply_preference_biases(self, parameters: Dict[str, float], profile: UserProfile) -> None:
        """Apply learned preference biases to parameters"""

        # Apply EQ biases
        for param, bias in profile.eq_preferences.items():
            if param in parameters:
                parameters[param] += bias * profile.confidence_score

        # Apply dynamics biases
        for param, bias in profile.dynamics_preferences.items():
            if param in parameters:
                parameters[param] += bias * profile.confidence_score

    def _apply_predictions(self, parameters: Dict[str, float],
                         predictions: Dict[str, float], confidence: float) -> None:
        """Apply ML predictions with confidence weighting"""

        prediction_weight = confidence * 0.5  # Conservative weighting

        for param, prediction in predictions.items():
            if param in parameters:
                parameters[param] += prediction * prediction_weight

    def get_user_insights(self, user_id: str) -> Dict[str, Any]:
        """Get insights about user preferences"""

        with self.lock:
            if user_id not in self.user_profiles:
                return {}

            profile = self.user_profiles[user_id]
            predictor = self.predictors.get(user_id)

            insights = {
                'profile_summary': {
                    'total_sessions': profile.total_sessions,
                    'total_adjustments': profile.total_adjustments,
                    'average_rating': profile.average_rating,
                    'confidence_score': profile.confidence_score,
                    'learning_progress': min(profile.total_adjustments / 50.0, 1.0)
                },
                'preferences': {
                    'brightness': profile.brightness_preference,
                    'warmth': profile.warmth_preference,
                    'dynamics': profile.dynamics_preference,
                    'loudness': profile.loudness_preference
                },
                'eq_biases': profile.eq_preferences,
                'dynamics_biases': profile.dynamics_preferences,
                'ml_model': predictor.get_model_info() if predictor else None
            }

            return insights

    def save_user_profile(self, user_id: str) -> bool:
        """Save user profile to storage"""
        try:
            with self.lock:
                if user_id not in self.user_profiles:
                    return False

                profile = self.user_profiles[user_id]
                profile_file = self.storage_path / f"{user_id}_profile.json"

                # Convert profile to JSON-serializable format
                profile_data = asdict(profile)
                profile_data['creation_date'] = profile.creation_date.isoformat()
                profile_data['last_updated'] = profile.last_updated.isoformat()

                with open(profile_file, 'w') as f:
                    json.dump(profile_data, f, indent=2)

                debug(f"Saved user profile: {user_id}")
                return True

        except Exception as e:
            debug(f"Failed to save user profile {user_id}: {e}")
            return False

    def _load_user_profile(self, user_id: str) -> bool:
        """Load user profile from storage"""
        try:
            profile_file = self.storage_path / f"{user_id}_profile.json"

            if not profile_file.exists():
                return False

            with open(profile_file, 'r') as f:
                profile_data = json.load(f)

            # Convert back from JSON
            profile_data['creation_date'] = datetime.fromisoformat(profile_data['creation_date'])
            profile_data['last_updated'] = datetime.fromisoformat(profile_data['last_updated'])

            # Create profile object
            self.user_profiles[user_id] = UserProfile(**profile_data)
            self.predictors[user_id] = PreferencePredictor()

            return True

        except Exception as e:
            debug(f"Failed to load user profile {user_id}: {e}")
            return False

    def cleanup_old_data(self, days_threshold: int = 90) -> None:
        """Clean up old learning data"""
        cutoff_date = datetime.now() - timedelta(days=days_threshold)

        with self.lock:
            # Clean action history
            for user_id in list(self.action_history.keys()):
                history = self.action_history[user_id]
                # Remove old actions
                filtered_history = deque(
                    [action for action in history if action.timestamp > cutoff_date],
                    maxlen=1000
                )
                self.action_history[user_id] = filtered_history

    def get_learning_statistics(self) -> Dict[str, Any]:
        """Get overall learning system statistics"""
        with self.lock:
            stats = {
                'total_users': len(self.user_profiles),
                'active_users': sum(
                    1 for profile in self.user_profiles.values()
                    if profile.last_updated > datetime.now() - timedelta(days=7)
                ),
                'total_actions': sum(
                    len(history) for history in self.action_history.values()
                ),
                'trained_models': sum(
                    1 for predictor in self.predictors.values()
                    if predictor.is_trained
                )
            }
            return stats


def smooth_update(current_value: float, new_value: float, learning_rate: float) -> float:
    """Smooth update using exponential moving average"""
    return (1 - learning_rate) * current_value + learning_rate * new_value


def create_preference_engine(storage_path: Optional[str] = None) -> PreferenceLearningEngine:
    """
    Factory function to create preference learning engine

    Args:
        storage_path: Optional path for storing user profiles

    Returns:
        Configured PreferenceLearningEngine
    """
    return PreferenceLearningEngine(storage_path)