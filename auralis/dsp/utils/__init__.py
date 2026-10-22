"""
DSP Utility Functions
~~~~~~~~~~~~~~~~~~~~

Organized DSP utilities for audio processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .adaptive import (
    adaptive_gain_calculation,
    calculate_loudness_units,
    smooth_parameter_transition,
)
from .audio_info import (
    channel_count,
    clip,
    is_mono,
    is_stereo,
    mono_to_stereo,
    size,
    to_mono,
)
from .conversion import (
    SILENCE_FLOOR_DB,
    amplitude_to_db,
    peak_db,
    rms_db,
    to_db,
)
from .interpolation_helpers import (
    create_mel_triangular_filters,
    create_triangular_envelope,
    create_triangular_filterbank,
)
from .spectral import (
    crest_factor,
    energy_profile,
    spectral_centroid,
    spectral_rolloff,
    tempo_estimate,
    zero_crossing_rate,
)
from .stereo import (
    adjust_stereo_width,
    stereo_width_analysis,
)

__all__ = [
    # Audio info
    'size',
    'channel_count',
    'is_mono',
    'is_stereo',
    'mono_to_stereo',
    'to_mono',
    'clip',
    # Conversion
    'to_db',
    'amplitude_to_db',
    'peak_db',
    'rms_db',
    'SILENCE_FLOOR_DB',
    # Spectral analysis
    'spectral_centroid',
    'spectral_rolloff',
    'zero_crossing_rate',
    'crest_factor',
    'energy_profile',
    'tempo_estimate',
    # Adaptive processing
    'adaptive_gain_calculation',
    'smooth_parameter_transition',
    'calculate_loudness_units',
    # Stereo processing
    'stereo_width_analysis',
    'adjust_stereo_width',
    # Interpolation and envelope
    'create_triangular_envelope',
    'create_triangular_filterbank',
    'create_mel_triangular_filters',
]
