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
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
from pathlib import Path
import threading
from collections import defaultdict, deque

from ..utils.logging import debug, info


@dataclass
class UserAction:
    """Record of user action/preference"""
    timestamp: datetime
    action_type: str  # 'adjustment', 'rating', 'preset_selection', 'correction'
    audio_features: Dict[str, float]  # Audio characteristics when action occurred
    parameters_before: Dict[str, float]  # Processing parameters before action
    parameters_after: Dict[str, float]   # Processing parameters after action
    user_rating: Optional[float] = None  # Optional 1-5 rating
    genre: Optional[str] = None
    confidence: float = 1.0  # Confidence in this preference data


@dataclass
class UserProfile:
    """User preference profile"""
    user_id: str
    creation_date: datetime
    last_updated: datetime

    # Preference statistics
    total_sessions: int = 0
    total_adjustments: int = 0
    average_rating: float = 3.0

    # Genre preferences (normalized weights)
    genre_preferences: Dict[str, float] = None

    # Parameter preferences (bias adjustments)
    eq_preferences: Dict[str, float] = None
    dynamics_preferences: Dict[str, float] = None

    # Content-based preferences
    brightness_preference: float = 0.0  # -1 to 1 (darker to brighter)
    warmth_preference: float = 0.0      # -1 to 1 (cooler to warmer)
    dynamics_preference: float = 0.0    # -1 to 1 (compressed to dynamic)
    loudness_preference: float = 0.0    # -1 to 1 (quieter to louder)

    # Learning statistics
    learning_rate: float = 0.1
    confidence_score: float = 0.0  # 0 to 1

    def __post_init__(self):
        if self.genre_preferences is None:
            self.genre_preferences = {}
        if self.eq_preferences is None:
            self.eq_preferences = {
                'bass_boost': 0.0,
                'midrange_clarity': 0.0,
                'treble_enhancement': 0.0
            }
        if self.dynamics_preferences is None:
            self.dynamics_preferences = {
                'compression_threshold': 0.0,
                'compression_ratio': 0.0,
                'limiter_threshold': 0.0
            }


class PreferencePredictor:
    """Predict user preferences using lightweight ML"""

    def __init__(self):
        # Simple linear model for preference prediction
        self.feature_weights = {
            'spectral_centroid': 0.0,
            'spectral_rolloff': 0.0,
            'zero_crossing_rate': 0.0,
            'tempo': 0.0,
            'dynamic_range': 0.0,
            'rms_level': 0.0
        }

        # Parameter prediction weights
        self.parameter_weights = {
            'bass_boost': np.zeros(len(self.feature_weights)),
            'midrange_clarity': np.zeros(len(self.feature_weights)),
            'treble_enhancement': np.zeros(len(self.feature_weights)),
            'compression_threshold': np.zeros(len(self.feature_weights)),
            'compression_ratio': np.zeros(len(self.feature_weights))
        }

        self.training_data = []
        self.is_trained = False

    def add_training_sample(self, audio_features: Dict[str, float],
                          parameter_adjustments: Dict[str, float]):
        """Add training sample from user action"""

        # Convert features to array
        feature_array = np.array([
            audio_features.get('spectral_centroid', 2000) / 1000,  # Normalize
            audio_features.get('spectral_rolloff', 4000) / 1000,
            audio_features.get('zero_crossing_rate', 0.1),
            audio_features.get('tempo', 120) / 60,  # Normalize to ~2
            audio_features.get('dynamic_range', 15) / 30,  # Normalize to 0.5
            audio_features.get('rms_level', 0.3)
        ])

        self.training_data.append((feature_array, parameter_adjustments))

        # Retrain if we have enough samples
        if len(self.training_data) >= 10:
            self._retrain_model()

    def _retrain_model(self):
        """Retrain the preference prediction model"""
        if len(self.training_data) < 5:
            return

        debug(f"Retraining preference model with {len(self.training_data)} samples")

        # Prepare training data
        X = np.array([sample[0] for sample in self.training_data])

        # Train separate model for each parameter
        for param_name in self.parameter_weights.keys():
            y = np.array([sample[1].get(param_name, 0.0) for sample in self.training_data])

            # Simple linear regression (normal equation)
            if len(X) > len(X[0]):  # More samples than features
                try:
                    # Add bias term
                    X_bias = np.column_stack([np.ones(len(X)), X])
                    weights = np.linalg.lstsq(X_bias, y, rcond=None)[0]

                    # Store weights (excluding bias)
                    self.parameter_weights[param_name] = weights[1:]

                except np.linalg.LinAlgError:
                    # Fallback to simple averaging
                    self.parameter_weights[param_name] = np.zeros(len(self.feature_weights))

        self.is_trained = True
        debug("Preference model retrained successfully")

    def predict_adjustments(self, audio_features: Dict[str, float]) -> Dict[str, float]:
        """Predict parameter adjustments based on audio features"""

        if not self.is_trained:
            return {}  # No predictions until trained

        # Convert features to array
        feature_array = np.array([
            audio_features.get('spectral_centroid', 2000) / 1000,
            audio_features.get('spectral_rolloff', 4000) / 1000,
            audio_features.get('zero_crossing_rate', 0.1),
            audio_features.get('tempo', 120) / 60,
            audio_features.get('dynamic_range', 15) / 30,
            audio_features.get('rms_level', 0.3)
        ])

        # Predict adjustments
        predictions = {}
        for param_name, weights in self.parameter_weights.items():
            prediction = np.dot(feature_array, weights)
            # Clamp predictions to reasonable range
            predictions[param_name] = np.clip(prediction, -6.0, 6.0)

        return predictions

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the trained model"""
        return {
            'is_trained': self.is_trained,
            'training_samples': len(self.training_data),
            'feature_importance': {
                name: float(np.mean(np.abs(weights)))
                for name, weights in self.parameter_weights.items()
            }
        }


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
        self.action_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

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

    def record_user_action(self, user_id: str, action: UserAction):
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
                                adjustments: Dict[str, float]):
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
                                     adjustments: Dict[str, float]):
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

    def _update_confidence_score(self, profile: UserProfile):
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

    def _apply_preference_biases(self, parameters: Dict[str, float], profile: UserProfile):
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
                         predictions: Dict[str, float], confidence: float):
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

    def cleanup_old_data(self, days_threshold: int = 90):
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