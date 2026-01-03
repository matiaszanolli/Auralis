# -*- coding: utf-8 -*-

"""
Fingerprint Metrics Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular metrics utilities for fingerprint analysis.

This package provides a collection of utility classes for audio fingerprinting:
- Constants: Core constants and validation
- Safe operations: Numerical stability guards
- Audio metrics: RMS, loudness, dB conversions
- Normalization: Statistical normalization methods
- Aggregation: Frame-to-track aggregation
- Spectral operations: Spectral analysis utilities
- Variation metrics: Variation calculation pipelines
- Stability metrics: Stability calculation patterns
- Band normalization: EQ band mapping

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .aggregation import AggregationUtils
from .audio_metrics import AudioMetrics
from .band_normalization import BandNormalizationTable
from .constants import FingerprintConstants
from .normalization import MetricUtils
from .safe_operations import SafeOperations
from .spectral_ops import SpectralOperations
from .stability_metrics import StabilityMetrics
from .variation_metrics import VariationMetrics

__all__ = [
    "FingerprintConstants",
    "SafeOperations",
    "AudioMetrics",
    "MetricUtils",
    "AggregationUtils",
    "SpectralOperations",
    "VariationMetrics",
    "StabilityMetrics",
    "BandNormalizationTable",
]
