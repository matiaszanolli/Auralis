"""
Scoring Operations
~~~~~~~~~~~~~~~~~~

Common scoring patterns and utilities for quality assessments.

Provides parameterized scoring functions used across all quality assessors
to ensure consistency and reduce code duplication.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

import numpy as np


class ScoringOperations:
    """Common scoring patterns for quality assessments"""

    @staticmethod
    def linear_scale_score(value: float, min_val: float, max_val: float,
                          inverted: bool = False) -> float:
        """
        Map a value to 0-100 scale between min and max

        Args:
            value: The value to scale
            min_val: Minimum acceptable value (maps to 0)
            max_val: Maximum acceptable value (maps to 100)
            inverted: If True, reverse the mapping (higher = worse)

        Returns:
            Score 0-100, clamped
        """
        if max_val == min_val:
            return 100.0 if value == max_val else 0.0

        normalized = (value - min_val) / (max_val - min_val)
        score = normalized * 100

        if inverted:
            score = 100 - score

        return float(np.clip(score, 0, 100))

    @staticmethod
    def range_based_score(value: float, optimal_range: tuple[float, float],
                         acceptable_range: tuple[float, float]) -> float:
        """
        Score based on optimal and acceptable ranges

        Structure:
        - Optimal range (100 points)
        - Acceptable range (70 points)
        - Outside (0 points with penalties)

        Args:
            value: The value to score
            optimal_range: Tuple (min, max) for 100-point range
            acceptable_range: Tuple (min, max) for 70-point range

        Returns:
            Score 0-100
        """
        opt_min, opt_max = optimal_range
        acc_min, acc_max = acceptable_range

        # In optimal range
        if opt_min <= value <= opt_max:
            return 100.0

        # In acceptable range (outside optimal)
        if acc_min <= value < opt_min:
            # Linear interpolation from acceptable to optimal
            return 70 + (value - acc_min) * 30 / (opt_min - acc_min)
        elif opt_max < value <= acc_max:
            # Linear interpolation from optimal to acceptable
            return 70 + (acc_max - value) * 30 / (acc_max - opt_max)

        # Outside acceptable range (penalty)
        if value < acc_min:
            # Penalty for too low
            range_width = opt_min - acc_min
            excess = acc_min - value
            penalty = min(70, excess * 70 / range_width)
            return max(0, 70 - penalty)
        else:
            # Penalty for too high
            range_width = acc_max - opt_max
            excess = value - acc_max
            penalty = min(70, excess * 70 / range_width)
            return max(0, 70 - penalty)

    @staticmethod
    def exponential_penalty(value: float, target: float,
                           steepness: float = 1.0) -> float:
        """
        Apply exponential penalty for deviation from target

        Useful for clipping detection, distortion, etc.

        Args:
            value: Measured value
            target: Target value
            steepness: Penalty steepness (default 1.0)

        Returns:
            Score 0-100
        """
        deviation = abs(value - target)
        # Exponential penalty: exp(-steepness * deviation)
        penalty_factor = np.exp(-steepness * deviation)
        return float(penalty_factor * 100)

    @staticmethod
    def weighted_score(*scores_and_weights: Any) -> float:
        """
        Combine multiple scores with weights

        Args:
            *scores_and_weights: Alternating (score, weight) pairs
                                 or list of (score, weight) tuples

        Returns:
            Weighted average score 0-100
        """
        if len(scores_and_weights) == 1 and isinstance(scores_and_weights[0], list):
            # Called with list of tuples
            pairs = scores_and_weights[0]
        else:
            # Called with individual arguments
            pairs = list(zip(scores_and_weights[0::2], scores_and_weights[1::2]))

        if not pairs:
            return 0.0

        total_weight = sum(w for _, w in pairs)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(score * weight for score, weight in pairs)
        return float(weighted_sum / total_weight)

    @staticmethod
    def percentile_score(value: float, percentiles: dict[int, tuple[float, float]]) -> float:
        """
        Score based on percentile distribution

        Percentiles dict should have format:
        {
            5: (value_at_p5, score_at_p5),
            25: (value_at_p25, score_at_p25),
            50: (value_at_p50, score_at_p50),  # Median
            75: (value_at_p75, score_at_p75),
            95: (value_at_p95, score_at_p95),
        }

        Args:
            value: The value to score
            percentiles: Dictionary of percentiles to (value, score) tuples

        Returns:
            Interpolated score 0-100
        """
        if not percentiles:
            return 50.0

        # Convert to sorted list of (percentile, value, score)
        sorted_percentiles = sorted(
            [(p, v, s) for p, (v, s) in percentiles.items()]
        )

        # Find surrounding percentiles
        for i, (p, v, s) in enumerate(sorted_percentiles):
            if value <= v:
                if i == 0:
                    return float(s)

                # Interpolate between previous and current
                p_prev, v_prev, s_prev = sorted_percentiles[i - 1]
                if v == v_prev:
                    return float((s + s_prev) / 2)

                # Linear interpolation
                progress = (value - v_prev) / (v - v_prev)
                interpolated_score = s_prev + (s - s_prev) * progress
                return float(np.clip(interpolated_score, 0, 100))

        # Beyond highest percentile
        _, _, last_score = sorted_percentiles[-1]
        return float(last_score)

    @staticmethod
    def band_score(value: float, bands: list[tuple[float, float]]) -> float:
        """
        Score using frequency bands

        Bands should be list of (threshold, score) tuples, sorted by threshold.
        Value falling between thresholds is interpolated.

        Args:
            value: The value to score
            bands: List of (threshold, score) tuples

        Returns:
            Interpolated score 0-100
        """
        if not bands:
            return 50.0

        bands = sorted(bands, key=lambda x: x[0])

        # Below lowest threshold
        if value <= bands[0][0]:
            return float(bands[0][1])

        # Find surrounding bands
        for i in range(len(bands) - 1):
            t1, s1 = bands[i]
            t2, s2 = bands[i + 1]

            if t1 <= value <= t2:
                if t1 == t2:
                    return float((s1 + s2) / 2)

                # Linear interpolation
                progress = (value - t1) / (t2 - t1)
                return float(s1 + (s2 - s1) * progress)

        # Above highest threshold
        return float(bands[-1][1])

    @staticmethod
    def consistency_score(values: list[float], target: float,
                         tolerance: float = 0.1) -> float:
        """
        Score consistency of multiple values around target

        Args:
            values: List of values to assess
            target: Target value
            tolerance: Acceptable deviation (default 10%)

        Returns:
            Score 0-100
        """
        if not values:
            return 100.0

        deviations = [abs(v - target) / max(abs(target), 0.001) for v in values]
        mean_deviation = float(np.mean(deviations))
        std_deviation = float(np.std(deviations))

        # Score based on how well values cluster around target
        if mean_deviation <= tolerance:
            consistency_score = 100.0
        else:
            # Penalize for average deviation
            penalty = min(100.0, mean_deviation * 100 / tolerance)
            consistency_score = 100 - penalty

        # Additional penalty for high variance
        variance_penalty = std_deviation * 100 / max(1.0, mean_deviation)
        final_score = consistency_score - min(30.0, variance_penalty)

        return float(np.clip(final_score, 0, 100))

    @staticmethod
    def threshold_score(value: float, threshold: float,
                       max_penalty: float = 100.0) -> float:
        """
        Score with hard threshold

        Score is 100 if value is below/equal threshold, 0 if above with
        linear penalty between.

        Args:
            value: The value to check
            threshold: The threshold
            max_penalty: Maximum penalty applied (default 100)

        Returns:
            Score 0-100
        """
        if value <= threshold:
            return 100.0

        # Linear penalty above threshold
        excess = value - threshold
        # Assume 2x threshold excess = 0 score
        penalty = min(max_penalty, excess * max_penalty / threshold)
        return float(max(0, 100 - penalty))
