# -*- coding: utf-8 -*-

"""
SIMD Accelerator
~~~~~~~~~~~~~~~~

SIMD-optimized operations for audio processing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Optional


class SIMDAccelerator:
    """SIMD acceleration for common audio operations"""

    @staticmethod
    def fast_fft(audio: np.ndarray, fft_size: Optional[int] = None) -> np.ndarray:
        """Optimized FFT computation"""
        if fft_size is None:
            fft_size = len(audio)

        # Use power-of-2 sizes for optimal performance
        if fft_size & (fft_size - 1) != 0:  # Not power of 2
            optimal_size = 1 << (fft_size - 1).bit_length()
            if optimal_size <= fft_size * 1.5:  # Within reasonable range
                fft_size = optimal_size

        # Zero-pad if necessary
        if len(audio) < fft_size:
            padded = np.zeros(fft_size, dtype=audio.dtype)
            padded[:len(audio)] = audio
            audio = padded
        elif len(audio) > fft_size:
            audio = audio[:fft_size]

        # Use optimized FFT
        return np.fft.fft(audio)

    @staticmethod
    def fast_convolution(signal: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        """Optimized convolution using FFT"""
        if len(kernel) < 64:  # Use direct convolution for small kernels
            return np.convolve(signal, kernel, mode='same')

        # Use FFT convolution for larger kernels
        conv_size = len(signal) + len(kernel) - 1
        fft_size = 1 << (conv_size - 1).bit_length()  # Next power of 2

        signal_fft = np.fft.fft(signal, fft_size)
        kernel_fft = np.fft.fft(kernel, fft_size)

        result = np.fft.ifft(signal_fft * kernel_fft).real

        # Extract the 'same' portion
        start = len(kernel) // 2
        return result[start:start + len(signal)]

    @staticmethod
    def vectorized_gain_apply(audio: np.ndarray, gains: np.ndarray) -> np.ndarray:
        """Apply gains using vectorized operations"""
        if audio.ndim == 1:
            # Mono audio
            return np.asarray(audio * gains, dtype=np.float32)
        else:
            # Multi-channel audio
            if len(gains) == audio.shape[1]:
                # Per-channel gains
                return np.asarray(audio * gains[np.newaxis, :], dtype=np.float32)
            else:
                # Single gain for all channels
                return np.asarray(audio * gains, dtype=np.float32)

    @staticmethod
    def fast_rms_calculation(audio: np.ndarray, window_size: int = 1024) -> np.ndarray:
        """Fast RMS calculation using sliding window"""
        if len(audio) <= window_size:
            return np.array([np.sqrt(np.mean(audio ** 2))])

        # Use cumulative sum for efficiency
        audio_squared = audio ** 2
        cumsum = np.cumsum(np.concatenate(([0], audio_squared)))

        # Calculate RMS for each window
        num_windows = len(audio) - window_size + 1
        rms_values = np.zeros(num_windows)

        for i in range(num_windows):
            window_sum = cumsum[i + window_size] - cumsum[i]
            rms_values[i] = np.sqrt(window_sum / window_size)

        return rms_values
