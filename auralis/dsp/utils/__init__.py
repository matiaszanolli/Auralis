# -*- coding: utf-8 -*-

"""
DSP Utility Functions
~~~~~~~~~~~~~~~~~~~~

Organized DSP utilities for audio processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .adaptive import (
    adaptive_gain_calculation,
    calculate_loudness_units,
    psychoacoustic_weighting,
    smooth_parameter_transition,
)
from .audio_info import (
    channel_count,
    clip,
    count_max_peaks,
    is_mono,
    is_stereo,
    mono_to_stereo,
    size,
)
from .conversion import (
    from_db,
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
    # Interpolation and envelope
    'create_triangular_envelope',
    'create_triangular_filterbank',
    'create_mel_triangular_filters',
]
