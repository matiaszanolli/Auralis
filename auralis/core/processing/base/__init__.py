"""
Base Processing Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular base processing utilities for audio processing modes.
Extracted from base_processing_mode.py for better maintainability.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .compression_expansion import CompressionStrategies, ExpansionStrategies
from .full_audio_measurement import FullAudioMeasurement
from .normalization_step import NormalizationStep
from .peak_management import PeakNormalizer, SafetyLimiter
from .processing_logger import ProcessingLogger
from .stereo_width_processor import StereoWidthProcessor

__all__ = [
    # Compression and Expansion
    'CompressionStrategies',
    'ExpansionStrategies',
    # Full Audio Measurement
    'FullAudioMeasurement',
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
