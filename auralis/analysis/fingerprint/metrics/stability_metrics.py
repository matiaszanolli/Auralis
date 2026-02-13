"""
Stability Metrics
~~~~~~~~~~~~~~~~~

Unified stability calculation patterns from various audio metrics.

Consolidates the pattern: Extract metric → Calculate CV → Convert to stability
Used by: rhythm, pitch, and other stability calculations

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from .normalization import MetricUtils


class StabilityMetrics:
    """
    Unified stability calculation patterns from various audio metrics.

    Consolidates the pattern: Extract metric → Calculate CV → Convert to stability
    Used by: rhythm, pitch, and other stability calculations
    """

    @staticmethod
    def from_intervals(intervals: np.ndarray, scale: float = 1.0) -> float:
        """
        Calculate stability from inter-event intervals (rhythm, beats, etc).

        Args:
            intervals: Array of time intervals (e.g., beat-to-beat, note-to-note)
            scale: CV scaling factor (default 1.0)
                   Use higher for sensitive metrics (e.g., 10.0 for pitch)

        Returns:
            Stability score (0-1)
        """
        if len(intervals) < 2:
            return 0.0

        interval_std = np.std(intervals)
        interval_mean = np.mean(intervals)

        if interval_mean > 0:
            return MetricUtils.stability_from_cv(interval_std, interval_mean, scale=scale)
        else:
            return 0.5

    @staticmethod
    def from_values(values: np.ndarray, scale: float = 1.0) -> float:
        """
        Calculate stability from a set of values.

        Args:
            values: Array of metric values (e.g., pitches, peak amplitudes)
            scale: CV scaling factor (default 1.0)

        Returns:
            Stability score (0-1)
        """
        if len(values) < 2:
            return 0.5

        value_std = np.std(values)
        value_mean = np.mean(values)

        if value_mean > 0:
            return MetricUtils.stability_from_cv(value_std, value_mean, scale=scale)
        else:
            return 0.5
