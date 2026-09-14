"""
Base Processing Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular base processing utilities for audio processing modes.
Extracted from base_processing_mode.py for better maintainability.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .audio_measurement import AudioMeasurement, MeasurementUtilities
from .compression_expansion import CompressionStrategies, ExpansionStrategies
from .db_conversion import DBConversion
from .full_audio_measurement import FullAudioMeasurement
from .normalization_step import NormalizationStep
from .peak_management import PeakNormalizer, SafetyLimiter
from .processing_logger import ProcessingLogger
from .stereo_width_processor import StereoWidthProcessor

__all__ = [
    # Audio Measurement
    'AudioMeasurement',
    'MeasurementUtilities',
    # Compression and Expansion
    'CompressionStrategies',
    'ExpansionStrategies',
    # DB Conversion
    'DBConversion',
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
