"""
Safe Mathematical Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Safe mathematical operations to prevent numerical errors.
Consolidates epsilon guards and fallback handling.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
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

    @staticmethod
    def safe_log(
        value: np.ndarray,
        fallback: float = -np.inf
    ) -> np.ndarray:
        """
        Safe logarithm operation.

        Prevents log(0) and handles small values gracefully.

        Args:
            value: Value or array to take log of
            fallback: Value to use for log(x <= epsilon)

        Returns:
            Logarithm with fallback for invalid inputs
        """
        value = np.asarray(value)

        # Create safe value with epsilon guard
        safe_value = np.maximum(value, SafeOperations.EPSILON)

        # Compute log
        result = np.log(safe_value)

        # Use fallback where original value was too small
        result = np.where(
            value <= SafeOperations.EPSILON,
            fallback,
            result
        )

        return result

    @staticmethod
    def safe_power(
        base: np.ndarray,
        exponent: float,
        fallback: float = 0.0
    ) -> np.ndarray:
        """
        Safe power operation for positive bases.

        Args:
            base: Base value(s)
            exponent: Exponent (typically 0.5 for square root, 1/3 for cube root)
            fallback: Value to use for base <= epsilon

        Returns:
            Result of base^exponent with fallback for small bases
        """
        base = np.asarray(base)

        # Create safe base with epsilon guard
        safe_base = np.maximum(base, SafeOperations.EPSILON)

        # Compute power
        result = np.power(safe_base, exponent)

        # Use fallback where original base was too small
        result = np.where(
            base <= SafeOperations.EPSILON,
            fallback,
            result
        )

        return result
