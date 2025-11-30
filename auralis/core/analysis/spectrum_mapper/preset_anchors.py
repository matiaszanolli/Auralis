#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Preset Anchor Definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~

Defines preset anchor points on the processing spectrum

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Tuple
from .data_classes import SpectrumPosition, ProcessingParameters


def get_preset_anchors() -> Dict[str, Tuple[SpectrumPosition, ProcessingParameters]]:
    """
    Define presets as anchor points on the spectrum.
    Each preset has a position and corresponding parameters.

    Returns:
        Dictionary mapping preset names to (position, parameters) tuples
    """
    return {
        'gentle': (
            SpectrumPosition(
                input_level=0.6,  # Well-leveled
                dynamic_range=0.8,  # Preserve dynamics
                spectral_balance=0.6,  # Balanced, slightly bright
                energy=0.4,  # Moderate energy
                density=0.5,  # Medium complexity
            ),
            ProcessingParameters(
                bass_adjustment=0.3,
                low_mid_adjustment=0.0,
                mid_adjustment=0.0,
                high_mid_adjustment=0.2,
                treble_adjustment=0.5,
                compression_ratio=1.8,
                compression_threshold=-20.0,
                compression_amount=0.5,
                expansion_amount=0.0,
                limiter_threshold=-2.0,
                limiter_amount=0.5,
                input_gain=0.0,
                output_target_rms=-15.0,
                eq_intensity=0.6,
                dynamics_intensity=0.5,
            )
        ),

        'punchy': (
            SpectrumPosition(
                input_level=0.5,  # Moderate level
                dynamic_range=0.5,  # Controlled dynamics
                spectral_balance=0.6,  # Balanced with presence
                energy=0.8,  # High energy
                density=0.7,  # Complex/busy
            ),
            ProcessingParameters(
                bass_adjustment=1.8,
                low_mid_adjustment=0.5,
                mid_adjustment=0.0,
                high_mid_adjustment=1.5,
                treble_adjustment=0.8,
                compression_ratio=2.5,
                compression_threshold=-18.0,
                compression_amount=0.65,
                expansion_amount=0.0,
                limiter_threshold=-2.0,
                limiter_amount=0.65,
                input_gain=0.0,
                output_target_rms=-14.0,
                eq_intensity=0.75,
                dynamics_intensity=0.65,
            )
        ),

        'live': (
            SpectrumPosition(
                input_level=0.7,  # Often hot peaks
                dynamic_range=0.7,  # High crest factor
                spectral_balance=0.5,  # Varies, often muddy
                energy=0.7,  # High energy
                density=0.6,  # Moderate complexity
            ),
            ProcessingParameters(
                bass_adjustment=0.8,
                low_mid_adjustment=-0.8,  # Reduce mud
                mid_adjustment=0.5,
                high_mid_adjustment=2.0,  # Clarity
                treble_adjustment=1.5,
                compression_ratio=1.8,
                compression_threshold=-22.0,
                compression_amount=0.4,
                expansion_amount=0.0,
                limiter_threshold=-3.5,
                limiter_amount=0.4,
                input_gain=0.0,
                output_target_rms=-14.0,  # Reduced from -11.5 to match Matchering's +3-5 dB boost behavior
                eq_intensity=0.7,
                dynamics_intensity=0.4,
            )
        ),

        'adaptive': (
            SpectrumPosition(
                input_level=0.5,  # Center/neutral
                dynamic_range=0.8,  # Prefer preserving dynamics
                spectral_balance=0.5,  # Neutral
                energy=0.5,  # Neutral
                density=0.5,  # Neutral
            ),
            ProcessingParameters(
                bass_adjustment=0.0,
                low_mid_adjustment=0.0,
                mid_adjustment=0.0,
                high_mid_adjustment=0.0,
                treble_adjustment=0.0,
                compression_ratio=1.5,
                compression_threshold=-26.0,
                compression_amount=0.25,
                expansion_amount=0.0,
                limiter_threshold=-4.0,
                limiter_amount=0.25,
                input_gain=0.0,
                output_target_rms=-16.0,
                eq_intensity=0.4,
                dynamics_intensity=0.25,
            )
        ),
    }
