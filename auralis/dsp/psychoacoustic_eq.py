# -*- coding: utf-8 -*-

"""
Psychoacoustic EQ System - Backward Compatibility Wrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module maintains backward compatibility while the actual implementation
has been refactored into smaller, focused modules under auralis/dsp/eq/

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

DEPRECATED: Import from auralis.dsp.eq instead
"""

from .eq import create_psychoacoustic_eq, generate_genre_eq_curve
from .eq.critical_bands import CriticalBand
from .eq.masking import MaskingThresholdCalculator

# Re-export everything from the new modular structure
from .eq.psychoacoustic_eq import EQSettings, PsychoacousticEQ

# Maintain all public exports for backward compatibility
__all__ = [
    'PsychoacousticEQ',
    'EQSettings',
    'CriticalBand',
    'MaskingThresholdCalculator',
    'create_psychoacoustic_eq',
    'generate_genre_eq_curve',
]
