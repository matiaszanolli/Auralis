# -*- coding: utf-8 -*-

"""
Preference Manager
~~~~~~~~~~~~~~~~~

Manages user preference learning and feedback

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from ...learning.preference_engine import PreferenceLearningEngine, UserAction
from ...utils.logging import info, debug


class PreferenceManager:
    """Manages user preference learning for HybridProcessor"""

    def __init__(self, preference_engine: PreferenceLearningEngine):
        self.preference_engine = preference_engine
        self.current_user_id: Optional[str] = None
        self.last_content_profile: Optional[Dict[str, Any]] = None

    def set_user(self, user_id: str):
        """Set the current user for preference learning"""
        self.current_user_id = user_id
        # Ensure user profile exists
        self.preference_engine.get_or_create_user(user_id)
        info(f"User set for preference learning: {user_id}")

    def set_content_profile(self, content_profile: Dict[str, Any]):
        """Store the current content profile for learning context"""
        self.last_content_profile = content_profile

    def record_feedback(self, rating: float,
                       parameters_before: Optional[Dict[str, float]] = None,
                       parameters_after: Optional[Dict[str, float]] = None):
        """Record user feedback for learning"""
        if not self.current_user_id:
            debug("No user set for preference learning")
            return

        if self.last_content_profile is None:
            debug("No content profile available for learning")
            return

        # Create user action record
        action = UserAction(
            timestamp=datetime.now(),
            action_type='rating',
            audio_features=self.last_content_profile,
            parameters_before=parameters_before or {},
            parameters_after=parameters_after or {},
            user_rating=rating
        )

        self.preference_engine.record_user_action(self.current_user_id, action)
        info(f"Recorded user rating: {rating}/5")

    def record_adjustment(self, parameter_name: str,
                         old_value: float, new_value: float):
        """Record user parameter adjustment for learning"""
        if not self.current_user_id or self.last_content_profile is None:
            return

        action = UserAction(
            timestamp=datetime.now(),
            action_type='adjustment',
            audio_features=self.last_content_profile,
            parameters_before={parameter_name: old_value},
            parameters_after={parameter_name: new_value}
        )

        self.preference_engine.record_user_action(self.current_user_id, action)
        debug(f"Recorded parameter adjustment: {parameter_name} {old_value} -> {new_value}")

    def get_insights(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get user preference insights"""
        target_user = user_id or self.current_user_id
        if not target_user:
            return {}

        return self.preference_engine.get_user_insights(target_user)

    def save_preferences(self, user_id: Optional[str] = None) -> bool:
        """Save user preferences to storage"""
        target_user = user_id or self.current_user_id
        if not target_user:
            return False

        return self.preference_engine.save_user_profile(target_user)
