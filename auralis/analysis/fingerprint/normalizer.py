"""
Fingerprint Normalizer
~~~~~~~~~~~~~~~~~~~~~

Normalizes 25D fingerprint vectors to 0-1 scale for fair similarity comparison

Different dimensions have different scales:
- tempo_bpm: 60-200 (range ~140)
- phase_correlation: -1 to 1 (range ~2)
- lufs: -30 to -5 (range ~25)

Without normalization, high-range dimensions dominate distance calculations.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import Any

import numpy as np

from ...utils.logging import debug, error, info
from .normalizer_stats import DimensionStats, NormalizerPersistenceMixin
from .schema import DIMENSION_NAMES


class FingerprintNormalizer(NormalizerPersistenceMixin):
    """
    Normalizes fingerprint vectors for similarity comparison

    Normalization Strategy:
    1. Min-Max Normalization: Scale to [0, 1] based on observed min/max
    2. Robust to Outliers: Uses percentiles (5th, 95th) instead of absolute min/max
    3. Per-Dimension: Each dimension normalized independently

    Usage:
        # Calculate statistics from library
        normalizer = FingerprintNormalizer()
        normalizer.fit(fingerprint_repository)

        # Normalize a fingerprint
        normalized = normalizer.normalize(fingerprint_vector)

        # Save/load statistics
        normalizer.save('stats.json')
        normalizer.load('stats.json')
    """

    # Dimension names in order (must match TrackFingerprint.to_vector()); derived
    # from the schema so it cannot drift (#5786).
    DIMENSION_NAMES: list[str] = list(DIMENSION_NAMES)

    def __init__(self, use_robust: bool = True, percentile_range: tuple[float, float] = (5.0, 95.0)):
        """
        Initialize normalizer

        Args:
            use_robust: Use percentile-based normalization (robust to outliers)
            percentile_range: Percentile range for robust normalization (default: 5th-95th)
        """
        self.use_robust = use_robust
        self.percentile_range = percentile_range
        self.stats: dict[str, DimensionStats] = {}
        self.fitted = False

    def fit(
        self,
        fingerprint_repository: Any,
        min_samples: int = 10,
        batch_size: int = 5000,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """
        Calculate normalization statistics from library fingerprints

        Reads fingerprints in bounded batches (#4115) so the entire
        ``track_fingerprints`` table is never hydrated as ORM objects at once.
        Only the compact numeric vectors are retained — each batch's ORM
        objects are released before the next batch is read, keeping peak ORM
        memory at ``O(batch_size)`` instead of ``O(N)``. Robust normalization
        needs exact per-dimension percentiles, so the (small) ``N x 25`` float
        array is still accumulated; the statistics are identical to a single
        full-table read.

        Args:
            fingerprint_repository: FingerprintRepository instance
            min_samples: Minimum number of fingerprints required
            batch_size: Rows hydrated per DB read (peak ORM memory bound)
            stop_event: Checked between batch reads (#4682) — if set, the
                fit is abandoned and this returns False rather than starting
                a new batch read. A background caller running this on a
                thread it cannot forcibly cancel (an in-flight DB read can't
                be interrupted) uses this for cooperative early exit, e.g.
                on process shutdown or a library reset.

        Returns:
            True if successful, False if insufficient data or stopped early
        """
        # Cheap count first so we can short-circuit without reading any rows.
        total = fingerprint_repository.get_count()
        if total < min_samples:
            error(f"Insufficient fingerprints for normalization: {total} < {min_samples}")
            return False

        info(f"Calculating normalization statistics from {total} fingerprints")

        # Stream rows in batches; keep only the numeric vectors. Each `batch`
        # of ORM objects becomes collectable when reassigned on the next
        # iteration, so the whole table is never held in RAM at once.
        batch_arrays: list[np.ndarray] = []
        offset = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                info("Similarity fit stopped before completing (#4682)")
                return False
            batch = fingerprint_repository.get_all(limit=batch_size, offset=offset)
            if not batch:
                break
            batch_arrays.append(
                np.asarray([fp.to_vector() for fp in batch], dtype=np.float64)
            )
            offset += len(batch)
            if len(batch) < batch_size:
                break

        if not batch_arrays:
            error("Insufficient fingerprints for normalization: 0 readable rows")
            return False

        # Single compact N x 25 float array (~10 MB at 50k tracks).
        vectors = np.vstack(batch_arrays)
        del batch_arrays
        sample_count = vectors.shape[0]

        # Build a complete replacement off to the side.  A fit may run while
        # existing similarity readers are still using the previous model;
        # publishing one new dict at the end keeps those readers from seeing
        # a partially populated set of dimensions (#5243).
        new_stats: dict[str, DimensionStats] = {}

        # Calculate statistics for each dimension
        for i, dim_name in enumerate(self.DIMENSION_NAMES):
            dim_values = vectors[:, i]

            if self.use_robust:
                # Use percentiles (robust to outliers)
                min_val = np.percentile(dim_values, self.percentile_range[0])
                max_val = np.percentile(dim_values, self.percentile_range[1])
            else:
                # Use absolute min/max
                min_val = np.min(dim_values)
                max_val = np.max(dim_values)

            mean = np.mean(dim_values)
            std = np.std(dim_values)

            new_stats[dim_name] = DimensionStats(
                name=dim_name,
                min_val=float(min_val),
                max_val=float(max_val),
                mean=float(mean),
                std=float(std),
                count=sample_count
            )

            debug(f"  {dim_name}: min={min_val:.3f}, max={max_val:.3f}, "
                  f"mean={mean:.3f}, std={std:.3f}")

        self.stats = new_stats
        self.fitted = True
        info("Normalization statistics calculated successfully")
        return True

    def normalize(self, vector: list[float]) -> np.ndarray:
        """
        Normalize a fingerprint vector to [0, 1] scale

        Args:
            vector: 25-element fingerprint vector

        Returns:
            Normalized vector (numpy array)

        Raises:
            ValueError: If normalizer not fitted or vector wrong size
        """
        if not self.fitted:
            raise ValueError("Normalizer not fitted. Call fit() first.")

        if len(vector) != 25:
            raise ValueError(f"Expected 25-element vector, got {len(vector)}")

        normalized = np.zeros(25, dtype=np.float32)

        for i, dim_name in enumerate(self.DIMENSION_NAMES):
            stats = self.stats[dim_name]
            value = vector[i]

            # Min-max normalization to [0, 1]
            range_val = stats.max_val - stats.min_val

            if range_val > 1e-6:  # Avoid division by zero
                normalized[i] = (value - stats.min_val) / range_val
            else:
                # Zero variance - set to 0.5 (middle of range)
                normalized[i] = 0.5
                debug(f"Zero variance for {dim_name}, using 0.5")

            # Clamp to [0, 1] (handles values outside observed range)
            normalized[i] = np.clip(normalized[i], 0.0, 1.0)

        return normalized

    def denormalize(self, normalized_vector: np.ndarray) -> np.ndarray:
        """
        Convert normalized vector back to original scale

        Useful for visualization/debugging

        Args:
            normalized_vector: Normalized vector (0-1 scale)

        Returns:
            Denormalized vector (original scale)
        """
        if not self.fitted:
            raise ValueError("Normalizer not fitted. Call fit() first.")

        if len(normalized_vector) != 25:
            raise ValueError(f"Expected 25-element vector, got {len(normalized_vector)}")

        denormalized = np.zeros(25, dtype=np.float32)

        for i, dim_name in enumerate(self.DIMENSION_NAMES):
            stats = self.stats[dim_name]
            norm_value = normalized_vector[i]

            # Reverse min-max normalization
            range_val = stats.max_val - stats.min_val
            denormalized[i] = norm_value * range_val + stats.min_val

        return denormalized

    def is_fitted(self) -> bool:
        """Check if normalizer has been fitted"""
        return self.fitted
