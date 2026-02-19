"""
Parallel EQ Processor
~~~~~~~~~~~~~~~~~~~~~

Multi-threaded parallel processing for psychoacoustic EQ

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import cast

import numpy as np
from scipy.fft import fft, ifft

from ....utils.logging import debug
from .config import ParallelEQConfig


class ParallelEQProcessor:
    """
    Parallel psychoacoustic EQ processor

    Processes frequency bands in parallel for 2-3x speedup over sequential processing
    """

    def __init__(self, config: ParallelEQConfig | None = None):
        self.config = config or ParallelEQConfig()

        debug(f"Parallel EQ processor initialized: max_workers={self.config.max_workers}")

    def apply_eq_gains_parallel(
        self,
        audio_chunk: np.ndarray,
        gains: np.ndarray,
        freq_to_band_map: np.ndarray,
        fft_size: int
    ) -> np.ndarray:
        """
        Apply EQ gains with parallel band processing

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
            result = self._apply_eq_mono_parallel(
                audio_chunk, gains, freq_to_band_map, fft_size
            )
        else:
            # Process channels in parallel (for stereo)
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        self._apply_eq_mono_parallel,
                        audio_chunk[:, ch],
                        gains,
                        freq_to_band_map,
                        fft_size
                    )
                    for ch in range(audio_chunk.shape[1])
                ]
                processed_channels = [f.result() for f in futures]
            result = np.column_stack(processed_channels)

        return result[:original_length]

    def _apply_eq_mono_parallel(
        self,
        audio_mono: np.ndarray,
        gains: np.ndarray,
        freq_to_band_map: np.ndarray,
        fft_size: int
    ) -> np.ndarray:
        """
        Apply EQ to mono audio using a vectorized gain curve.

        The previous parallel-per-band implementation had a race condition: every
        thread received a copy of the original spectrum, applied one band's gain,
        and returned its copy; the merge loop then discarded all but the last
        thread's result (#2448).

        Fix: build a complete gain_curve for all bins (O(bands) — trivially fast),
        then apply in a single vectorized pass.  The genuine parallelism for stereo
        (two independent channels) is preserved in apply_eq_gains_parallel().

        Args:
            audio_mono: Mono audio data
            gains: Gain values in dB for each critical band
            freq_to_band_map: Mapping from FFT bins to critical bands
            fft_size: FFT size for processing

        Returns:
            Processed mono audio
        """
        num_bands = len(gains)

        if not self.config.enable_parallel or num_bands < self.config.min_bands_for_parallel:
            return self._apply_eq_mono_sequential(
                audio_mono, gains, freq_to_band_map, fft_size
            )

        # No windowing for direct frequency-domain EQ — see VectorizedEQProcessor
        spectrum = fft(audio_mono[:fft_size])

        # Build complete gain curve for all frequency bins — no per-band copies,
        # no merge race (#2448)
        num_bins = fft_size // 2 + 1
        gains_linear = 10 ** (gains / 20)
        gain_curve = np.ones(num_bins)
        for i, gain in enumerate(gains_linear):
            mask = freq_to_band_map == i
            gain_curve[mask] = gain

        # Apply all gains in a single pass (vectorized)
        spectrum[:num_bins] *= gain_curve
        spectrum[num_bins:] *= np.conj(gain_curve[1:-1][::-1])

        processed_audio = np.real(ifft(spectrum))
        return cast(np.ndarray, processed_audio[:len(audio_mono)])

    def _apply_eq_mono_sequential(
        self,
        audio_mono: np.ndarray,
        gains: np.ndarray,
        freq_to_band_map: np.ndarray,
        fft_size: int
    ) -> np.ndarray:
        """
        Sequential fallback implementation

        Args:
            audio_mono: Mono audio data
            gains: Gain values in dB for each critical band
            freq_to_band_map: Mapping from FFT bins to critical bands
            fft_size: FFT size

        Returns:
            Processed mono audio
        """
        # No windowing for direct frequency-domain EQ — see VectorizedEQProcessor
        spectrum = fft(audio_mono[:fft_size])

        # Apply gains sequentially
        for i, gain_db in enumerate(gains):
            gain_linear = 10 ** (gain_db / 20)
            band_mask = freq_to_band_map == i

            # Apply gain to positive frequencies (including DC and Nyquist)
            spectrum[:fft_size // 2 + 1][band_mask] *= gain_linear

            # Apply gain to negative frequencies (maintain hermitian symmetry).
            # band_mask[1:-1] excludes DC (bin 0) and Nyquist (bin fft_size//2),
            # which have no negative-frequency counterparts.
            # The reversed mask selects exactly those negative-frequency bins
            # that mirror the positive-frequency bins belonging to this band.
            # The old `if i > 0` guard was wrong: it prevented band 0's non-DC
            # bins from being reflected, and the slice never used neg_mask as a
            # boolean index, causing all bands' gains to accumulate on every
            # negative-frequency bin (#2448).
            neg_mask = band_mask[1:-1][::-1]  # shape (fft_size//2 - 1,)
            spectrum[fft_size // 2 + 1:][neg_mask] *= gain_linear

        # Transform back
        processed_audio = np.real(ifft(spectrum))

        return cast(np.ndarray, processed_audio[:len(audio_mono)])
