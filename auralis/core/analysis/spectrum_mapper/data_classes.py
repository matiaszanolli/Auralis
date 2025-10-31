#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Spectrum Data Classes
~~~~~~~~~~~~~~~~~~~~~

Data structures for spectrum-based processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass


@dataclass
class SpectrumPosition:
    """
    Position on the multi-dimensional processing spectrum.
    Each dimension ranges from 0.0 to 1.0.
    """
    # Input level dimension: 0.0 = very quiet, 1.0 = very loud
    input_level: float

    # Dynamic range dimension: 0.0 = highly compressed, 1.0 = very dynamic
    dynamic_range: float

    # Spectral balance: 0.0 = very dark, 1.0 = very bright
    spectral_balance: float

    # Energy level: 0.0 = calm/ambient, 1.0 = energetic/aggressive
    energy: float

    # Density: 0.0 = sparse/simple, 1.0 = dense/complex
    density: float


@dataclass
class ProcessingParameters:
    """
    Calculated processing parameters from spectrum analysis.
    These flow naturally from content, not rigid presets.
    """
    # EQ parameters (dB)
    bass_adjustment: float
    low_mid_adjustment: float
    mid_adjustment: float
    high_mid_adjustment: float
    treble_adjustment: float

    # Dynamics parameters
    compression_ratio: float
    compression_threshold: float
    compression_amount: float  # 0.0-1.0 blend (0 = no compression)

    expansion_amount: float  # 0.0-1.0 blend (0 = no expansion, for dynamics restoration)

    limiter_threshold: float
    limiter_amount: float  # 0.0-1.0 blend

    # Gain staging
    input_gain: float
    output_target_rms: float  # Target RMS level

    # Processing intensity
    eq_intensity: float  # 0.0-1.0
    dynamics_intensity: float  # 0.0-1.0
