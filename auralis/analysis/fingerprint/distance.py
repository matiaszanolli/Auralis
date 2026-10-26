"""
Fingerprint Distance Calculator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Calculates weighted Euclidean distance between fingerprints for similarity ranking

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import math

import numpy as np

from .dimension_weights import DimensionWeights
from .metrics import MetricUtils


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

    def __init__(self, weights: DimensionWeights | None = None):
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

        return np.asarray(distances, dtype=np.float32)

    def find_closest_n(
        self,
        target: np.ndarray,
        candidates: list[tuple[int, np.ndarray]],
        n: int = 10
    ) -> list[tuple[int, float]]:
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
            Similarity score in [0.0, 1.0] (1.0 = identical, 0.0 = completely
            different). Always finite, for any float input.

        A NaN distance collapses to 0.0 — "least similar" — rather than
        propagating (#5057). `np.clip` inside `normalize_to_range` handles ±inf
        (they saturate to 1.0 / 0.0) but passes NaN straight through, and NaN was
        the one value that escaped: every similarity score in the system comes
        from here, including the ones `KNNGraphBuilder` persists as graph edges,
        and the response models bound this field with `ge=0.0, le=1.0`, so a NaN
        became a `ResponseValidationError` — an opaque 500 — at serialization.

        0.0 rather than a neutral 0.5: `find_similar` sorts by this score
        descending, so a pair we could not measure must not outrank one we could.
        Sorting it last is the conservative recommendation; 0.5 would place an
        unmeasurable pair above genuinely dissimilar but correctly-measured ones.
        """
        # Inverse relationship: lower distance = higher similarity
        # Normalize distance to 0-1 using MetricUtils, then invert
        normalized_distance = MetricUtils.normalize_to_range(distance, max_distance, clip=True)
        similarity = 1.0 - normalized_distance

        if not math.isfinite(similarity):
            return 0.0

        return similarity

    def get_dimension_contributions(
        self,
        vector1: np.ndarray,
        vector2: np.ndarray
    ) -> dict[str, float]:
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
