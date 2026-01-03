# -*- coding: utf-8 -*-

"""
Spectral Operations
~~~~~~~~~~~~~~~~~~~

Spectral analysis utility operations.
Consolidates spectral normalization and processing patterns.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from .safe_operations import SafeOperations


class SpectralOperations:
    """
    Spectral analysis utility operations.
    Consolidates spectral normalization and processing patterns.
    """

    @staticmethod
    def normalize_magnitude(
        magnitude: np.ndarray,
        axis: int = 0
    ) -> np.ndarray:
        """
        Normalize magnitude spectrogram to [0, 1] per frequency bin or frame.

        Args:
            magnitude: Magnitude spectrogram (frequency x time or other)
            axis: Axis to normalize across

        Returns:
            Normalized magnitude spectrogram
        """
        norm: np.ndarray = np.sum(np.abs(magnitude), axis=axis, keepdims=True)
        norm = np.maximum(norm, SafeOperations.EPSILON)

        return magnitude / norm  # type: ignore[no-any-return]

    @staticmethod
    def spectral_flatness(
        magnitude: np.ndarray,
        axis: int = 0
    ) -> np.ndarray:
        """
        Calculate spectral flatness (Wiener entropy).

        Measures how white the spectrum is (flat = white noise, peaked = tonal).

        Args:
            magnitude: Magnitude spectrogram
            axis: Frequency axis

        Returns:
            Spectral flatness per frame [0, 1]
        """
        # Geometric mean
        geom_mean = SafeOperations.safe_power(
            np.prod(np.maximum(magnitude, SafeOperations.EPSILON), axis=axis),
            1.0 / magnitude.shape[axis]
        )

        # Arithmetic mean
        arith_mean = np.mean(magnitude, axis=axis)

        # Flatness = geom_mean / arith_mean
        flatness = SafeOperations.safe_divide(geom_mean, arith_mean)

        return np.clip(flatness, 0, 1)

    @staticmethod
    def spectral_centroid_safe(
        magnitude: np.ndarray,
        frequencies: np.ndarray
    ) -> float:
        """
        Calculate spectral centroid (brightness) safely.

        Args:
            magnitude: Magnitude spectrum
            frequencies: Corresponding frequencies

        Returns:
            Spectral centroid in Hz
        """
        magnitude = np.asarray(magnitude)
        frequencies = np.asarray(frequencies)

        # Normalize magnitude
        mag_norm = SafeOperations.safe_divide(
            magnitude,
            np.sum(magnitude)
        )

        # Weighted average of frequencies
        centroid = np.sum(frequencies * mag_norm)

        return float(centroid)
