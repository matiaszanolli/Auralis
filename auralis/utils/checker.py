# -*- coding: utf-8 -*-

"""
Auralis Audio Checker
~~~~~~~~~~~~~~~~~~~~~

Audio validation and checking utilities

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""

import numpy as np
from .logging import debug, ModuleError, Code


def check(audio: np.ndarray, sample_rate: int, config, file_type: str = "audio"):
    """
    Check and validate audio data

    Performs comprehensive validation including:
    - Empty audio check
    - Sample rate validation
    - Audio length and amplitude checks
    - Clipping detection
    - Data type conversion to float32/float64
    - Automatic resampling to config.internal_sample_rate

    Args:
        audio: Audio data to check
        sample_rate: Sample rate of the audio
        config: Processing configuration
        file_type: Type of file being checked

    Returns:
        tuple: (validated_audio, resampled_sample_rate)

    Raises:
        ModuleError: If audio validation fails (empty, invalid sample rate, etc.)
    """
    debug(f"Checking {file_type} audio: {audio.shape}, {sample_rate} Hz")

    # Import validation functions
    from ..io.processing import validate_audio, resample_audio

    # Validate audio (checks for empty, NaN, Inf, clipping, etc.)
    audio, sample_rate = validate_audio(audio, sample_rate, file_type)

    # Resample to internal sample rate if needed
    if sample_rate != config.internal_sample_rate:
        debug(f"Resampling from {sample_rate} Hz to {config.internal_sample_rate} Hz")
        audio = resample_audio(audio, sample_rate, config.internal_sample_rate)
        sample_rate = config.internal_sample_rate
        debug(f"Resampling complete: {audio.shape}, {sample_rate} Hz")

    return audio, sample_rate


def check_equality(target: np.ndarray, reference: np.ndarray):
    """
    Check if target and reference are too similar

    Args:
        target: Target audio data
        reference: Reference audio data

    Raises:
        ModuleError: If files are too similar
    """
    # Simple similarity check
    if np.array_equal(target, reference):
        raise ModuleError(Code.ERROR_VALIDATION)

    debug("Equality check passed")


def is_audio_file(filepath: str) -> bool:
    """
    Check if a file is an audio file based on its extension.

    Args:
        filepath: Path to the file

    Returns:
        bool: True if the file appears to be an audio file
    """
    import os

    audio_extensions = {
        '.wav', '.mp3', '.flac', '.aiff', '.aif', '.m4a', '.ogg',
        '.wma', '.opus', '.ac3', '.dts', '.mp2', '.ape', '.wv'
    }

    _, ext = os.path.splitext(filepath.lower())
    return ext in audio_extensions


def check_file_permissions(filepath: str) -> bool:
    """
    Check if a file has proper read permissions.

    Args:
        filepath: Path to the file

    Returns:
        bool: True if file is readable
    """
    import os

    try:
        return os.path.isfile(filepath) and os.access(filepath, os.R_OK)
    except (OSError, IOError):
        return False