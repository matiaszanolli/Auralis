# -*- coding: utf-8 -*-

"""
Psychoacoustic Masking Calculations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Masking threshold calculations based on psychoacoustic models

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import List
from .critical_bands import CriticalBand


class MaskingThresholdCalculator:
    """Calculate psychoacoustic masking thresholds"""

    def calculate_masking(self,
                         magnitude_spectrum: np.ndarray,
                         critical_bands: List[CriticalBand],
                         sample_rate: int = 44100) -> np.ndarray:
        """
        Calculate masking thresholds for each critical band

        Uses simplified psychoacoustic masking model based on spectral peaks
        and critical band analysis.

        Args:
            magnitude_spectrum: Magnitude spectrum (linear scale)
            critical_bands: List of critical bands
            sample_rate: Audio sample rate in Hz

        Returns:
            Masking threshold in dB for each band
        """
        thresholds = np.full(len(critical_bands), -60.0)  # Default threshold

        # Simplified masking calculation
        for i, band in enumerate(critical_bands):
            # Calculate FFT bin range for this band
            band_start = int(band.low_freq * len(magnitude_spectrum) * 2 / sample_rate)
            band_end = int(band.high_freq * len(magnitude_spectrum) * 2 / sample_rate)
            band_start = max(0, band_start)
            band_end = min(len(magnitude_spectrum), band_end)

            if band_end > band_start:
                band_magnitude = magnitude_spectrum[band_start:band_end]
                if len(band_magnitude) > 0:
                    peak_magnitude = np.max(band_magnitude)

                    # Calculate masking threshold (simplified)
                    # In reality, this would involve complex psychoacoustic modeling
                    # including simultaneous and temporal masking
                    threshold_db = 20 * np.log10(peak_magnitude + 1e-10) - 20
                    thresholds[i] = max(threshold_db, -80.0)

        return thresholds

    def calculate_simultaneous_masking(self,
                                      magnitude_spectrum: np.ndarray,
                                      critical_bands: List[CriticalBand]) -> np.ndarray:
        """
        Calculate simultaneous masking (frequency-domain masking)

        Simultaneous masking occurs when a strong signal masks weaker signals
        at nearby frequencies.

        Args:
            magnitude_spectrum: Magnitude spectrum
            critical_bands: List of critical bands

        Returns:
            Simultaneous masking threshold for each band
        """
        # This is a simplified model
        # A full implementation would use spreading functions
        return self.calculate_masking(magnitude_spectrum, critical_bands)

    def calculate_temporal_masking(self,
                                   magnitude_history: List[np.ndarray],
                                   critical_bands: List[CriticalBand]) -> np.ndarray:
        """
        Calculate temporal masking (time-domain masking)

        Temporal masking occurs before (pre-masking) and after (post-masking)
        a strong signal.

        Args:
            magnitude_history: List of magnitude spectra from recent frames
            critical_bands: List of critical bands

        Returns:
            Temporal masking threshold for each band
        """
        if not magnitude_history:
            return np.full(len(critical_bands), -60.0)

        # Simplified temporal masking based on recent peak levels
        num_bands = len(critical_bands)
        temporal_thresholds = np.full(num_bands, -60.0)

        # Use exponential decay for post-masking effect
        decay_weights = np.exp(-np.arange(len(magnitude_history)) * 0.5)

        for i in range(num_bands):
            band_peaks = []
            for spectrum in magnitude_history:
                # Extract band energy (simplified)
                if len(spectrum) > i:
                    band_peaks.append(spectrum[i] if i < len(spectrum) else 0.0)

            if band_peaks:
                weighted_peak = np.average(band_peaks, weights=decay_weights[:len(band_peaks)])
                temporal_thresholds[i] = 20 * np.log10(weighted_peak + 1e-10) - 30

        return temporal_thresholds
