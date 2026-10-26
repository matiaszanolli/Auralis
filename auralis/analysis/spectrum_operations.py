"""
Spectrum Operations
~~~~~~~~~~~~~~~~~~~

Common spectrum analysis patterns and operations for all spectrum analyzers.

Provides shared spectrum computation, weighting, band mapping, and analysis
functions used across sequential and parallel spectrum analyzers.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, cast

import numpy as np
from scipy import signal

from ..dsp.constants import DEFAULT_FFT_SIZE
from .fingerprint.metrics import AggregationUtils, AudioMetrics
from .spectrum_bands import band_masks
from .spectrum_weighting import WeightingMixin


class SpectrumOperations(WeightingMixin):
    """Common spectrum analysis operations"""

    @staticmethod
    def create_frequency_bins(min_freq: float = 20.0,
                              max_freq: float = 20000.0,
                              num_bands: int = 64) -> np.ndarray:
        """
        Create logarithmically spaced frequency bins

        Args:
            min_freq: Minimum frequency (Hz)
            max_freq: Maximum frequency (Hz)
            num_bands: Number of frequency bands

        Returns:
            Array of frequency bin centers
        """
        return np.logspace(
            np.log10(min_freq),
            np.log10(max_freq),
            num_bands
        )

    @staticmethod
    def create_window(window_type: str = 'hann',
                     fft_size: int = DEFAULT_FFT_SIZE) -> np.ndarray:
        """
        Create analysis window function

        Args:
            window_type: Type of window ('hann', 'hamming', 'blackman', etc.)
            fft_size: FFT size (window length)

        Returns:
            Window array
        """
        return cast(np.ndarray, signal.get_window(window_type, fft_size))

    @staticmethod
    def compute_fft(audio_data: np.ndarray,
                   window: np.ndarray,
                   fft_size: int,
                   channel: int = 0) -> tuple[np.ndarray, int]:
        """
        Compute FFT for audio chunk

        Args:
            audio_data: Audio data (mono or stereo)
            window: Window function
            fft_size: FFT size
            channel: Channel to analyze (0=left, 1=right, -1=sum)

        Returns:
            Tuple of (frequencies, magnitude_spectrum)
        """
        # Extract channel data
        if audio_data.ndim == 1:
            data = audio_data
        elif channel == -1:
            # Sum both channels
            data = np.sum(audio_data, axis=1) / 2
        else:
            data = audio_data[:, channel]

        # Ensure we have enough data
        if len(data) < fft_size:
            data = np.pad(data, (0, fft_size - len(data)))

        # Apply window and compute FFT
        windowed_data = data[:fft_size] * window
        fft_result = np.fft.rfft(windowed_data)
        magnitude = np.abs(fft_result)

        return magnitude, fft_size

    @staticmethod
    def map_to_bands(frequencies: np.ndarray,
                    magnitude: np.ndarray,
                    frequency_bins: np.ndarray) -> np.ndarray:
        """
        Map FFT bins to frequency bands

        Args:
            frequencies: Frequency array from FFT
            magnitude: Magnitude spectrum from FFT
            frequency_bins: Target frequency bin centers

        Returns:
            Spectrum mapped to frequency bands (in dB)
        """
        spectrum = np.zeros(len(frequency_bins))

        for i, mask in enumerate(band_masks(frequencies, frequency_bins)):
            if np.any(mask):
                # Average magnitude of the FFT bins in this band
                spectrum[i] = np.mean(magnitude[mask])

        # Convert to dB using safe log conversion
        spectrum = AudioMetrics.rms_to_db(spectrum)

        return spectrum

    @staticmethod
    def apply_smoothing(current_spectrum: np.ndarray,
                       previous_spectrum: np.ndarray | None,
                       smoothing_factor: float = 0.8) -> np.ndarray:
        """
        Apply exponential smoothing to spectrum

        Args:
            current_spectrum: Current spectrum values
            previous_spectrum: Previous spectrum values (or None for first frame)
            smoothing_factor: Smoothing factor (0-1, higher = more smoothing)

        Returns:
            Smoothed spectrum
        """
        if previous_spectrum is None:
            return current_spectrum

        return (smoothing_factor * previous_spectrum +
                (1 - smoothing_factor) * current_spectrum)

    @staticmethod
    def calculate_spectral_centroid(frequency_bins: np.ndarray,
                                   spectrum: np.ndarray) -> float:
        """
        Calculate spectral centroid (center of mass)

        Args:
            frequency_bins: Frequency bin centers
            spectrum: Spectrum magnitude values

        Returns:
            Spectral centroid in Hz
        """
        denominator = np.sum(spectrum)
        if denominator == 0:
            return float(frequency_bins[len(frequency_bins) // 2])

        return float(cast(np.ndarray, np.sum(frequency_bins * spectrum) / denominator))

    @staticmethod
    def calculate_spectral_rolloff(frequency_bins: np.ndarray,
                                  spectrum: np.ndarray,
                                  rolloff_threshold: float = 0.85) -> float:
        """
        Calculate spectral rolloff frequency

        Frequency below which a specified percentage of spectral energy is contained.

        Args:
            frequency_bins: Frequency bin centers
            spectrum: Spectrum magnitude values (linear or dB)
            rolloff_threshold: Energy percentage threshold (0-1, default 85%)

        Returns:
            Spectral rolloff frequency in Hz
        """
        # Convert from dB if necessary
        if np.any(spectrum < 0):
            # Assume already in dB
            linear_spectrum = 10**(spectrum / 20)
        else:
            linear_spectrum = spectrum

        cumulative_energy = np.cumsum(linear_spectrum)
        total_energy = cumulative_energy[-1]

        if total_energy == 0:
            return float(frequency_bins[-1])

        rolloff_energy = total_energy * rolloff_threshold
        rolloff_idx = np.argmax(cumulative_energy >= rolloff_energy)

        return float(cast(np.ndarray, frequency_bins[rolloff_idx]))

    @staticmethod
    def get_band_names(frequency_bins: np.ndarray) -> list[str]:
        """
        Get human-readable frequency band names

        Args:
            frequency_bins: Frequency bin centers

        Returns:
            List of band name strings
        """
        band_names = []
        for freq in frequency_bins:
            if freq < 1000:
                band_names.append(f"{freq:.0f}Hz")
            else:
                band_names.append(f"{freq/1000:.1f}kHz")
        return band_names

    @staticmethod
    def aggregate_analysis_results(chunk_results: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Aggregate spectrum analysis results across multiple chunks

        Args:
            chunk_results: List of analysis results from each chunk

        Returns:
            Aggregated analysis results
        """
        if not chunk_results:
            return {}

        # Aggregate spectrum
        aggregated_spectrum = np.mean([r['spectrum'] for r in chunk_results], axis=0)

        # Aggregate scalar metrics using standardized aggregation
        peak_frequencies = np.array([r['peak_frequency'] for r in chunk_results])
        spectral_centroids = np.array([r['spectral_centroid'] for r in chunk_results])
        spectral_rolloffs = np.array([r['spectral_rolloff'] for r in chunk_results])
        total_energies = np.array([r['total_energy'] for r in chunk_results])

        return {
            'spectrum': aggregated_spectrum,
            'peak_frequency': float(AggregationUtils.aggregate_frames_to_track(peak_frequencies, method='mean')),
            'spectral_centroid': float(AggregationUtils.aggregate_frames_to_track(spectral_centroids, method='mean')),
            'spectral_rolloff': float(AggregationUtils.aggregate_frames_to_track(spectral_rolloffs, method='mean')),
            'total_energy': float(AggregationUtils.aggregate_frames_to_track(total_energies, method='mean')),
            'num_chunks': len(chunk_results)
        }
