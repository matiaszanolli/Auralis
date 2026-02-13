"""
Vectorized EQ Processor
~~~~~~~~~~~~~~~~~~~~~~~

Fully vectorized EQ processor using NumPy operations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import cast

import numpy as np
from scipy.fft import fft, ifft

from ....utils.logging import debug


class VectorizedEQProcessor:
    """
    Fully vectorized EQ processor (no parallelism, but very fast for NumPy)

    Often faster than parallel for medium-sized problems due to no thread overhead
    """

    def __init__(self) -> None:
        debug("Vectorized EQ processor initialized")

    def apply_eq_gains_vectorized(
        self,
        audio_chunk: np.ndarray,
        gains: np.ndarray,
        freq_to_band_map: np.ndarray,
        fft_size: int
    ) -> np.ndarray:
        """
        Apply EQ gains using fully vectorized operations

        Args:
            audio_chunk: Input audio data (mono or stereo)
            gains: Gain values in dB for each critical band
            freq_to_band_map: Mapping from FFT bins to critical bands
            fft_size: FFT size for processing

        Returns:
            EQ-processed audio
        """
        # Handle padding
        original_length = len(audio_chunk)
        if len(audio_chunk) < fft_size:
            padded = np.zeros((fft_size, audio_chunk.shape[1] if audio_chunk.ndim == 2 else 1))
            if audio_chunk.ndim == 2:
                padded[:len(audio_chunk), :] = audio_chunk
            else:
                padded[:len(audio_chunk), 0] = audio_chunk
            audio_chunk = padded.squeeze()

        # Process each channel
        if audio_chunk.ndim == 1:
            result = self._apply_eq_mono_vectorized(
                audio_chunk, gains, freq_to_band_map, fft_size
            )
        else:
            processed_channels = []
            for ch in range(audio_chunk.shape[1]):
                processed_ch = self._apply_eq_mono_vectorized(
                    audio_chunk[:, ch], gains, freq_to_band_map, fft_size
                )
                processed_channels.append(processed_ch)
            result = np.column_stack(processed_channels)

        return result[:original_length]

    def _apply_eq_mono_vectorized(
        self,
        audio_mono: np.ndarray,
        gains: np.ndarray,
        freq_to_band_map: np.ndarray,
        fft_size: int
    ) -> np.ndarray:
        """
        Vectorized EQ application to mono audio

        Args:
            audio_mono: Mono audio data
            gains: Gain values in dB for each critical band
            freq_to_band_map: Mapping from FFT bins to critical bands
            fft_size: FFT size

        Returns:
            Processed mono audio
        """
        # Apply window
        window = np.hanning(fft_size)
        windowed_audio = audio_mono[:fft_size] * window

        # Transform to frequency domain
        spectrum = fft(windowed_audio)

        # Create gain curve for all frequencies (vectorized)
        num_bins = fft_size // 2 + 1
        gain_curve = np.ones(num_bins)

        # Map gains to frequency bins (vectorized)
        gains_linear = 10 ** (gains / 20)  # Convert all gains at once
        for i, gain in enumerate(gains_linear):
            mask = freq_to_band_map == i
            gain_curve[mask] = gain

        # Apply gains to positive frequencies (vectorized)
        spectrum[:num_bins] *= gain_curve

        # Apply gains to negative frequencies (vectorized, maintain symmetry)
        spectrum[num_bins:] *= np.conj(gain_curve[1:-1][::-1])

        # Transform back to time domain
        processed_audio = np.real(ifft(spectrum))

        # Apply window compensation
        processed_audio *= window

        return cast(np.ndarray, processed_audio[:len(audio_mono)])
