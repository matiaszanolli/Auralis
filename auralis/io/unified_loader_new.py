# -*- coding: utf-8 -*-

"""
Unified Audio Loader
~~~~~~~~~~~~~~~~~~~~

Enhanced audio file loading supporting multiple formats and processing modes

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Unified audio loading system combining Matchering and Auralis capabilities
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Union, List

from .loaders import load_with_soundfile, load_with_ffmpeg
from .processing import validate_audio, resample_audio
from ..utils.logging import debug, info, ModuleError, Code


# Supported audio formats
SUPPORTED_FORMATS = {
    '.wav': 'WAV',
    '.flac': 'FLAC',
    '.mp3': 'MP3',
    '.m4a': 'M4A',
    '.aac': 'AAC',
    '.ogg': 'OGG',
    '.wma': 'WMA'
}

# Formats that require FFmpeg conversion
FFMPEG_FORMATS = {'.mp3', '.m4a', '.aac', '.ogg', '.wma'}


def load_audio(
    file_path: Union[str, Path],
    file_type: str = "audio",
    temp_folder: Optional[str] = None,
    target_sample_rate: Optional[int] = None,
    force_stereo: bool = False,
    normalize_on_load: bool = False
) -> Tuple[np.ndarray, int]:
    """
    Load an audio file with format detection and conversion

    Args:
        file_path: Path to the audio file
        file_type: Type of file being loaded ("target", "reference", or "audio")
        temp_folder: Temporary folder for FFmpeg conversions
        target_sample_rate: Resample to this sample rate (optional)
        force_stereo: Convert mono to stereo if True
        normalize_on_load: Normalize audio on loading

    Returns:
        tuple: (audio_data, sample_rate)

    Raises:
        ModuleError: If file cannot be loaded or is invalid
    """
    file_path = Path(file_path)

    debug(f"Loading {file_type} audio file: {file_path}")

    # Validate file exists
    if not file_path.exists():
        raise ModuleError(f"{Code.ERROR_FILE_NOT_FOUND}: {file_path}")

    # Check file size
    file_size = file_path.stat().st_size
    if file_size == 0:
        raise ModuleError(f"{Code.ERROR_EMPTY_FILE}: {file_path}")

    debug(f"File size: {file_size / (1024*1024):.2f} MB")

    # Get file extension
    file_ext = file_path.suffix.lower()

    if file_ext not in SUPPORTED_FORMATS:
        raise ModuleError(f"{Code.ERROR_UNSUPPORTED_FORMAT}: {file_ext}")

    info(f"Detected format: {SUPPORTED_FORMATS[file_ext]}")

    # Load audio based on format
    if file_ext in FFMPEG_FORMATS:
        audio_data, sample_rate = load_with_ffmpeg(file_path, temp_folder)
    else:
        audio_data, sample_rate = load_with_soundfile(file_path)

    # Validate audio data
    audio_data, sample_rate = validate_audio(audio_data, sample_rate, file_type)

    # Apply post-processing options
    if target_sample_rate and target_sample_rate != sample_rate:
        audio_data = resample_audio(audio_data, sample_rate, target_sample_rate)
        sample_rate = target_sample_rate

    if force_stereo and audio_data.ndim == 1:
        audio_data = np.column_stack([audio_data, audio_data])
        debug("Converted mono to stereo")

    if normalize_on_load:
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val
            debug(f"Normalized audio (peak: {max_val:.6f})")

    info(f"Loaded audio: {len(audio_data)} samples at {sample_rate} Hz")

    return audio_data, sample_rate


# Keep all remaining functions from original file (get_audio_info, batch_load_info, etc.)
# Import them here for backwards compatibility
from .unified_loader_legacy import (
    get_audio_info,
    batch_load_info,
    is_audio_file,
    get_supported_formats
)


def load_target(file_path: Union[str, Path], **kwargs) -> Tuple[np.ndarray, int]:
    """Convenience function to load target audio"""
    return load_audio(file_path, file_type="target", **kwargs)


def load_reference(file_path: Union[str, Path], **kwargs) -> Tuple[np.ndarray, int]:
    """Convenience function to load reference audio"""
    return load_audio(file_path, file_type="reference", **kwargs)
