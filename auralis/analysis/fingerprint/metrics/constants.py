"""
Fingerprint Constants
~~~~~~~~~~~~~~~~~~~~

Single source of truth for all fingerprint-related constants.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any


class FingerprintConstants:
    """
    Constants for fingerprint analysis.
    Single source of truth for all fingerprint-related constants.
    """

    # Core fingerprint dimensions
    FINGERPRINT_DIMENSIONS = 25
    EPSILON = 1e-10  # Safe epsilon for division/log operations

    # Normalization constants
    SPECTRAL_CENTROID_MAX = 8000.0
    SPECTRAL_ROLLOFF_MAX = 10000.0
    CHROMA_ENERGY_MAX = 0.4
    ONSET_DENSITY_MAX = 10.0

    # Stability/consistency scaling factors
    CV_HARMONIC_SCALE = 10.0  # Harmonic pitch stability uses higher sensitivity
    CV_DEFAULT_SCALE = 1.0    # Standard coefficient of variation scaling

    @staticmethod
    def validate_vector(vector: Any, expected_dims: int | None = None) -> bool:
        """
        Validate fingerprint vector dimensions.

        Args:
            vector: Vector to validate
            expected_dims: Expected dimensions (default: FINGERPRINT_DIMENSIONS)

        Returns:
            True if valid

        Raises:
            ValueError: If dimensions don't match
        """
        dims: int = expected_dims if expected_dims is not None else FingerprintConstants.FINGERPRINT_DIMENSIONS

        if len(vector) != dims:
            raise ValueError(
                f"Expected {dims}-element vector, got {len(vector)}"
            )

        return True
