"""
Audio Processing
~~~~~~~~~~~~~~~~

Audio validation and processing utilities

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from ..utils.logging import Code, ModuleError, debug, warning


def validate_audio(audio_data: np.ndarray, sample_rate: int, file_type: str) -> tuple[np.ndarray, int]:
    """Validate loaded audio data"""

    # Check if audio is empty
    if audio_data.size == 0:
        raise ModuleError(f"{Code.ERROR_EMPTY_AUDIO}: No audio data found")

    # Check sample rate
    if sample_rate <= 0:
        raise ModuleError(f"{Code.ERROR_INVALID_SAMPLE_RATE}: {sample_rate}")

    if sample_rate < 8000:
        warning(f"Very low sample rate: {sample_rate} Hz")
    elif sample_rate > 192000:
        warning(f"Very high sample rate: {sample_rate} Hz")

    # Check audio length
    duration_seconds = len(audio_data) / sample_rate
    if duration_seconds < 1.0:
        warning(f"Very short audio: {duration_seconds:.2f} seconds")
    elif duration_seconds > 30 * 60:  # 30 minutes
        warning(f"Very long audio: {duration_seconds/60:.1f} minutes")

    # Check for silence
    max_amplitude = np.max(np.abs(audio_data))
    if max_amplitude < 1e-6:
        warning(f"Audio appears to be silent (peak: {max_amplitude:.2e})")

    # Check for clipping
    if max_amplitude >= 0.99:
        clipped_samples = np.sum(np.abs(audio_data) >= 0.99)
        clipping_percentage = (clipped_samples / audio_data.size) * 100
        if clipping_percentage > 0.1:
            warning(f"Audio may be clipped ({clipping_percentage:.2f}% of samples)")

    # Ensure proper data type
    if audio_data.dtype != np.float32 and audio_data.dtype != np.float64:
        audio_data = audio_data.astype(np.float32)
        debug(f"Converted audio to float32")

    return audio_data, sample_rate


def resample_audio(audio_data: np.ndarray, original_rate: int, target_rate: int) -> np.ndarray:
    """Resample audio to target sample rate"""
    if original_rate == target_rate:
        return audio_data

    try:
        import resampy
        debug(f"Resampling from {original_rate} Hz to {target_rate} Hz using resampy")

        input_dtype = audio_data.dtype  # Preserve caller's dtype (fixes #2227)
        if audio_data.ndim == 1:
            return np.asarray(resampy.resample(audio_data, original_rate, target_rate), dtype=input_dtype)
        else:
            # Resample each channel separately
            resampled_channels = []
            for channel in range(audio_data.shape[1]):
                resampled_channel = resampy.resample(
                    audio_data[:, channel], original_rate, target_rate
                )
                resampled_channels.append(resampled_channel)
            return np.column_stack(resampled_channels).astype(input_dtype, copy=False)

    except ImportError:
        # Fallback to simple linear interpolation (less quality but no dependency)
        warning("resampy not available, using simple interpolation")
        return simple_resample(audio_data, original_rate, target_rate)


def simple_resample(audio_data: np.ndarray, original_rate: int, target_rate: int) -> np.ndarray:
    """Simple resampling using linear interpolation.

    Output dtype matches the input dtype (fixes #2227).
    """
    input_dtype = audio_data.dtype
    ratio = target_rate / original_rate
    new_length = int(len(audio_data) * ratio)

    if audio_data.ndim == 1:
        # Mono audio
        old_indices = np.linspace(0, len(audio_data) - 1, new_length)
        return np.asarray(np.interp(old_indices, np.arange(len(audio_data)), audio_data), dtype=input_dtype)
    else:
        # Multi-channel audio
        resampled_channels = []
        for channel in range(audio_data.shape[1]):
            old_indices = np.linspace(0, len(audio_data) - 1, new_length)
            resampled_channel = np.interp(
                old_indices, np.arange(len(audio_data)), audio_data[:, channel]
            )
            resampled_channels.append(resampled_channel)
        return np.column_stack(resampled_channels).astype(input_dtype, copy=False)
