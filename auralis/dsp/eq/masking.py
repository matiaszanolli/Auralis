"""
Psychoacoustic Masking Calculations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Masking threshold calculations based on psychoacoustic models

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


import numpy as np

from .critical_bands import CriticalBand


class MaskingThresholdCalculator:
    """Calculate psychoacoustic masking thresholds"""

    def calculate_masking(self,
                         magnitude_spectrum: np.ndarray,
                         critical_bands: list[CriticalBand],
                         sample_rate: int) -> np.ndarray:
        """
        Calculate masking thresholds for each critical band

        Uses simplified psychoacoustic masking model based on spectral peaks
        and critical band analysis.

        Args:
            magnitude_spectrum: Magnitude spectrum (linear scale)
            critical_bands: List of critical bands
            sample_rate: Audio sample rate in Hz. Required (#4622) — used to
                derive each band's FFT bin range, so a missing/wrong value
                silently mis-places every masking threshold.

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
