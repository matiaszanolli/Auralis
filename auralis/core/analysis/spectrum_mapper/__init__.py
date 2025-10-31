#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Spectrum Mapper Module
~~~~~~~~~~~~~~~~~~~~~~~

Maps content analysis to processing parameters using spectrum-based approach

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .data_classes import SpectrumPosition, ProcessingParameters
from .spectrum_mapper import SpectrumMapper
from .preset_anchors import get_preset_anchors
from .content_modifiers import apply_content_modifiers

__all__ = [
    'SpectrumMapper',
    'SpectrumPosition',
    'ProcessingParameters',
    'get_preset_anchors',
    'apply_content_modifiers',
]
