"""
Psychoacoustic EQ System
~~~~~~~~~~~~~~~~~~~~~~~~

Advanced EQ processing based on human auditory perception models

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .critical_bands import CriticalBand, create_critical_bands
from .curves import generate_genre_eq_curve
from .filters import apply_eq_gains, apply_eq_mono
from .masking import MaskingThresholdCalculator
from .psychoacoustic_eq import EQSettings, PsychoacousticEQ


__all__ = [
    'PsychoacousticEQ',
    'EQSettings',
    'CriticalBand',
    'MaskingThresholdCalculator',
    'generate_genre_eq_curve',
    'create_critical_bands',
    'apply_eq_gains',
    'apply_eq_mono',
]
