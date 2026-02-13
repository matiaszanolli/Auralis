"""
Unified DSP System - Backward Compatibility Wrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module maintains backward compatibility while the actual implementation
has been refactored into smaller, focused modules under auralis/dsp/utils/

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

DEPRECATED: Import from auralis.dsp.utils instead
"""

# Re-export basic functions from basic.py (still needed by other modules)
from .basic import amplify, mid_side_decode, mid_side_encode, normalize, rms
from .utils.adaptive import (
    adaptive_gain_calculation,
    calculate_loudness_units,
    psychoacoustic_weighting,
    smooth_parameter_transition,
)

# Re-export everything from the new modular structure
from .utils.audio_info import (
    channel_count,
    clip,
    count_max_peaks,
    is_mono,
    is_stereo,
    mono_to_stereo,
    size,
)
from .utils.conversion import (
    from_db,
    to_db,
)
from .utils.spectral import (
    crest_factor,
    energy_profile,
    spectral_centroid,
    spectral_rolloff,
    tempo_estimate,
    zero_crossing_rate,
)
from .utils.stereo import (
    adjust_stereo_width,
    stereo_width_analysis,
)

# Maintain all public exports for backward compatibility
__all__ = [
    # Basic DSP (from basic.py)
    'rms',
    'normalize',
    'amplify',
    'mid_side_encode',
    'mid_side_decode',
    # Audio info
    'size',
    'channel_count',
    'is_mono',
    'is_stereo',
    'mono_to_stereo',
    'count_max_peaks',
    'clip',
    # Conversion
    'to_db',
    'from_db',
    # Spectral analysis
    'spectral_centroid',
    'spectral_rolloff',
    'zero_crossing_rate',
    'crest_factor',
    'energy_profile',
    'tempo_estimate',
    # Adaptive processing
    'adaptive_gain_calculation',
    'psychoacoustic_weighting',
    'smooth_parameter_transition',
    'calculate_loudness_units',
    # Stereo processing
    'stereo_width_analysis',
    'adjust_stereo_width',
]
