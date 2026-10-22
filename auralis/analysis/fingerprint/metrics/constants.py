"""
Fingerprint Constants
~~~~~~~~~~~~~~~~~~~~

Single source of truth for all fingerprint-related constants.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from ..schema import DIMENSION_NAMES

# The 25 fingerprint dimensions, by name. Lives beside
# FingerprintConstants.FINGERPRINT_DIMENSIONS (the count) so the two cannot
# drift — previously only the count was centralised here while the names were
# a set literal rebuilt per track inside FingerprintExtractor (#4283).
#
# This is the authoritative *complete* set. Other modules define
# purpose-specific subsets (target_derivation.TARGET_FEATURES,
# reference_seeder.BAND_FIELDS); those are not substitutes for this.
#
# Anything an analyzer emits that is NOT listed here is metadata (e.g.
# '_harmonic_analysis_method') and must not be persisted as a dimension.
FINGERPRINT_DIMENSION_NAMES: frozenset[str] = frozenset(DIMENSION_NAMES)


class FingerprintConstants:
    """
    Constants for fingerprint analysis.
    Single source of truth for all fingerprint-related constants.
    """

    # Core fingerprint dimensions
    FINGERPRINT_DIMENSIONS = 25
    EPSILON = 1e-10  # Safe epsilon for division/log operations

    # Stability/consistency scaling factors
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
