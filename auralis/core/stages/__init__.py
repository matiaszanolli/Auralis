"""
Mastering Stage Modules
~~~~~~~~~~~~~~~~~~~~~~~~

Each module exposes a single ``apply()`` function implementing one DSP stage
of the SimpleMasteringPipeline. Stages are stateless — all shared context is
passed as explicit arguments (config, fingerprint fields).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from . import (
    air_enhancement,
    bass_enhancement,
    clarity_boost,
    harmonic_exciter,
    loudness_maximizer,
    mid_warmth,
    presence_enhancement,
    resonance_notches,
    safety_limiter,
    stereo_expansion,
    sub_bass_control,
    transient_shaper,
)

__all__ = [
    'air_enhancement',
    'bass_enhancement',
    'clarity_boost',
    'harmonic_exciter',
    'loudness_maximizer',
    'mid_warmth',
    'presence_enhancement',
    'resonance_notches',
    'safety_limiter',
    'stereo_expansion',
    'sub_bass_control',
    'transient_shaper',
]
