# -*- coding: utf-8 -*-

"""
Audio Quality Metrics - Backward Compatibility Wrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module maintains backward compatibility while the actual implementation
has been refactored into smaller, focused modules under auralis/analysis/quality/

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

DEPRECATED: Import from auralis.analysis.quality instead
"""

# Re-export everything from the new modular structure
from .quality.quality_metrics import QualityMetrics, QualityScores
from .quality.frequency_assessment import FrequencyResponseAssessor
from .quality.dynamic_assessment import DynamicRangeAssessor
from .quality.stereo_assessment import StereoImagingAssessor
from .quality.distortion_assessment import DistortionAssessor
from .quality.loudness_assessment import LoudnessAssessor

__all__ = [
    'QualityMetrics',
    'QualityScores',
    'FrequencyResponseAssessor',
    'DynamicRangeAssessor',
    'StereoImagingAssessor',
    'DistortionAssessor',
    'LoudnessAssessor',
]
