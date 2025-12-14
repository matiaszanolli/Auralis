# -*- coding: utf-8 -*-

"""
Auralis Audio Analysis
~~~~~~~~~~~~~~~~~~~~~

Advanced audio analysis and measurement tools for real-time and offline processing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .spectrum_analyzer import SpectrumAnalyzer, SpectrumSettings  # type: ignore[attr-defined]
from .loudness_meter import LoudnessMeter, LUFSMeasurement
from .phase_correlation import PhaseCorrelationAnalyzer
from .dynamic_range import DynamicRangeAnalyzer
from .quality_metrics import QualityMetrics, QualityScores

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