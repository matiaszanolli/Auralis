# -*- coding: utf-8 -*-

"""
Auralis Learning Module
~~~~~~~~~~~~~~~~~~~~~~~

Machine learning and user preference learning components

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
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