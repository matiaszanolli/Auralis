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
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ...utils.logging import debug, error, info, warning


@dataclass
class DimensionStats:
    """Statistics for a single fingerprint dimension"""
    name: str
    min_val: float
    max_val: float
    mean: float
    std: float
    count: int  # Number of samples used to calculate stats

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'min': self.min_val,
            'max': self.max_val,
            'mean': self.mean,
            'std': self.std,
            'count': self.count
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DimensionStats:
        """Create from dictionary"""
        return cls(
            name=data['name'],
            min_val=data['min'],
            max_val=data['max'],
            mean=data['mean'],
            std=data['std'],
            count=data['count']
        )


class FingerprintNormalizer:
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

    # Dimension names in order (must match TrackFingerprint.to_vector())
    DIMENSION_NAMES = [
        # Frequency (7D)
        'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
        'upper_mid_pct', 'presence_pct', 'air_pct',
        # Dynamics (3D)
        'lufs', 'crest_db', 'bass_mid_ratio',
        # Temporal (4D)
        'tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio',
        # Spectral (3D)
        'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
        # Harmonic (3D)
        'harmonic_ratio', 'pitch_stability', 'chroma_energy',
        # Variation (3D)
        'dynamic_range_variation', 'loudness_variation_std', 'peak_consistency',
        # Stereo (2D)
        'stereo_width', 'phase_correlation',
    ]

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

        Returns:
            True if successful, False if insufficient data
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

            self.stats[dim_name] = DimensionStats(
                name=dim_name,
                min_val=float(min_val),
                max_val=float(max_val),
                mean=float(mean),
                std=float(std),
                count=sample_count
            )

            debug(f"  {dim_name}: min={min_val:.3f}, max={max_val:.3f}, "
                  f"mean={mean:.3f}, std={std:.3f}")

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

    def normalize_batch(self, vectors: list[list[float]]) -> np.ndarray:
        """
        Normalize multiple fingerprint vectors

        Args:
            vectors: List of 25-element fingerprint vectors

        Returns:
            Normalized vectors (N x 25 numpy array)
        """
        if not self.fitted:
            raise ValueError("Normalizer not fitted. Call fit() first.")

        return np.array([self.normalize(v) for v in vectors])

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

    def save(self, filepath: str) -> bool:
        """
        Save normalization statistics to JSON file

        Args:
            filepath: Path to save statistics

        Returns:
            True if successful, False otherwise
        """
        if not self.fitted:
            warning("Normalizer not fitted, nothing to save")
            return False

        try:
            data = {
                'use_robust': self.use_robust,
                'percentile_range': list(self.percentile_range),
                'dimensions': {
                    name: stats.to_dict()
                    for name, stats in self.stats.items()
                }
            }

            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            info(f"Normalization statistics saved to {filepath}")
            return True

        except Exception as e:
            error(f"Failed to save normalization statistics: {e}")
            return False

    def load(self, filepath: str) -> bool:
        """
        Load normalization statistics from JSON file

        Args:
            filepath: Path to load statistics from

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filepath) as f:
                data = json.load(f)

            self.use_robust = data['use_robust']
            self.percentile_range = tuple(data['percentile_range'])
            self.stats = {
                name: DimensionStats.from_dict(stats_data)
                for name, stats_data in data['dimensions'].items()
            }

            self.fitted = True
            info(f"Normalization statistics loaded from {filepath}")
            return True

        except Exception as e:
            error(f"Failed to load normalization statistics: {e}")
            return False

    def get_stats_summary(self) -> dict[str, dict[str, float]]:
        """
        Get summary of normalization statistics

        Returns:
            Dictionary mapping dimension names to stats
        """
        if not self.fitted:
            return {}

        return {
            name: {
                'min': stats.min_val,
                'max': stats.max_val,
                'mean': stats.mean,
                'std': stats.std,
                'range': stats.max_val - stats.min_val
            }
            for name, stats in self.stats.items()
        }

    def is_fitted(self) -> bool:
        """Check if normalizer has been fitted"""
        return self.fitted
