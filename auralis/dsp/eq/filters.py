# -*- coding: utf-8 -*-

"""
EQ Filter Implementation
~~~~~~~~~~~~~~~~~~~~~~~

FFT-based EQ filter application with critical band processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from scipy.fft import fft, ifft


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

    Args:
        audio_mono: Mono audio data
        gains: Gain values in dB for each critical band
        freq_to_band_map: Mapping from FFT bins to critical bands
        fft_size: FFT size for processing

    Returns:
        Processed mono audio
    """
    # Apply Hanning window to reduce spectral leakage
    window = np.hanning(fft_size)
    windowed_audio = audio_mono[:fft_size] * window

    # Transform to frequency domain
    spectrum = fft(windowed_audio)

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

    # Apply window compensation
    processed_audio *= window

    return processed_audio[:len(audio_mono)]


def create_filter_bank(critical_bands: list,
                      sample_rate: int,
                      fft_size: int) -> np.ndarray:
    """
    Create filter bank for critical bands

    Args:
        critical_bands: List of CriticalBand objects
        sample_rate: Sample rate in Hz
        fft_size: FFT size

    Returns:
        Filter bank matrix (num_bands x fft_bins)
    """
    num_bands = len(critical_bands)
    num_bins = fft_size // 2 + 1
    filter_bank = np.zeros((num_bands, num_bins))

    freqs = np.linspace(0, sample_rate // 2, num_bins)

    for i, band in enumerate(critical_bands):
        # Create a bandpass filter for this critical band
        # Using triangular filter shape
        for j, freq in enumerate(freqs):
            if band.low_freq <= freq <= band.high_freq:
                if freq <= band.center_freq:
                    # Rising slope
                    filter_bank[i, j] = (freq - band.low_freq) / (band.center_freq - band.low_freq)
                else:
                    # Falling slope
                    filter_bank[i, j] = (band.high_freq - freq) / (band.high_freq - band.center_freq)

    return filter_bank
