# -*- coding: utf-8 -*-

"""
Parallel Spectrum Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~

High-performance spectrum analysis with parallel FFT processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from scipy import signal
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..optimization.parallel_processor import ParallelFFTProcessor, ParallelConfig
from ..utils.logging import debug
from .fingerprint.common_metrics import SafeOperations, AudioMetrics, AggregationUtils


@dataclass
class ParallelSpectrumSettings:
    """Configuration for parallel spectrum analysis"""
    fft_size: int = 4096
    window_type: str = 'hann'
    overlap: float = 0.75
    sample_rate: int = 44100
    frequency_bands: int = 64
    frequency_weighting: str = 'A'  # 'A', 'C', or 'Z' (none)
    smoothing_factor: float = 0.8

    # Frequency range
    min_frequency: float = 20.0
    max_frequency: float = 20000.0

    # Parallel processing
    enable_parallel: bool = True
    max_workers: int = 8
    min_chunks_for_parallel: int = 4  # Minimum chunks to use parallel processing


class ParallelSpectrumAnalyzer:
    """
    Advanced spectrum analyzer with parallel FFT processing

    Provides 3-4x speedup over sequential processing for long audio files
    """

    def __init__(self, settings: ParallelSpectrumSettings = None):
        self.settings = settings or ParallelSpectrumSettings()

        # Create frequency bins (vectorized)
        self.frequency_bins = self._create_frequency_bins()

        # Smoothing buffer for real-time analysis
        self.smoothing_buffer = None

        # Window function (cached)
        self.window = signal.get_window(
            self.settings.window_type,
            self.settings.fft_size
        )

        # Frequency weighting filters (pre-computed)
        self._init_weighting_filters()

        # Initialize parallel FFT processor
        parallel_config = ParallelConfig(
            enable_parallel=self.settings.enable_parallel,
            max_workers=self.settings.max_workers,
            use_multiprocessing=False  # Threading works well for FFT
        )
        self.fft_processor = ParallelFFTProcessor(parallel_config)

        # Pre-compute band masks for vectorized processing
        self._init_band_masks()

        debug(f"Parallel spectrum analyzer initialized: {self.settings.frequency_bands} bands, "
              f"{self.settings.max_workers} workers")

    def _create_frequency_bins(self) -> np.ndarray:
        """Create logarithmically spaced frequency bins (vectorized)"""
        return np.logspace(
            np.log10(self.settings.min_frequency),
            np.log10(self.settings.max_frequency),
            self.settings.frequency_bands
        )

    def _init_weighting_filters(self):
        """Initialize frequency weighting filters (vectorized)"""
        if self.settings.frequency_weighting == 'A':
            self.weighting_curve = self._a_weighting_curve(self.frequency_bins)
        elif self.settings.frequency_weighting == 'C':
            self.weighting_curve = self._c_weighting_curve(self.frequency_bins)
        else:
            self.weighting_curve = np.ones(len(self.frequency_bins))

    def _a_weighting_curve(self, frequencies: np.ndarray) -> np.ndarray:
        """Calculate A-weighting curve (fully vectorized)"""
        f = frequencies
        f2 = f * f
        f4 = f2 * f2

        numerator = 12194**2 * f4
        denominator = (f2 + 20.6**2) * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2)) * (f2 + 12194**2)

        response = numerator / denominator
        return 20 * np.log10(response / np.max(response))

    def _c_weighting_curve(self, frequencies: np.ndarray) -> np.ndarray:
        """Calculate C-weighting curve (fully vectorized)"""
        f = frequencies
        f2 = f * f
        f4 = f2 * f2

        numerator = 12194**2 * f4
        denominator = (f2 + 20.6**2) * (f2 + 12194**2)

        response = numerator / denominator
        return 20 * np.log10(response / np.max(response))

    def _init_band_masks(self):
        """Pre-compute band masks for vectorized band mapping"""
        freqs = np.fft.rfftfreq(self.settings.fft_size, 1/self.settings.sample_rate)
        num_bins = len(freqs)

        # Create masks for each band (vectorized)
        self.band_masks = []
        for i in range(len(self.frequency_bins) - 1):
            start_freq = self.frequency_bins[i]
            end_freq = self.frequency_bins[i + 1]
            mask = (freqs >= start_freq) & (freqs < end_freq)
            self.band_masks.append(mask)

        # Last band
        mask = freqs >= self.frequency_bins[-1]
        self.band_masks.append(mask)

        debug(f"Pre-computed {len(self.band_masks)} band masks for vectorized processing")

    def analyze_file(self, audio_data: np.ndarray, sample_rate: int = None) -> Dict:
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

        if num_chunks < self.settings.min_chunks_for_parallel or not self.settings.enable_parallel:
            # Sequential processing for small files
            return self._analyze_file_sequential(audio_data, hop_size, num_chunks)

        # Parallel FFT processing
        fft_results = self.fft_processor.parallel_windowed_fft(
            audio_data,
            fft_size=self.settings.fft_size,
            hop_size=hop_size,
            window=self.window
        )

        # Process FFT results in parallel
        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as executor:
            # Map each FFT to bands
            chunk_results = list(executor.map(self._process_fft_to_spectrum, fft_results))

        # Aggregate results using AggregationUtils (vectorized)
        aggregated_spectrum = np.mean([r['spectrum'] for r in chunk_results], axis=0)

        # Aggregate scalar metrics using standardized aggregation
        peak_frequencies = np.array([r['peak_frequency'] for r in chunk_results])
        spectral_centroids = np.array([r['spectral_centroid'] for r in chunk_results])
        spectral_rolloffs = np.array([r['spectral_rolloff'] for r in chunk_results])
        total_energies = np.array([r['total_energy'] for r in chunk_results])

        avg_peak_frequency = AggregationUtils.aggregate_frames_to_track(peak_frequencies, method='mean')
        avg_spectral_centroid = AggregationUtils.aggregate_frames_to_track(spectral_centroids, method='mean')
        avg_spectral_rolloff = AggregationUtils.aggregate_frames_to_track(spectral_rolloffs, method='mean')
        avg_total_energy = AggregationUtils.aggregate_frames_to_track(total_energies, method='mean')

        return {
            'spectrum': aggregated_spectrum.tolist(),
            'frequency_bins': self.frequency_bins.tolist(),
            'peak_frequency': float(avg_peak_frequency),
            'spectral_centroid': float(avg_spectral_centroid),
            'spectral_rolloff': float(avg_spectral_rolloff),
            'total_energy': float(avg_total_energy),
            'num_chunks_analyzed': len(chunk_results),
            'analysis_duration': len(audio_data) / self.settings.sample_rate,
            'settings': {
                'fft_size': self.settings.fft_size,
                'frequency_bands': self.settings.frequency_bands,
                'weighting': self.settings.frequency_weighting,
                'overlap': self.settings.overlap,
                'parallel_processing': True
            }
        }

    def _analyze_file_sequential(
        self,
        audio_data: np.ndarray,
        hop_size: int,
        num_chunks: int
    ) -> Dict:
        """Sequential analysis fallback for small files"""
        chunk_results = []

        for i in range(num_chunks):
            start_idx = i * hop_size
            end_idx = start_idx + self.settings.fft_size

            if end_idx <= len(audio_data):
                chunk = audio_data[start_idx:end_idx]

                # Apply window and compute FFT
                windowed = chunk * self.window
                fft_result = np.fft.fft(windowed, self.settings.fft_size)

                # Process to spectrum
                result = self._process_fft_to_spectrum(fft_result)
                chunk_results.append(result)

        # Aggregate using AggregationUtils
        aggregated_spectrum = np.mean([r['spectrum'] for r in chunk_results], axis=0)

        # Aggregate scalar metrics using standardized aggregation
        peak_frequencies = np.array([r['peak_frequency'] for r in chunk_results])
        spectral_centroids = np.array([r['spectral_centroid'] for r in chunk_results])
        spectral_rolloffs = np.array([r['spectral_rolloff'] for r in chunk_results])
        total_energies = np.array([r['total_energy'] for r in chunk_results])

        return {
            'spectrum': aggregated_spectrum.tolist(),
            'frequency_bins': self.frequency_bins.tolist(),
            'peak_frequency': float(AggregationUtils.aggregate_frames_to_track(peak_frequencies, method='mean')),
            'spectral_centroid': float(AggregationUtils.aggregate_frames_to_track(spectral_centroids, method='mean')),
            'spectral_rolloff': float(AggregationUtils.aggregate_frames_to_track(spectral_rolloffs, method='mean')),
            'total_energy': float(AggregationUtils.aggregate_frames_to_track(total_energies, method='mean')),
            'num_chunks_analyzed': len(chunk_results),
            'analysis_duration': len(audio_data) / self.settings.sample_rate,
            'settings': {
                'fft_size': self.settings.fft_size,
                'frequency_bands': self.settings.frequency_bands,
                'weighting': self.settings.frequency_weighting,
                'overlap': self.settings.overlap,
                'parallel_processing': False
            }
        }

    def _process_fft_to_spectrum(self, fft_result: np.ndarray) -> Dict:
        """
        Process single FFT result to spectrum (vectorized)

        Args:
            fft_result: FFT output

        Returns:
            Dictionary with spectrum metrics
        """
        # Get magnitude spectrum
        magnitude = np.abs(fft_result[:self.settings.fft_size // 2 + 1])

        # Map to frequency bands (vectorized using pre-computed masks)
        spectrum = self._map_to_bands_vectorized(magnitude)

        # Apply frequency weighting (vectorized)
        weighted_spectrum = spectrum + self.weighting_curve

        # Apply smoothing if we have a buffer
        if self.smoothing_buffer is not None:
            weighted_spectrum = (
                self.settings.smoothing_factor * self.smoothing_buffer +
                (1 - self.settings.smoothing_factor) * weighted_spectrum
            )
            self.smoothing_buffer = weighted_spectrum
        else:
            self.smoothing_buffer = weighted_spectrum.copy()

        # Calculate metrics (vectorized)
        peak_frequency = self.frequency_bins[np.argmax(weighted_spectrum)]
        # Use SafeOperations for safe division
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
        Map FFT bins to frequency bands (vectorized with pre-computed masks)

        Args:
            magnitude: FFT magnitude spectrum

        Returns:
            Band energies in dB
        """
        spectrum = np.zeros(len(self.frequency_bins))

        # Vectorized band mapping using pre-computed masks
        for i, mask in enumerate(self.band_masks):
            if np.any(mask):
                spectrum[i] = np.mean(magnitude[mask])

        # Convert to dB (vectorized) using safe log conversion
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
        energy = 10 ** (spectrum / 20)

        # Cumulative sum (vectorized)
        cumulative_energy = np.cumsum(energy)
        total_energy = cumulative_energy[-1]
        rolloff_energy = total_energy * rolloff_threshold

        # Find rolloff point (vectorized)
        rolloff_idx = np.searchsorted(cumulative_energy, rolloff_energy)
        rolloff_idx = min(rolloff_idx, len(self.frequency_bins) - 1)

        return self.frequency_bins[rolloff_idx]

    def analyze_chunk(self, audio_chunk: np.ndarray, channel: int = 0) -> Dict:
        """
        Analyze a single chunk of audio (for real-time processing)

        Args:
            audio_chunk: Audio data chunk
            channel: Channel to analyze (0=left, 1=right, -1=sum)

        Returns:
            Dictionary with analysis results
        """
        # Extract channel data
        if audio_chunk.ndim == 1:
            data = audio_chunk
        elif channel == -1:
            data = np.sum(audio_chunk, axis=1) / 2
        else:
            data = audio_chunk[:, channel]

        # Ensure we have enough data
        if len(data) < self.settings.fft_size:
            data = np.pad(data, (0, self.settings.fft_size - len(data)))

        # Apply window and compute FFT
        windowed_data = data[:self.settings.fft_size] * self.window
        fft_result = np.fft.fft(windowed_data, self.settings.fft_size)

        # Process to spectrum
        result = self._process_fft_to_spectrum(fft_result)

        return {
            'spectrum': result['spectrum'].tolist(),
            'frequency_bins': self.frequency_bins.tolist(),
            'peak_frequency': result['peak_frequency'],
            'spectral_centroid': result['spectral_centroid'],
            'spectral_rolloff': result['spectral_rolloff'],
            'total_energy': result['total_energy'],
            'settings': {
                'fft_size': self.settings.fft_size,
                'frequency_bands': self.settings.frequency_bands,
                'weighting': self.settings.frequency_weighting
            }
        }

    def reset_smoothing(self):
        """Reset smoothing buffer for new analysis session"""
        self.smoothing_buffer = None

    def get_frequency_band_names(self) -> List[str]:
        """Get human-readable frequency band names"""
        band_names = []
        for freq in self.frequency_bins:
            if freq < 1000:
                band_names.append(f"{freq:.0f}Hz")
            else:
                band_names.append(f"{freq/1000:.1f}kHz")
        return band_names


# Factory function
def create_parallel_spectrum_analyzer(settings: ParallelSpectrumSettings = None) -> ParallelSpectrumAnalyzer:
    """
    Create parallel spectrum analyzer instance

    Args:
        settings: Spectrum analyzer settings

    Returns:
        Configured ParallelSpectrumAnalyzer
    """
    return ParallelSpectrumAnalyzer(settings)
