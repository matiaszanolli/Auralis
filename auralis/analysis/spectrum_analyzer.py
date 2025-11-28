# -*- coding: utf-8 -*-

"""
Advanced Spectrum Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~

Real-time and offline spectrum analysis with configurable parameters.
"""

import numpy as np
from scipy import signal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from .fingerprint.common_metrics import AudioMetrics, AggregationUtils


@dataclass
class SpectrumSettings:
    """Configuration for spectrum analysis"""
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


class SpectrumAnalyzer:
    """Advanced spectrum analyzer with real-time capabilities"""

    def __init__(self, settings: SpectrumSettings = None):
        self.settings = settings or SpectrumSettings()

        # Create frequency bins
        self.frequency_bins = self._create_frequency_bins()

        # Smoothing buffer for real-time analysis
        self.smoothing_buffer = None

        # Window function
        self.window = signal.get_window(
            self.settings.window_type,
            self.settings.fft_size
        )

        # Frequency weighting filters
        self._init_weighting_filters()

    def _create_frequency_bins(self) -> np.ndarray:
        """Create logarithmically spaced frequency bins"""
        return np.logspace(
            np.log10(self.settings.min_frequency),
            np.log10(self.settings.max_frequency),
            self.settings.frequency_bands
        )

    def _init_weighting_filters(self):
        """Initialize frequency weighting filters"""
        if self.settings.frequency_weighting == 'A':
            # A-weighting filter coefficients (simplified)
            self.weighting_curve = self._a_weighting_curve(self.frequency_bins)
        elif self.settings.frequency_weighting == 'C':
            # C-weighting filter coefficients (simplified)
            self.weighting_curve = self._c_weighting_curve(self.frequency_bins)
        else:
            # No weighting (Z)
            self.weighting_curve = np.ones(len(self.frequency_bins))

    def _a_weighting_curve(self, frequencies: np.ndarray) -> np.ndarray:
        """Calculate A-weighting curve"""
        f = frequencies
        f2 = f * f
        f4 = f2 * f2

        # A-weighting formula
        numerator = 12194**2 * f4
        denominator = (f2 + 20.6**2) * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2)) * (f2 + 12194**2)

        response = numerator / denominator
        # Normalize response by max value for consistent 0dB peak
        response_max = np.max(response)
        if response_max > 0:
            response_normalized = response / response_max
        else:
            response_normalized = response
        return 20 * np.log10(np.maximum(response_normalized, 1e-10))

    def _c_weighting_curve(self, frequencies: np.ndarray) -> np.ndarray:
        """Calculate C-weighting curve"""
        f = frequencies
        f2 = f * f
        f4 = f2 * f2

        # C-weighting formula (simplified)
        numerator = 12194**2 * f4
        denominator = (f2 + 20.6**2) * (f2 + 12194**2)

        response = numerator / denominator
        # Normalize response by max value for consistent 0dB peak
        response_max = np.max(response)
        if response_max > 0:
            response_normalized = response / response_max
        else:
            response_normalized = response
        return 20 * np.log10(np.maximum(response_normalized, 1e-10))

    def analyze_chunk(self, audio_chunk: np.ndarray, channel: int = 0) -> Dict:
        """
        Analyze a chunk of audio data

        Args:
            audio_chunk: Audio data (mono or stereo)
            channel: Channel to analyze (0=left, 1=right, -1=sum)

        Returns:
            Dictionary with analysis results
        """
        # Extract channel data
        if audio_chunk.ndim == 1:
            data = audio_chunk
        elif channel == -1:
            # Sum both channels
            data = np.sum(audio_chunk, axis=1) / 2
        else:
            data = audio_chunk[:, channel]

        # Ensure we have enough data
        if len(data) < self.settings.fft_size:
            data = np.pad(data, (0, self.settings.fft_size - len(data)))

        # Apply window
        windowed_data = data[:self.settings.fft_size] * self.window

        # Compute FFT
        fft = np.fft.rfft(windowed_data)
        magnitude = np.abs(fft)

        # Convert to frequency domain
        freqs = np.fft.rfftfreq(self.settings.fft_size, 1/self.settings.sample_rate)

        # Map to frequency bands
        spectrum = self._map_to_bands(freqs, magnitude)

        # Apply frequency weighting
        weighted_spectrum = spectrum + self.weighting_curve

        # Apply smoothing
        if self.smoothing_buffer is not None:
            weighted_spectrum = (
                self.settings.smoothing_factor * self.smoothing_buffer +
                (1 - self.settings.smoothing_factor) * weighted_spectrum
            )

        self.smoothing_buffer = weighted_spectrum

        # Calculate additional metrics
        peak_frequency = self.frequency_bins[np.argmax(weighted_spectrum)]
        spectral_centroid = np.sum(self.frequency_bins * weighted_spectrum) / np.sum(weighted_spectrum)
        spectral_rolloff = self._calculate_rolloff(weighted_spectrum, 0.85)

        return {
            'spectrum': weighted_spectrum.tolist(),
            'frequency_bins': self.frequency_bins.tolist(),
            'peak_frequency': float(peak_frequency),
            'spectral_centroid': float(spectral_centroid),
            'spectral_rolloff': float(spectral_rolloff),
            'total_energy': float(np.sum(weighted_spectrum)),
            'settings': {
                'fft_size': self.settings.fft_size,
                'frequency_bands': self.settings.frequency_bands,
                'weighting': self.settings.frequency_weighting
            }
        }

    def _map_to_bands(self, freqs: np.ndarray, magnitude: np.ndarray) -> np.ndarray:
        """Map FFT bins to frequency bands"""
        spectrum = np.zeros(len(self.frequency_bins))

        for i in range(len(self.frequency_bins) - 1):
            # Find FFT bins in this frequency band
            start_freq = self.frequency_bins[i]
            end_freq = self.frequency_bins[i + 1]

            mask = (freqs >= start_freq) & (freqs < end_freq)
            if np.any(mask):
                # Average magnitude in this band
                spectrum[i] = np.mean(magnitude[mask])

        # Handle last band
        mask = freqs >= self.frequency_bins[-1]
        if np.any(mask):
            spectrum[-1] = np.mean(magnitude[mask])

        # Convert to dB using safe log conversion
        spectrum = AudioMetrics.rms_to_db(spectrum)

        return spectrum

    def _calculate_rolloff(self, spectrum: np.ndarray, rolloff_threshold: float = 0.85) -> float:
        """Calculate spectral rolloff frequency"""
        cumulative_energy = np.cumsum(10**(spectrum/20))
        total_energy = cumulative_energy[-1]
        rolloff_energy = total_energy * rolloff_threshold

        rolloff_idx = np.argmax(cumulative_energy >= rolloff_energy)
        return self.frequency_bins[rolloff_idx]

    def analyze_file(self, audio_data: np.ndarray, sample_rate: int = None) -> Dict:
        """
        Analyze an entire audio file

        Args:
            audio_data: Complete audio data
            sample_rate: Sample rate (if different from settings)

        Returns:
            Dictionary with comprehensive analysis
        """
        if sample_rate:
            self.settings.sample_rate = sample_rate

        # Calculate hop size
        hop_size = int(self.settings.fft_size * (1 - self.settings.overlap))

        # Analyze in chunks
        num_chunks = (len(audio_data) - self.settings.fft_size) // hop_size + 1
        chunk_results = []

        for i in range(num_chunks):
            start_idx = i * hop_size
            end_idx = start_idx + self.settings.fft_size

            if end_idx <= len(audio_data):
                chunk = audio_data[start_idx:end_idx]
                if audio_data.ndim == 2:
                    chunk = chunk.reshape(-1, audio_data.shape[1])

                result = self.analyze_chunk(chunk)
                chunk_results.append(result)

        if not chunk_results:
            return {}

        # Aggregate results using AggregationUtils
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
                'overlap': self.settings.overlap
            }
        }

    def get_frequency_band_names(self) -> List[str]:
        """Get human-readable frequency band names"""
        band_names = []
        for freq in self.frequency_bins:
            if freq < 1000:
                band_names.append(f"{freq:.0f}Hz")
            else:
                band_names.append(f"{freq/1000:.1f}kHz")
        return band_names

    def reset_smoothing(self):
        """Reset smoothing buffer for new analysis session"""
        self.smoothing_buffer = None