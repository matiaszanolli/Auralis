"""
Aggregation Utilities
~~~~~~~~~~~~~~~~~~~~~

Methods for aggregating frame-level features to track-level features.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


import numpy as np


class AggregationUtils:
    """
    Methods for aggregating frame-level features to track-level features.
    """

    @staticmethod
    def aggregate_frames_to_track(
        frame_values: np.ndarray,
        method: str = "median"
    ) -> float:
        """
        Aggregate frame-level values to single track-level feature.

        Different aggregation methods capture different aspects:
        - median: Robust to outliers, typical behavior
        - mean: Average behavior
        - std: Variability
        - percentile: Percentile-based (upper/lower extreme)

        Args:
            frame_values: Array of per-frame values
            method: Aggregation method ('median', 'mean', 'std', 'min', 'max')

        Returns:
            Single aggregated feature value
        """
        frame_values = np.asarray(frame_values)

        if len(frame_values) == 0:
            return 0.5

        if method == "median":
            return float(np.median(frame_values))
        elif method == "mean":
            return float(np.mean(frame_values))
        elif method == "std":
            return float(np.std(frame_values))
        elif method == "min":
            return float(np.min(frame_values))
        elif method == "max":
            return float(np.max(frame_values))
        elif method == "percentile_95":
            return float(np.percentile(frame_values, 95))
        else:
            raise ValueError(f"Unknown aggregation method: {method}")
