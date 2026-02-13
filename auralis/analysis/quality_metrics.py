"""
Audio Quality Metrics - Backward Compatibility Wrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

⚠️ DEPRECATED: This module is a backward compatibility wrapper.

The actual implementation has been refactored into smaller, focused modules
under auralis/analysis/quality/

**Migration Guide:**

Import directly from submodules instead:
- QualityMetrics, QualityScores → auralis.analysis.quality.quality_metrics
- FrequencyResponseAssessor → auralis.analysis.quality.frequency_assessment
- DynamicRangeAssessor → auralis.analysis.quality.dynamic_assessment
- StereoImagingAssessor → auralis.analysis.quality.stereo_assessment
- DistortionAssessor → auralis.analysis.quality.distortion_assessment
- LoudnessAssessor → auralis.analysis.quality.loudness_assessment

This wrapper will be removed in v1.2.0.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .quality.distortion_assessment import DistortionAssessor
from .quality.dynamic_assessment import DynamicRangeAssessor
from .quality.frequency_assessment import FrequencyResponseAssessor
from .quality.loudness_assessment import LoudnessAssessor

# Re-export everything from the new modular structure
from .quality.quality_metrics import QualityMetrics, QualityScores
from .quality.stereo_assessment import StereoImagingAssessor

__all__ = [
    'QualityMetrics',
    'QualityScores',
    'FrequencyResponseAssessor',
    'DynamicRangeAssessor',
    'StereoImagingAssessor',
    'DistortionAssessor',
    'LoudnessAssessor',
]
