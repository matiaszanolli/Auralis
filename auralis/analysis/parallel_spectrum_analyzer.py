# -*- coding: utf-8 -*-

"""
Parallel Spectrum Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~

High-performance spectrum analysis with parallel FFT processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..optimization.parallel_processor import ParallelFFTProcessor, ParallelConfig
from ..utils.logging import debug
from .base_spectrum_analyzer import BaseSpectrumAnalyzer, SpectrumSettings
from .spectrum_operations import SpectrumOperations
from .fingerprint.common_metrics import SafeOperations, AggregationUtils


@dataclass
class ParallelSpectrumSettings(SpectrumSettings):
    """Configuration for parallel spectrum analysis

    Extends SpectrumSettings with parallel processing options
    """
    # Parallel processing
    enable_parallel: bool = True
    max_workers: int = 8
    min_chunks_for_parallel: int = 4  # Minimum chunks to use parallel processing


class ParallelSpectrumAnalyzer(BaseSpectrumAnalyzer):
    """
    Advanced spectrum analyzer with parallel FFT processing

    Provides 3-4x speedup over sequential processing for long audio files.
    Extends BaseSpectrumAnalyzer with parallel processing capabilities.
    """

    def __init__(self, settings: Optional[ParallelSpectrumSettings] = None) -> None:
        # Ensure we have ParallelSpectrumSettings
        if settings is None:
            settings = ParallelSpectrumSettings()
        elif not isinstance(settings, ParallelSpectrumSettings):
            # Convert SpectrumSettings to ParallelSpectrumSettings if needed
            settings_obj: ParallelSpectrumSettings = ParallelSpectrumSettings(  # type: ignore[unreachable]
                fft_size=settings.fft_size,
                window_type=settings.window_type,
                overlap=settings.overlap,
                sample_rate=settings.sample_rate,
                frequency_bands=settings.frequency_bands,
                frequency_weighting=settings.frequency_weighting,
                smoothing_factor=settings.smoothing_factor,
                min_frequency=settings.min_frequency,
                max_frequency=settings.max_frequency
            )
            settings = settings_obj

        # Call parent constructor
        super().__init__(settings)

        # Initialize parallel FFT processor
        parallel_config: ParallelConfig = ParallelConfig(
            enable_parallel=settings.enable_parallel,
            max_workers=settings.max_workers,
            use_multiprocessing=False  # Threading works well for FFT
        )
        self.fft_processor: Any = ParallelFFTProcessor(parallel_config)

        # Pre-compute band masks for vectorized processing
        self._init_band_masks()

        debug(f"Parallel spectrum analyzer initialized: {self.settings.frequency_bands} bands, "
              f"{settings.max_workers} workers")

    def _init_band_masks(self) -> None:
        """Pre-compute band masks for vectorized band mapping"""
        freqs: np.ndarray = np.fft.rfftfreq(self.settings.fft_size, 1/self.settings.sample_rate)

        # Create masks for each band (vectorized)
        self.band_masks: List[np.ndarray] = []
        for i in range(len(self.frequency_bins) - 1):
            start_freq: float = self.frequency_bins[i]
            end_freq: float = self.frequency_bins[i + 1]
            mask: np.ndarray = (freqs >= start_freq) & (freqs < end_freq)
            self.band_masks.append(mask)

        # Last band
        mask = freqs >= self.frequency_bins[-1]
        self.band_masks.append(mask)

        debug(f"Pre-computed {len(self.band_masks)} band masks for vectorized processing")

    def analyze_chunk(self, audio_chunk: np.ndarray, channel: int = 0) -> Dict[str, Any]:
        """
        Analyze a single chunk of audio (for real-time processing)

        Args:
            audio_chunk: Audio data chunk
            channel: Channel to analyze (0=left, 1=right, -1=sum)

        Returns:
            Dictionary with analysis results
        """
        return self._create_chunk_result(audio_chunk, channel, self.settings.sample_rate)

    def analyze_file(self, audio_data: np.ndarray, sample_rate: Optional[int] = None) -> Dict[str, Any]:
        """
        Analyze an entire audio file with parallel FFT processing

        Args:
            audio_data: Complete audio data
            sample_rate: Sample rate (if different from settings)

        Returns:
            Dictionary with comprehensive analysis including:
                - spectrum: Average spectrum across all windows
                - frequency_bins: Frequency values for each band
                - spectral_centroid: Weighted average frequency
                - spectral_rolloff: 85% energy frequency
                - total_energy: Total spectral energy
                - num_chunks_analyzed: Number of FFT windows processed
        """
        if sample_rate:
            self.settings.sample_rate = sample_rate

        # Convert stereo to mono if needed
        if audio_data.ndim == 2:
            audio_data = np.mean(audio_data, axis=1)

        # Calculate hop size
        hop_size = int(self.settings.fft_size * (1 - self.settings.overlap))

        # Calculate number of chunks
        num_chunks = (len(audio_data) - self.settings.fft_size) // hop_size + 1

        # Determine if we should use parallel processing
        use_parallel = (num_chunks >= self.settings.min_chunks_for_parallel and  # type: ignore[attr-defined]
                       self.settings.enable_parallel)  # type: ignore[attr-defined]

        if use_parallel:
            # Parallel FFT processing
            fft_results = self.fft_processor.parallel_windowed_fft(
                audio_data,
                fft_size=self.settings.fft_size,
                hop_size=hop_size,
                window=self.window
            )

            # Process FFT results in parallel
            with ThreadPoolExecutor(max_workers=self.settings.max_workers) as executor:  # type: ignore[attr-defined]
                chunk_results = list(executor.map(self._process_fft_to_spectrum, fft_results))
        else:
            # Sequential fallback for small files
            chunk_results = self._process_chunks_sequential(audio_data, hop_size, num_chunks)

        if not chunk_results:
            return {}

        # Aggregate results using SpectrumOperations
        aggregated = SpectrumOperations.aggregate_analysis_results(chunk_results)

        return {
            'spectrum': aggregated['spectrum'].tolist(),
            'frequency_bins': self.frequency_bins.tolist(),
            'peak_frequency': float(AggregationUtils.aggregate_frames_to_track(
                np.array([r['peak_frequency'] for r in chunk_results]), method='mean'
            )),
            'spectral_centroid': float(AggregationUtils.aggregate_frames_to_track(
                np.array([r['spectral_centroid'] for r in chunk_results]), method='mean'
            )),
            'spectral_rolloff': float(AggregationUtils.aggregate_frames_to_track(
                np.array([r['spectral_rolloff'] for r in chunk_results]), method='mean'
            )),
            'total_energy': float(AggregationUtils.aggregate_frames_to_track(
                np.array([r['total_energy'] for r in chunk_results]), method='mean'
            )),
            'num_chunks_analyzed': len(chunk_results),
            'analysis_duration': len(audio_data) / self.settings.sample_rate,
            'settings': {
                'fft_size': self.settings.fft_size,
                'frequency_bands': self.settings.frequency_bands,
                'weighting': self.settings.frequency_weighting,
                'overlap': self.settings.overlap,
                'parallel_processing': use_parallel
            }
        }

    def _process_chunks_sequential(self, audio_data: np.ndarray, hop_size: int, num_chunks: int) -> List[Dict[str, Any]]:
        """Process chunks sequentially (fallback for small files)"""
        chunk_results: List[Dict[str, Any]] = []

        for i in range(num_chunks):
            start_idx: int = i * hop_size
            end_idx: int = start_idx + self.settings.fft_size

            if end_idx <= len(audio_data):
                chunk: np.ndarray = audio_data[start_idx:end_idx]

                # Apply window and compute FFT
                windowed: np.ndarray = chunk * self.window
                fft_result: np.ndarray = np.fft.fft(windowed, self.settings.fft_size)

                # Process to spectrum
                result: Dict[str, Any] = self._process_fft_to_spectrum(fft_result)
                chunk_results.append(result)

        return chunk_results

    def _process_fft_to_spectrum(self, fft_result: np.ndarray) -> Dict[str, Any]:
        """
        Process single FFT result to spectrum (vectorized with band masks)

        Args:
            fft_result: FFT output

        Returns:
            Dictionary with spectrum metrics
        """
        # Get magnitude spectrum
        magnitude = np.abs(fft_result[:self.settings.fft_size // 2 + 1])

        # Map to frequency bands (vectorized using pre-computed masks)
        spectrum = self._map_to_bands_vectorized(magnitude)

        # Apply frequency weighting
        weighted_spectrum = spectrum + self.weighting_curve

        # Apply smoothing if we have a buffer
        if self.smoothing_buffer is not None:
            weighted_spectrum = (  # type: ignore[unreachable]
                self.settings.smoothing_factor * self.smoothing_buffer +
                (1 - self.settings.smoothing_factor) * weighted_spectrum
            )
            self.smoothing_buffer = weighted_spectrum
        else:
            self.smoothing_buffer = weighted_spectrum.copy()

        # Calculate metrics (vectorized)
        peak_frequency = self.frequency_bins[np.argmax(weighted_spectrum)]
        spectrum_sum = np.sum(weighted_spectrum)
        spectral_centroid = SafeOperations.safe_divide(
            np.sum(self.frequency_bins * weighted_spectrum),
            spectrum_sum,
            fallback=0.0
        )
        spectral_rolloff = self._calculate_rolloff_vectorized(weighted_spectrum)

        return {
            'spectrum': weighted_spectrum,
            'peak_frequency': float(peak_frequency),
            'spectral_centroid': float(spectral_centroid),
            'spectral_rolloff': float(spectral_rolloff),
            'total_energy': float(np.sum(weighted_spectrum))
        }

    def _map_to_bands_vectorized(self, magnitude: np.ndarray) -> np.ndarray:
        """
        Map FFT bins to frequency bands using pre-computed masks (vectorized)

        Args:
            magnitude: FFT magnitude spectrum

        Returns:
            Band energies in dB
        """
        spectrum: np.ndarray = np.zeros(len(self.frequency_bins))

        # Vectorized band mapping using pre-computed masks
        for i, mask in enumerate(self.band_masks):
            if np.any(mask):
                spectrum[i] = np.mean(magnitude[mask])

        # Convert to dB using safe log conversion
        from .fingerprint.common_metrics import AudioMetrics
        spectrum = AudioMetrics.rms_to_db(spectrum)

        return spectrum

    def _calculate_rolloff_vectorized(self, spectrum: np.ndarray, rolloff_threshold: float = 0.85) -> float:
        """
        Calculate spectral rolloff frequency (vectorized)

        Args:
            spectrum: Spectrum in dB
            rolloff_threshold: Energy threshold (default: 0.85 = 85%)

        Returns:
            Rolloff frequency in Hz
        """
        # Convert to linear energy
        energy: np.ndarray = 10 ** (spectrum / 20)

        # Cumulative sum (vectorized)
        cumulative_energy: np.ndarray = np.cumsum(energy)
        total_energy: Any = cumulative_energy[-1]
        rolloff_energy: Any = total_energy * rolloff_threshold

        # Find rolloff point (vectorized)
        rolloff_idx: Any = np.searchsorted(cumulative_energy, rolloff_energy)
        rolloff_idx = min(rolloff_idx, len(self.frequency_bins) - 1)

        return float(self.frequency_bins[rolloff_idx])


# Factory function
def create_parallel_spectrum_analyzer(settings: Optional[ParallelSpectrumSettings] = None) -> ParallelSpectrumAnalyzer:
    """
    Create parallel spectrum analyzer instance

    Args:
        settings: Spectrum analyzer settings

    Returns:
        Configured ParallelSpectrumAnalyzer
    """
    return ParallelSpectrumAnalyzer(settings)
