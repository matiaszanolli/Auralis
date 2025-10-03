# -*- coding: utf-8 -*-

"""
User Preference Models
~~~~~~~~~~~~~~~~~~~~~~

Data models for user preference learning

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


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
