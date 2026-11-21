"""
Safe Mathematical Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Safe mathematical operations to prevent numerical errors.
Consolidates epsilon guards and fallback handling.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

from .constants import FingerprintConstants


class SafeOperations:
    """
    Safe mathematical operations to prevent numerical errors.
    Consolidates epsilon guards and fallback handling.
    """

    EPSILON = FingerprintConstants.EPSILON

    @staticmethod
    def safe_divide(
        numerator: np.ndarray,
        denominator: np.ndarray,
        fallback: float = 0.0
    ) -> np.ndarray:
        """
        Safe division with epsilon guard.

        Prevents division by zero and handles edge cases gracefully.

        Args:
            numerator: Numerator array/scalar
            denominator: Denominator array/scalar
            fallback: Value to use when denominator is too small

        Returns:
            Result of division with fallback where denominator is near zero
        """
        numerator = np.asarray(numerator)
        denominator = np.asarray(denominator)

        # Create safe denominator with epsilon guard
        safe_denom = np.where(
            np.abs(denominator) > SafeOperations.EPSILON,
            denominator,
            SafeOperations.EPSILON
        )

        # Perform division, using fallback where original denominator was too small
        result = np.divide(numerator, safe_denom)
        result = np.where(
            np.abs(denominator) <= SafeOperations.EPSILON,
            fallback,
            result
        )

        return result

