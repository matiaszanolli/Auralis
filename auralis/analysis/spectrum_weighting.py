"""
Frequency weighting curves for SpectrumOperations (split from
spectrum_operations.py, #5838): A- and C-weighting and the selector.
"""

from typing import cast

import numpy as np


class WeightingMixin:
    """Static weighting helpers; ``SpectrumOperations`` inherits them."""

    @staticmethod
    def compute_a_weighting(frequencies: np.ndarray) -> np.ndarray:
        """
        Calculate A-weighting curve (ISO 61672-1)

        A-weighting emphasizes frequencies important to human hearing.

        Args:
            frequencies: Frequency array in Hz

        Returns:
            A-weighting curve in dB
        """
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

        return cast(np.ndarray, 20 * np.log10(np.maximum(response_normalized, 1e-10)))

    @staticmethod
    def compute_c_weighting(frequencies: np.ndarray) -> np.ndarray:
        """
        Calculate C-weighting curve (ISO 61672-1)

        C-weighting is flatter than A-weighting, used for high-level measurement.

        Args:
            frequencies: Frequency array in Hz

        Returns:
            C-weighting curve in dB
        """
        f = frequencies
        f2 = f * f
        f4 = f2 * f2

        # C-weighting formula
        numerator = 12194**2 * f4
        denominator = (f2 + 20.6**2) * (f2 + 12194**2)

        response = numerator / denominator

        # Normalize response by max value
        response_max = np.max(response)
        if response_max > 0:
            response_normalized = response / response_max
        else:
            response_normalized = response

        return cast(np.ndarray, 20 * np.log10(np.maximum(response_normalized, 1e-10)))

    @staticmethod
    def get_weighting_curve(frequencies: np.ndarray,
                           weighting_type: str = 'A') -> np.ndarray:
        """
        Get frequency weighting curve

        Args:
            frequencies: Frequency array in Hz
            weighting_type: 'A', 'C', or 'Z' (none)

        Returns:
            Weighting curve in dB
        """
        if weighting_type == 'A':
            return WeightingMixin.compute_a_weighting(frequencies)
        elif weighting_type == 'C':
            return WeightingMixin.compute_c_weighting(frequencies)
        else:
            # 'Z' or no weighting
            return np.zeros(len(frequencies))
