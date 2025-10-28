# -*- coding: utf-8 -*-

"""
Fingerprint Distance Calculator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Calculates weighted Euclidean distance between fingerprints for similarity ranking

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from ...utils.logging import info, warning, error, debug


@dataclass
class DimensionWeights:
    """Weights for fingerprint dimensions in similarity calculation"""

    # Frequency (7D) - Most important for perceived similarity
    sub_bass_pct: float = 0.04      # 4%
    bass_pct: float = 0.06           # 6%
    low_mid_pct: float = 0.05        # 5%
    mid_pct: float = 0.06            # 6%
    upper_mid_pct: float = 0.05      # 5%
    presence_pct: float = 0.04       # 4%
    air_pct: float = 0.03            # 3%
    # Subtotal: 33%

    # Dynamics (3D) - Very important
    lufs: float = 0.10               # 10%
    crest_db: float = 0.08           # 8%
    bass_mid_ratio: float = 0.05     # 5%
    # Subtotal: 23%

    # Temporal (4D) - Important for genre/style
    tempo_bpm: float = 0.08          # 8%
    rhythm_stability: float = 0.04   # 4%
    transient_density: float = 0.04  # 4%
    silence_ratio: float = 0.02      # 2%
    # Subtotal: 18%

    # Spectral (3D) - Moderate importance
    spectral_centroid: float = 0.05  # 5%
    spectral_rolloff: float = 0.04   # 4%
    spectral_flatness: float = 0.03  # 3%
    # Subtotal: 12%

    # Harmonic (3D) - Moderate importance
    harmonic_ratio: float = 0.04     # 4%
    pitch_stability: float = 0.03    # 3%
    chroma_energy: float = 0.02      # 2%
    # Subtotal: 9%

    # Variation (3D) - Low importance
    dynamic_range_variation: float = 0.02  # 2%
    loudness_variation_std: float = 0.02   # 2%
    peak_consistency: float = 0.01         # 1%
    # Subtotal: 5%

    # Stereo (2D) - Low importance
    stereo_width: float = 0.02       # 2%
    phase_correlation: float = 0.01  # 1%
    # Subtotal: 3%

    # TOTAL: 103% (normalized to 100% in to_array())

    def to_array(self) -> np.ndarray:
        """
        Convert weights to numpy array matching fingerprint dimension order

        Returns:
            25-element array of weights (normalized to sum=1.0)
        """
        weights = np.array([
            # Frequency (7D)
            self.sub_bass_pct,
            self.bass_pct,
            self.low_mid_pct,
            self.mid_pct,
            self.upper_mid_pct,
            self.presence_pct,
            self.air_pct,
            # Dynamics (3D)
            self.lufs,
            self.crest_db,
            self.bass_mid_ratio,
            # Temporal (4D)
            self.tempo_bpm,
            self.rhythm_stability,
            self.transient_density,
            self.silence_ratio,
            # Spectral (3D)
            self.spectral_centroid,
            self.spectral_rolloff,
            self.spectral_flatness,
            # Harmonic (3D)
            self.harmonic_ratio,
            self.pitch_stability,
            self.chroma_energy,
            # Variation (3D)
            self.dynamic_range_variation,
            self.loudness_variation_std,
            self.peak_consistency,
            # Stereo (2D)
            self.stereo_width,
            self.phase_correlation,
        ], dtype=np.float32)

        # Normalize to sum=1.0
        return weights / weights.sum()

    @classmethod
    def equal_weights(cls) -> 'DimensionWeights':
        """Create equal weights for all dimensions (1/25 each)"""
        weight = 1.0 / 25.0
        return cls(**{field: weight for field in cls.__dataclass_fields__})

    @classmethod
    def frequency_focused(cls) -> 'DimensionWeights':
        """Create weights emphasizing frequency distribution"""
        weights = cls()
        # Double frequency weights
        weights.sub_bass_pct *= 2.0
        weights.bass_pct *= 2.0
        weights.low_mid_pct *= 2.0
        weights.mid_pct *= 2.0
        weights.upper_mid_pct *= 2.0
        weights.presence_pct *= 2.0
        weights.air_pct *= 2.0
        return weights

    @classmethod
    def dynamics_focused(cls) -> 'DimensionWeights':
        """Create weights emphasizing dynamics"""
        weights = cls()
        # Double dynamics weights
        weights.lufs *= 2.0
        weights.crest_db *= 2.0
        weights.bass_mid_ratio *= 2.0
        return weights


class FingerprintDistance:
    """
    Calculate weighted Euclidean distance between fingerprints

    Distance Formula:
        d = sqrt(sum(w_i * (x_i - y_i)^2))

    Where:
        - w_i: weight for dimension i
        - x_i, y_i: normalized fingerprint values
        - Lower distance = more similar

    Usage:
        calculator = FingerprintDistance()
        distance = calculator.calculate(fp1_vector, fp2_vector)
    """

    def __init__(self, weights: Optional[DimensionWeights] = None):
        """
        Initialize distance calculator

        Args:
            weights: Dimension weights (default: use standard weights)
        """
        self.weights = weights or DimensionWeights()
        self.weight_array = self.weights.to_array()

    def calculate(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        Calculate weighted Euclidean distance between two fingerprints

        Args:
            vector1: First fingerprint vector (25D, normalized)
            vector2: Second fingerprint vector (25D, normalized)

        Returns:
            Distance value (0 = identical, higher = more different)

        Raises:
            ValueError: If vectors are wrong size
        """
        if len(vector1) != 25 or len(vector2) != 25:
            raise ValueError(f"Expected 25-element vectors, got {len(vector1)} and {len(vector2)}")

        # Weighted squared differences
        diff_squared = (vector1 - vector2) ** 2
        weighted_diff = self.weight_array * diff_squared

        # Euclidean distance
        distance = np.sqrt(np.sum(weighted_diff))

        return float(distance)

    def calculate_batch(self, target: np.ndarray, candidates: np.ndarray) -> np.ndarray:
        """
        Calculate distances from target to multiple candidates (vectorized)

        Args:
            target: Target fingerprint vector (25D)
            candidates: Candidate fingerprint vectors (N x 25)

        Returns:
            Distances array (N,)
        """
        if len(target) != 25:
            raise ValueError(f"Expected 25-element target vector, got {len(target)}")

        if candidates.shape[1] != 25:
            raise ValueError(f"Expected candidates with 25 dimensions, got {candidates.shape[1]}")

        # Vectorized calculation
        diff_squared = (candidates - target[np.newaxis, :]) ** 2
        weighted_diff = diff_squared * self.weight_array[np.newaxis, :]
        distances = np.sqrt(np.sum(weighted_diff, axis=1))

        return distances

    def find_closest_n(
        self,
        target: np.ndarray,
        candidates: List[Tuple[int, np.ndarray]],
        n: int = 10
    ) -> List[Tuple[int, float]]:
        """
        Find N closest fingerprints to target

        Args:
            target: Target fingerprint vector (25D)
            candidates: List of (track_id, fingerprint_vector) tuples
            n: Number of closest matches to return

        Returns:
            List of (track_id, distance) tuples, sorted by distance (ascending)
        """
        if not candidates:
            return []

        # Extract track IDs and vectors
        track_ids = [c[0] for c in candidates]
        vectors = np.array([c[1] for c in candidates])

        # Calculate all distances
        distances = self.calculate_batch(target, vectors)

        # Get indices of N smallest distances
        if n >= len(distances):
            # Return all, sorted
            sorted_indices = np.argsort(distances)
        else:
            # Partial sort for efficiency (O(n) instead of O(n log n))
            sorted_indices = np.argpartition(distances, n)[:n]
            # Sort just the selected indices
            sorted_indices = sorted_indices[np.argsort(distances[sorted_indices])]

        # Build result list
        results = [(track_ids[i], float(distances[i])) for i in sorted_indices[:n]]

        return results

    def calculate_similarity_score(self, distance: float, max_distance: float = 1.0) -> float:
        """
        Convert distance to similarity score (0-1 scale)

        Args:
            distance: Distance value
            max_distance: Maximum expected distance (for normalization)

        Returns:
            Similarity score (1.0 = identical, 0.0 = completely different)
        """
        # Inverse relationship: lower distance = higher similarity
        # Clamp to [0, max_distance]
        distance = min(distance, max_distance)

        # Convert to 0-1 similarity score
        similarity = 1.0 - (distance / max_distance)

        return similarity

    def get_dimension_contributions(
        self,
        vector1: np.ndarray,
        vector2: np.ndarray
    ) -> Dict[str, float]:
        """
        Get contribution of each dimension to total distance

        Useful for understanding why two tracks are similar/different

        Args:
            vector1: First fingerprint vector (25D)
            vector2: Second fingerprint vector (25D)

        Returns:
            Dictionary mapping dimension names to weighted distance contributions
        """
        from .normalizer import FingerprintNormalizer

        if len(vector1) != 25 or len(vector2) != 25:
            raise ValueError("Vectors must be 25D")

        # Calculate weighted squared differences
        diff_squared = (vector1 - vector2) ** 2
        weighted_diff = self.weight_array * diff_squared

        # Build dictionary
        contributions = {}
        for i, dim_name in enumerate(FingerprintNormalizer.DIMENSION_NAMES):
            contributions[dim_name] = float(weighted_diff[i])

        return contributions
