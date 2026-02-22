"""
Base Processing Mode
~~~~~~~~~~~~~~~~~~~~

Backward compatibility wrapper for base processing utilities.

DEPRECATED: This file is maintained for backward compatibility only.
New code should import from auralis.core.processing.base module instead:
    from auralis.core.processing.base import (
        AudioMeasurement,
        MeasurementUtilities,
        CompressionStrategies,
        ExpansionStrategies,
        DBConversion,
        StereoWidthProcessor,
        ProcessingLogger,
        SafetyLimiter,
        PeakNormalizer,
        NormalizationStep,
        FullAudioMeasurement
    )

Migration Timeline:
- v1.1.0: Marked deprecated (current)
- v1.2.0: Add deprecation warnings
- v2.0.0+: Consider removal or minimal facade only

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import warnings

warnings.warn(
    "auralis.core.processing.base_processing_mode is deprecated. "
    "Import from auralis.core.processing.base instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export all classes from the modular base package
from .base import (
    AudioMeasurement,
    CompressionStrategies,
    DBConversion,
    ExpansionStrategies,
    FullAudioMeasurement,
    MeasurementUtilities,
    NormalizationStep,
    PeakNormalizer,
    ProcessingLogger,
    SafetyLimiter,
    StereoWidthProcessor,
)

__all__ = [
    # Audio Measurement
    'AudioMeasurement',
    'MeasurementUtilities',
    'FullAudioMeasurement',
    # Compression and Expansion
    'CompressionStrategies',
    'ExpansionStrategies',
    # DB Conversion
    'DBConversion',
    # Normalization
    'NormalizationStep',
    # Peak Management
    'PeakNormalizer',
    'SafetyLimiter',
    # Processing Logger
    'ProcessingLogger',
    # Stereo Width
    'StereoWidthProcessor',
]
