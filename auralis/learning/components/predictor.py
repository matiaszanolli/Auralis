# -*- coding: utf-8 -*-

"""
Preference Predictor
~~~~~~~~~~~~~~~~~~~~

ML-based preference prediction

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, Dict, List, Tuple

import numpy as np

from ...utils.logging import debug


class PreferencePredictor:
    """Predict user preferences using lightweight ML"""

    def __init__(self) -> None:
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

        self.training_data: List[Tuple[Any, Dict[str, float]]] = []
        self.is_trained: bool = False

    def add_training_sample(self, audio_features: Dict[str, float],
                          parameter_adjustments: Dict[str, float]) -> None:
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

    def _retrain_model(self) -> None:
        """Retrain the preference prediction model"""
        if len(self.training_data) < 5:
            return

        debug(f"Retraining preference model with {len(self.training_data)} samples")

        # Extract features and targets
        X = np.array([sample[0] for sample in self.training_data])
        
        # Train weights for each parameter
        for param_name in self.parameter_weights.keys():
            y = np.array([sample[1].get(param_name, 0.0) 
                         for sample in self.training_data])
            
            # Simple linear regression (closed form)
            try:
                XtX = X.T @ X
                XtX_inv = np.linalg.inv(XtX + np.eye(X.shape[1]) * 0.01)  # Ridge regularization
                weights = XtX_inv @ X.T @ y
                self.parameter_weights[param_name] = weights
            except np.linalg.LinAlgError:
                debug(f"Failed to train weights for {param_name}")

        self.is_trained = True
        debug("Preference model training complete")

    def predict_adjustments(self, audio_features: Dict[str, float]) -> Dict[str, float]:
        """Predict parameter adjustments based on audio features"""
        if not self.is_trained:
            return {}

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
            # Clip predictions to reasonable range
            predictions[param_name] = float(np.clip(prediction, -6.0, 6.0))

        return predictions

    def get_model_info(self) -> Dict[str, Any]:
        """Get model training information"""
        return {
            'is_trained': self.is_trained,
            'training_samples': len(self.training_data),
            'parameters': list(self.parameter_weights.keys())
        }
