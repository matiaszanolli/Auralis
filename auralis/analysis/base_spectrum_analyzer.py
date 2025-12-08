# -*- coding: utf-8 -*-

"""
Base Spectrum Analyzer
~~~~~~~~~~~~~~~~~~~~~~

Abstract base class for spectrum analysis implementations.

Defines the common interface and shared functionality for all spectrum
analyzer implementations (sequential, parallel, real-time, etc.).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import numpy as np
from dataclasses import dataclass
from .spectrum_operations import SpectrumOperations


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


class BaseSpectrumAnalyzer(ABC):
    """Abstract base class for spectrum analyzers"""

    def __init__(self, settings: Optional[SpectrumSettings] = None) -> None:
        """
        Initialize base spectrum analyzer

        Args:
            settings: SpectrumSettings configuration object
        """
        self.settings = settings or SpectrumSettings()

        # Create frequency bins
        self.frequency_bins = SpectrumOperations.create_frequency_bins(
            min_freq=self.settings.min_frequency,
            max_freq=self.settings.max_frequency,
            num_bands=self.settings.frequency_bands
        )

        # Smoothing buffer for real-time analysis
        self.smoothing_buffer: Optional[np.ndarray] = None

        # Window function
        self.window = SpectrumOperations.create_window(
            self.settings.window_type,
            self.settings.fft_size
        )

        # Frequency weighting curve
        self.weighting_curve = SpectrumOperations.get_weighting_curve(
            self.frequency_bins,
            self.settings.frequency_weighting
        )

    @abstractmethod
    def analyze_chunk(self, audio_chunk: np.ndarray, channel: int = 0) -> Dict[str, Any]:
        """
        Analyze a chunk of audio data

        Args:
            audio_chunk: Audio data (mono or stereo)
            channel: Channel to analyze (0=left, 1=right, -1=sum)

        Returns:
            Dictionary with analysis results including:
            - spectrum: Frequency spectrum values
            - frequency_bins: Frequency bin centers
            - peak_frequency: Frequency with max energy
            - spectral_centroid: Center of mass frequency
            - spectral_rolloff: 85th percentile frequency
            - total_energy: Total spectral energy
            - settings: Analysis settings used
        """
        pass

    @abstractmethod
    def analyze_file(self, audio_data: np.ndarray, sample_rate: Optional[int] = None) -> Dict[str, Any]:
        """
        Analyze an entire audio file

        Args:
            audio_data: Complete audio data
            sample_rate: Sample rate (if different from settings)

        Returns:
            Dictionary with comprehensive analysis including:
            - spectrum: Aggregated frequency spectrum
            - frequency_bins: Frequency bin centers
            - peak_frequency: Mean peak frequency
            - spectral_centroid: Mean spectral centroid
            - spectral_rolloff: Mean spectral rolloff
            - total_energy: Mean total energy
            - num_chunks_analyzed: Number of chunks processed
            - analysis_duration: Duration analyzed in seconds
            - settings: Analysis settings used
        """
        pass

    def _create_chunk_result(self,
                            audio_chunk: np.ndarray,
                            channel: int = 0,
                            sample_rate: Optional[int] = None) -> Dict[str, Any]:
        """
        Create analysis result for a single audio chunk

        This is a helper method for subclasses to use.

        Args:
            audio_chunk: Audio data to analyze
            channel: Channel to analyze
            sample_rate: Sample rate (uses self.settings.sample_rate if None)

        Returns:
            Analysis result dictionary
        """
        if sample_rate is None:
            sample_rate = self.settings.sample_rate

        # Compute FFT
        magnitude, fft_size = SpectrumOperations.compute_fft(
            audio_chunk, self.window, self.settings.fft_size, channel
        )

        # Get frequency array
        frequencies = np.fft.rfftfreq(self.settings.fft_size, 1 / sample_rate)

        # Map to frequency bands
        spectrum = SpectrumOperations.map_to_bands(
            frequencies, magnitude, self.frequency_bins, sample_rate
        )

        # Apply frequency weighting
        weighted_spectrum = spectrum + self.weighting_curve

        # Apply smoothing
        weighted_spectrum = SpectrumOperations.apply_smoothing(
            weighted_spectrum,
            self.smoothing_buffer,
            self.settings.smoothing_factor
        )

        self.smoothing_buffer = weighted_spectrum

        # Calculate metrics
        peak_frequency = self.frequency_bins[np.argmax(weighted_spectrum)]
        spectral_centroid = SpectrumOperations.calculate_spectral_centroid(
            self.frequency_bins, weighted_spectrum
        )
        spectral_rolloff = SpectrumOperations.calculate_spectral_rolloff(
            self.frequency_bins, weighted_spectrum, 0.85
        )

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

    def get_frequency_band_names(self) -> List[str]:
        """
        Get human-readable frequency band names

        Returns:
            List of band name strings
        """
        return SpectrumOperations.get_band_names(self.frequency_bins)

    def reset_smoothing(self) -> None:
        """Reset smoothing buffer for new analysis session"""
        self.smoothing_buffer = None

    def update_settings(self, settings: SpectrumSettings) -> None:
        """
        Update analyzer settings and rebuild state

        Args:
            settings: New SpectrumSettings configuration
        """
        self.settings = settings

        # Rebuild frequency bins
        self.frequency_bins = SpectrumOperations.create_frequency_bins(
            min_freq=self.settings.min_frequency,
            max_freq=self.settings.max_frequency,
            num_bands=self.settings.frequency_bands
        )

        # Rebuild window
        self.window = SpectrumOperations.create_window(
            self.settings.window_type,
            self.settings.fft_size
        )

        # Rebuild weighting curve
        self.weighting_curve = SpectrumOperations.get_weighting_curve(
            self.frequency_bins,
            self.settings.frequency_weighting
        )

        # Reset smoothing buffer
        self.reset_smoothing()

    def _a_weighting_curve(self, frequencies: np.ndarray) -> np.ndarray:
        """
        Calculate A-weighting curve (backward compatibility wrapper)

        Args:
            frequencies: Frequency array in Hz

        Returns:
            A-weighting curve in dB
        """
        return SpectrumOperations.compute_a_weighting(frequencies)

    def _c_weighting_curve(self, frequencies: np.ndarray) -> np.ndarray:
        """
        Calculate C-weighting curve (backward compatibility wrapper)

        Args:
            frequencies: Frequency array in Hz

        Returns:
            C-weighting curve in dB
        """
        return SpectrumOperations.compute_c_weighting(frequencies)

    def _map_to_bands(self, freqs: np.ndarray, magnitude: np.ndarray) -> np.ndarray:
        """
        Map FFT bins to frequency bands (backward compatibility wrapper)

        Args:
            freqs: Frequency array from FFT
            magnitude: Magnitude spectrum from FFT

        Returns:
            Spectrum mapped to frequency bands (in dB)
        """
        return SpectrumOperations.map_to_bands(freqs, magnitude, self.frequency_bins, self.settings.sample_rate)

    def _calculate_rolloff(self, spectrum: np.ndarray, rolloff_threshold: float = 0.85) -> float:
        """
        Calculate spectral rolloff frequency (backward compatibility wrapper)

        Args:
            spectrum: Spectrum magnitude values (linear or dB)
            rolloff_threshold: Energy percentage threshold (0-1, default 85%)

        Returns:
            Spectral rolloff frequency in Hz
        """
        return SpectrumOperations.calculate_spectral_rolloff(self.frequency_bins, spectrum, rolloff_threshold)
