"""
Fingerprint Constants
~~~~~~~~~~~~~~~~~~~~

Single source of truth for all fingerprint-related constants.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

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
FINGERPRINT_DIMENSION_NAMES: frozenset[str] = frozenset({
    # 7-band spectral distribution
    'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
    'upper_mid_pct', 'presence_pct', 'air_pct',
    # Level / dynamics
    'lufs', 'crest_db', 'bass_mid_ratio',
    # Temporal
    'tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio',
    # Spectral shape
    'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
    # Harmonic
    'harmonic_ratio', 'pitch_stability', 'chroma_energy',
    # Stereo / consistency
    'stereo_width', 'phase_correlation', 'dynamic_range_variation',
    'loudness_variation_std', 'peak_consistency',
})


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
