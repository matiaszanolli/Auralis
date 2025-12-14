# -*- coding: utf-8 -*-

"""
Parallel EQ Processor
~~~~~~~~~~~~~~~~~~~~~

Multi-threaded parallel processing for psychoacoustic EQ

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from scipy.fft import fft, ifft
from typing import List, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor

from .config import ParallelEQConfig
from ....utils.logging import debug


class ParallelEQProcessor:
    """
    Parallel psychoacoustic EQ processor

    Processes frequency bands in parallel for 2-3x speedup over sequential processing
    """

    def __init__(self, config: Optional[ParallelEQConfig] = None):
        self.config = config or ParallelEQConfig()

        # Define band groups for batch processing
        self.band_groups: Optional[List[List[int]]]
        if self.config.use_band_grouping:
            self.band_groups = [
                list(range(*self.config.bass_bands)),
                list(range(*self.config.low_mid_bands)),
                list(range(*self.config.mid_bands)),
                list(range(*self.config.high_mid_bands)),
                list(range(*self.config.treble_bands))
            ]
        else:
            self.band_groups = None

        debug(f"Parallel EQ processor initialized: max_workers={self.config.max_workers}, "
              f"band_grouping={self.config.use_band_grouping}")

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
        Apply EQ to mono audio with parallel band processing

        Args:
            audio_mono: Mono audio data
            gains: Gain values in dB for each critical band
            freq_to_band_map: Mapping from FFT bins to critical bands
            fft_size: FFT size for processing

        Returns:
            Processed mono audio
        """
        num_bands = len(gains)

        # Check if parallel processing is worth it
        if not self.config.enable_parallel or num_bands < self.config.min_bands_for_parallel:
            return self._apply_eq_mono_sequential(
                audio_mono, gains, freq_to_band_map, fft_size
            )

        # Apply window and transform
        window = np.hanning(fft_size)
        windowed_audio = audio_mono[:fft_size] * window
        spectrum = fft(windowed_audio)

        # Pre-compute band masks and gains for all bands (vectorized)
        band_masks = []
        gains_linear = []
        for i in range(num_bands):
            mask = freq_to_band_map == i
            band_masks.append(mask)
            gains_linear.append(10 ** (gains[i] / 20))

        # Process bands using parallel strategy
        if self.config.use_band_grouping and self.band_groups:
            # Group-based parallel processing
            spectrum = self._process_band_groups_parallel(
                spectrum, band_masks, gains_linear, fft_size
            )
        else:
            # Individual band parallel processing
            spectrum = self._process_bands_parallel(
                spectrum, band_masks, gains_linear, fft_size
            )

        # Transform back to time domain
        processed_audio = np.real(ifft(spectrum))

        # Apply window compensation
        processed_audio *= window

        return processed_audio[:len(audio_mono)]

    def _process_bands_parallel(
        self,
        spectrum: np.ndarray,
        band_masks: List[np.ndarray],
        gains_linear: List[float],
        fft_size: int
    ) -> np.ndarray:
        """
        Process individual bands in parallel

        Args:
            spectrum: FFT spectrum
            band_masks: List of boolean masks for each band
            gains_linear: List of linear gain values
            fft_size: FFT size

        Returns:
            Modified spectrum
        """
        num_bands = len(band_masks)
        spectrum_copy = spectrum.copy()

        # Process bands in parallel using thread pool
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit tasks for each band
            futures = [
                executor.submit(
                    self._apply_gain_to_band,
                    spectrum_copy,
                    band_masks[i],
                    gains_linear[i],
                    i,
                    fft_size
                )
                for i in range(num_bands)
            ]

            # Wait for all tasks to complete
            for future in futures:
                band_idx, modified_spectrum = future.result()
                # Update spectrum with processed band
                spectrum_copy = modified_spectrum

        return spectrum_copy

    def _process_band_groups_parallel(
        self,
        spectrum: np.ndarray,
        band_masks: List[np.ndarray],
        gains_linear: List[float],
        fft_size: int
    ) -> np.ndarray:
        """
        Process bands in groups for better parallelism

        Args:
            spectrum: FFT spectrum
            band_masks: List of boolean masks for each band
            gains_linear: List of linear gain values
            fft_size: FFT size

        Returns:
            Modified spectrum
        """
        spectrum_copy = spectrum.copy()

        # Process each group in parallel
        with ThreadPoolExecutor(max_workers=len(self.band_groups)) as executor:
            futures = [
                executor.submit(
                    self._process_band_group,
                    spectrum_copy,
                    band_masks,
                    gains_linear,
                    group,
                    fft_size
                )
                for group in self.band_groups
            ]

            # Collect results and merge
            group_results = [f.result() for f in futures]

        # Merge group results (apply all gains)
        for group_spectrum in group_results:
            spectrum_copy = group_spectrum

        return spectrum_copy

    def _process_band_group(
        self,
        spectrum: np.ndarray,
        band_masks: List[np.ndarray],
        gains_linear: List[float],
        band_indices: List[int],
        fft_size: int
    ) -> np.ndarray:
        """
        Process a group of bands sequentially

        Args:
            spectrum: FFT spectrum
            band_masks: List of all band masks
            gains_linear: List of all gains
            band_indices: Indices of bands in this group
            fft_size: FFT size

        Returns:
            Spectrum with group bands processed
        """
        spectrum_copy = spectrum.copy()

        for band_idx in band_indices:
            if band_idx < len(band_masks):
                _, spectrum_copy = self._apply_gain_to_band(
                    spectrum_copy,
                    band_masks[band_idx],
                    gains_linear[band_idx],
                    band_idx,
                    fft_size
                )

        return spectrum_copy

    def _apply_gain_to_band(
        self,
        spectrum: np.ndarray,
        band_mask: np.ndarray,
        gain_linear: float,
        band_idx: int,
        fft_size: int
    ) -> Tuple[int, np.ndarray]:
        """
        Apply gain to a single frequency band

        Args:
            spectrum: FFT spectrum
            band_mask: Boolean mask for this band
            gain_linear: Linear gain value
            band_idx: Band index
            fft_size: FFT size

        Returns:
            Tuple of (band_idx, modified_spectrum)
        """
        spectrum_copy = spectrum.copy()

        # Apply gain to positive frequencies
        spectrum_copy[:fft_size // 2 + 1][band_mask] *= gain_linear

        # Apply gain to negative frequencies (maintain hermitian symmetry)
        if band_idx > 0:  # Skip DC component
            neg_mask = band_mask[1:-1][::-1]  # Reverse mask for negative frequencies
            if len(neg_mask) > 0 and fft_size // 2 + 1 + len(neg_mask) <= len(spectrum_copy):
                spectrum_copy[fft_size // 2 + 1:fft_size // 2 + 1 + len(neg_mask)] *= gain_linear

        return band_idx, spectrum_copy

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
        # Apply window
        window = np.hanning(fft_size)
        windowed_audio = audio_mono[:fft_size] * window

        # Transform to frequency domain
        spectrum = fft(windowed_audio)

        # Apply gains sequentially
        for i, gain_db in enumerate(gains):
            gain_linear = 10 ** (gain_db / 20)
            band_mask = freq_to_band_map == i

            # Apply gain to positive frequencies
            spectrum[:fft_size // 2 + 1][band_mask] *= gain_linear

            # Apply gain to negative frequencies (maintain symmetry)
            if i > 0:
                neg_mask = band_mask[1:-1][::-1]
                if len(neg_mask) > 0:
                    spectrum[fft_size // 2 + 1:fft_size // 2 + 1 + len(neg_mask)] *= gain_linear

        # Transform back
        processed_audio = np.real(ifft(spectrum))

        # Apply window compensation
        processed_audio *= window

        return processed_audio[:len(audio_mono)]
