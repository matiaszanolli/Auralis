"""
Core DSP Utilities
~~~~~~~~~~~~~~~~~~

Core digital signal processing utilities.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .harmonic_exciter import HarmonicExciter
from .parallel_eq import ParallelEQUtilities
from .resonance_notcher import Notch, ResonanceNotcher
from .transient_shaper import TransientShaper

__all__ = [
    'HarmonicExciter',
    'Notch',
    'ParallelEQUtilities',
    'ResonanceNotcher',
    'TransientShaper',
]
