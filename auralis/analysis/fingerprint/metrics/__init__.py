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

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .aggregation import AggregationUtils
from .audio_metrics import AudioMetrics
from .constants import FingerprintConstants
from .normalization import MetricUtils
from .safe_operations import SafeOperations

__all__ = [
    "FingerprintConstants",
    "SafeOperations",
    "AudioMetrics",
    "MetricUtils",
    "AggregationUtils",
]
