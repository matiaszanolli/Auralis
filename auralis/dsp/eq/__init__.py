"""
Psychoacoustic EQ System
~~~~~~~~~~~~~~~~~~~~~~~~

Advanced EQ processing based on human auditory perception models

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .critical_bands import CriticalBand, create_critical_bands
from .curves import generate_genre_eq_curve
from .filters import apply_eq_gains, apply_eq_mono
from .masking import MaskingThresholdCalculator
from .psychoacoustic_eq import EQSettings, PsychoacousticEQ


# Factory function for backward compatibility
def create_psychoacoustic_eq(sample_rate: int = 44100,
                            fft_size: int = 4096) -> PsychoacousticEQ:
    """Create psychoacoustic EQ with default settings"""
    settings = EQSettings(
        sample_rate=sample_rate,
        fft_size=fft_size,
        overlap=0.75,
        smoothing_factor=0.1
    )
    return PsychoacousticEQ(settings)


__all__ = [
    'PsychoacousticEQ',
    'EQSettings',
    'CriticalBand',
    'MaskingThresholdCalculator',
    'create_psychoacoustic_eq',
    'generate_genre_eq_curve',
    'create_critical_bands',
    'apply_eq_gains',
    'apply_eq_mono',
]
