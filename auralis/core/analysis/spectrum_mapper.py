#!/usr/bin/env python3

"""
Spectrum-Based Processing Mapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Maps content analysis to processing parameters using a spectrum-based approach.
Presets act as anchor points rather than rigid configurations.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

BACKWARD COMPATIBILITY WRAPPER
This file re-exports from the modular spectrum_mapper package.
"""

# Re-export all public classes and functions for backward compatibility
from .spectrum_mapper import (
    ProcessingParameters,
    SpectrumMapper,
    SpectrumPosition,
    apply_content_modifiers,
    get_preset_anchors,
)

__all__ = [
    'SpectrumMapper',
    'SpectrumPosition',
    'ProcessingParameters',
    'get_preset_anchors',
    'apply_content_modifiers',
]
