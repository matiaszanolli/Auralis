"""
Auralis Learning Module
~~~~~~~~~~~~~~~~~~~~~~~

Machine learning and user preference learning components

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .preference_engine import (  # type: ignore[attr-defined]
    PreferenceLearningEngine,
    UserAction,
    UserProfile,
    create_preference_engine,
)

__all__ = [
    'PreferenceLearningEngine',
    'UserProfile',
    'UserAction',
    'create_preference_engine'
]