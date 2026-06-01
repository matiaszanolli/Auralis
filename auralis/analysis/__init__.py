"""
Auralis Audio Analysis
~~~~~~~~~~~~~~~~~~~~~

Advanced audio analysis and measurement tools for real-time and offline processing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .dynamic_range import DynamicRangeAnalyzer
from .loudness_meter import LoudnessMeter, LUFSMeasurement
from .phase_correlation import PhaseCorrelationAnalyzer
from .quality.quality_metrics import QualityMetrics, QualityScores
from .base_spectrum_analyzer import SpectrumAnalyzer, SpectrumSettings

__all__ = [
    'SpectrumAnalyzer',
    'SpectrumSettings',
    'LoudnessMeter',
    'LUFSMeasurement',
    'PhaseCorrelationAnalyzer',
    'DynamicRangeAnalyzer',
    'QualityMetrics',
    'QualityScores'
]