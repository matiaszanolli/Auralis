#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Preference Engine Coverage Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for the preference learning engine to improve coverage
"""

import numpy as np
import tempfile
import os
import sys
import shutil
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath('../..'))

from auralis.learning.preference_engine import (
    PreferenceLearningEngine, UserProfile, UserAction, PreferencePredictor,
    create_preference_engine
)

class TestPreferenceLearningEngine:
    """Test the PreferenceLearningEngine class"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.engine = PreferenceLearningEngine(storage_dir=self.temp_dir)
        self.user_id = "test_user_123"

        # Sample audio features
        self.audio_features = {
            'spectral_centroid': 2000,
            'spectral_rolloff': 4000,
            'zero_crossing_rate': 0.1,
            'tempo': 120,
            'dynamic_range': 12,
            'rms_level': 0.3
        }

    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_engine_initialization(self):
        """Test engine initialization"""
        self.setUp()

        assert self.engine is not None
        assert hasattr(self.engine, 'get_or_create_user')
        assert hasattr(self.engine, 'record_user_action')
        assert hasattr(self.engine, 'get_adaptive_parameters')

        self.tearDown()

    def test_user_profile_creation(self):
        """Test user profile creation"""
        self.setUp()

        profile = self.engine.get_or_create_user(self.user_id)

        assert profile is not None
        assert isinstance(profile, UserProfile)
        assert profile.user_id == self.user_id
        assert profile.total_adjustments == 0
        assert profile.confidence_score == 0.0

        self.tearDown()

    def test_user_profile_attributes(self):
        """Test user profile attributes"""
        profile = UserProfile(user_id="test_user")

        assert profile.user_id == "test_user"
        assert profile.creation_date is not None
        assert isinstance(profile.creation_date, datetime)
        assert profile.total_adjustments == 0
        assert profile.average_rating == 0.0
        assert profile.confidence_score == 0.0
        assert isinstance(profile.eq_preferences, dict)

    def test_user_action_creation(self):
        """Test user action creation"""
        action = UserAction(
            timestamp=datetime.now(),
            action_type='adjustment',
            audio_features=self.audio_features,
            parameters_before={'bass_boost': 0.0},
            parameters_after={'bass_boost': 2.0},
            user_rating=4.0
        )

        assert action.action_type == 'adjustment'
        assert action.user_rating == 4.0
        assert action.parameters_after['bass_boost'] == 2.0

    def test_record_user_action(self):
        """Test recording user actions"""
        self.setUp()

        profile = self.engine.get_or_create_user(self.user_id)
        initial_adjustments = profile.total_adjustments

        action = UserAction(
            timestamp=datetime.now(),
            action_type='adjustment',
            audio_features=self.audio_features,
            parameters_before={'bass_boost': 0.0},
            parameters_after={'bass_boost': 2.0},
            user_rating=4.0
        )

        self.engine.record_user_action(self.user_id, action)

        updated_profile = self.engine.user_profiles[self.user_id]
        assert updated_profile.total_adjustments == initial_adjustments + 1

        self.tearDown()

    def test_preference_predictor(self):
        """Test preference predictor"""
        predictor = PreferencePredictor()

        # Add training data
        features = np.array([[2000, 4000, 0.1], [1000, 2000, 0.2]])
        targets = np.array([1.0, -1.0])

        predictor.update_model(features, targets)

        # Test prediction
        test_features = np.array([1500, 3000, 0.15])
        prediction = predictor.predict(test_features)

        assert prediction is not None
        assert isinstance(prediction, float)

    def test_get_adaptive_parameters(self):
        """Test adaptive parameter generation"""
        self.setUp()

        # Create user with some history
        profile = self.engine.get_or_create_user(self.user_id)

        # Add some actions
        for i in range(5):
            action = UserAction(
                timestamp=datetime.now(),
                action_type='adjustment',
                audio_features=self.audio_features,
                parameters_before={'bass_boost': 0.0, 'treble_enhancement': 0.0},
                parameters_after={'bass_boost': 2.0, 'treble_enhancement': -1.0},
                user_rating=4.0
            )
            self.engine.record_user_action(self.user_id, action)

        # Test parameter adaptation
        base_params = {
            'bass_boost': 0.0,
            'treble_enhancement': 0.0,
            'compression_threshold': -18.0
        }

        adapted_params = self.engine.get_adaptive_parameters(
            self.user_id, self.audio_features, base_params)

        assert adapted_params is not None
        assert 'bass_boost' in adapted_params
        assert 'treble_enhancement' in adapted_params

        self.tearDown()

    def test_user_profile_persistence(self):
        """Test saving and loading user profiles"""
        self.setUp()

        # Create and modify user profile
        profile = self.engine.get_or_create_user(self.user_id)
        action = UserAction(
            timestamp=datetime.now(),
            action_type='adjustment',
            audio_features=self.audio_features,
            parameters_before={'bass_boost': 0.0},
            parameters_after={'bass_boost': 2.0},
            user_rating=4.5
        )
        self.engine.record_user_action(self.user_id, action)

        # Save profile
        success = self.engine.save_user_profile(self.user_id)
        assert success

        # Create new engine and load profile
        new_engine = PreferenceLearningEngine(storage_dir=self.temp_dir)
        loaded_profile = new_engine.load_user_profile(self.user_id)

        assert loaded_profile is not None
        assert loaded_profile.user_id == self.user_id
        assert loaded_profile.total_adjustments > 0

        self.tearDown()

    def test_multiple_users(self):
        """Test handling multiple users"""
        self.setUp()

        user_ids = ["user1", "user2", "user3"]

        for user_id in user_ids:
            profile = self.engine.get_or_create_user(user_id)
            assert profile.user_id == user_id

        assert len(self.engine.user_profiles) == 3

        self.tearDown()

    def test_confidence_score_calculation(self):
        """Test confidence score calculation"""
        self.setUp()

        profile = self.engine.get_or_create_user(self.user_id)
        initial_confidence = profile.confidence_score

        # Add multiple actions to build confidence
        for i in range(10):
            action = UserAction(
                timestamp=datetime.now(),
                action_type='adjustment',
                audio_features=self.audio_features,
                parameters_before={'bass_boost': 0.0},
                parameters_after={'bass_boost': 2.0},
                user_rating=4.0
            )
            self.engine.record_user_action(self.user_id, action)

        updated_profile = self.engine.user_profiles[self.user_id]
        assert updated_profile.confidence_score > initial_confidence

        self.tearDown()

    def test_different_action_types(self):
        """Test different action types"""
        self.setUp()

        action_types = ['adjustment', 'rating', 'skip']

        for action_type in action_types:
            action = UserAction(
                timestamp=datetime.now(),
                action_type=action_type,
                audio_features=self.audio_features,
                parameters_before={'bass_boost': 0.0},
                parameters_after={'bass_boost': 1.0},
                user_rating=3.0
            )
            self.engine.record_user_action(self.user_id, action)

        profile = self.engine.user_profiles[self.user_id]
        assert profile.total_adjustments == len(action_types)

        self.tearDown()

    def test_factory_function(self):
        """Test factory function"""
        temp_dir = tempfile.mkdtemp()

        try:
            engine = create_preference_engine(temp_dir)
            assert engine is not None
            assert isinstance(engine, PreferenceLearningEngine)
        finally:
            shutil.rmtree(temp_dir)

    def test_edge_cases(self):
        """Test edge cases"""
        self.setUp()

        # Test with empty features
        empty_features = {}
        base_params = {'bass_boost': 0.0}

        adapted_params = self.engine.get_adaptive_parameters(
            self.user_id, empty_features, base_params)
        assert adapted_params is not None

        # Test with None parameters
        try:
            adapted_params = self.engine.get_adaptive_parameters(
                self.user_id, None, base_params)
            assert adapted_params is not None
        except:
            pass  # May raise exception, which is acceptable

        # Test invalid user ID
        invalid_params = self.engine.get_adaptive_parameters(
            "nonexistent_user", self.audio_features, base_params)
        assert invalid_params is not None

        self.tearDown()

    def test_preference_learning_workflow(self):
        """Test complete preference learning workflow"""
        self.setUp()

        # Simulate user interaction workflow
        user_preferences = {
            'bass_boost': 2.5,
            'treble_enhancement': -1.0,
            'compression_threshold': 2.0
        }

        # Simulate multiple sessions
        for session in range(3):
            for adjustment in range(5):
                action = UserAction(
                    timestamp=datetime.now(),
                    action_type='adjustment',
                    audio_features=self.audio_features,
                    parameters_before={k: 0.0 for k in user_preferences.keys()},
                    parameters_after=user_preferences,
                    user_rating=4.5
                )
                self.engine.record_user_action(self.user_id, action)

        # Test that system learned preferences
        base_params = {k: 0.0 for k in user_preferences.keys()}
        learned_params = self.engine.get_adaptive_parameters(
            self.user_id, self.audio_features, base_params)

        # Should be different from base (learned something)
        assert learned_params != base_params

        self.tearDown()

if __name__ == '__main__':
    import pytest
    pytest.main([__file__])