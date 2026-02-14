"""
EQ Filter Implementation
~~~~~~~~~~~~~~~~~~~~~~~

FFT-based EQ filter application with critical band processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

import numpy as np
from scipy.fft import fft, ifft

from ..utils import create_triangular_filterbank


def apply_eq_gains(audio_chunk: np.ndarray,
                  gains: np.ndarray,
                  freq_to_band_map: np.ndarray,
                  fft_size: int) -> np.ndarray:
    """
    Apply EQ gains to audio chunk

    Args:
        audio_chunk: Input audio data (mono or stereo)
        gains: Gain values in dB for each critical band
        freq_to_band_map: Mapping from FFT bins to critical bands
        fft_size: FFT size for processing

    Returns:
        EQ-processed audio
    """
    if len(audio_chunk) < fft_size:
        # Pad with zeros for processing
        padded = np.zeros((fft_size, audio_chunk.shape[1] if audio_chunk.ndim == 2 else 1))
        if audio_chunk.ndim == 2:
            padded[:len(audio_chunk), :] = audio_chunk
        else:
            padded[:len(audio_chunk), 0] = audio_chunk
        audio_chunk = padded.squeeze()

    # Process each channel
    if audio_chunk.ndim == 1:
        return apply_eq_mono(audio_chunk, gains, freq_to_band_map, fft_size)
    else:
        processed_channels = []
        for channel in range(audio_chunk.shape[1]):
            processed_channel = apply_eq_mono(
                audio_chunk[:, channel],
                gains,
                freq_to_band_map,
                fft_size
            )
            processed_channels.append(processed_channel)
        return np.column_stack(processed_channels)


def apply_eq_mono(audio_mono: np.ndarray,
                 gains: np.ndarray,
                 freq_to_band_map: np.ndarray,
                 fft_size: int) -> np.ndarray:
    """
    Apply EQ to mono audio using FFT processing

    Note: No windowing is applied for EQ processing. Windowing is used for spectral
    analysis to reduce leakage, but for filtering/EQ it creates amplitude modulation
    artifacts. For chunked processing, overlap-add with windowing should be handled
    at the chunk level, not here.

    Args:
        audio_mono: Mono audio data
        gains: Gain values in dB for each critical band
        freq_to_band_map: Mapping from FFT bins to critical bands
        fft_size: FFT size for processing

    Returns:
        Processed mono audio
    """
    # Transform to frequency domain (no windowing for EQ)
    spectrum = fft(audio_mono[:fft_size])

    # Apply gains to each critical band
    for i, gain_db in enumerate(gains):
        gain_linear = 10 ** (gain_db / 20)
        band_mask = freq_to_band_map == i

        # Apply gain to positive frequencies
        spectrum[:fft_size // 2 + 1][band_mask] *= gain_linear

        # Apply gain to negative frequencies (maintain symmetry)
        if i > 0:  # Skip DC component
            spectrum[fft_size // 2 + 1:][band_mask[1:-1][::-1]] *= gain_linear

    # Transform back to time domain
    processed_audio = np.real(ifft(spectrum))

    return np.asarray(processed_audio[:len(audio_mono)], dtype=np.float32)


def create_filter_bank(critical_bands: list[Any],
                      sample_rate: int,
                      fft_size: int) -> np.ndarray:
    """
    Create filter bank for critical bands

    Uses vectorized triangular filterbank creation for improved performance.

    Args:
        critical_bands: List of CriticalBand objects
        sample_rate: Sample rate in Hz
        fft_size: FFT size

    Returns:
        Filter bank matrix (num_bands x fft_bins)
    """
    return create_triangular_filterbank(critical_bands, sample_rate, fft_size)
