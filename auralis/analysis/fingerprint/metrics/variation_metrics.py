# -*- coding: utf-8 -*-

"""
Variation Metrics
~~~~~~~~~~~~~~~~~

Unified variation calculation pipelines for fingerprint analysis.

Consolidates repeated patterns for calculating different types of variation:
- Dynamic range variation (crest factor std)
- Loudness variation (RMS std in dB)
- Peak consistency (peak std CV→stability)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from .normalization import MetricUtils


class VariationMetrics:
    """
    Unified variation calculation pipelines for fingerprint analysis.

    Consolidates repeated patterns for calculating different types of variation:
    - Dynamic range variation (crest factor std)
    - Loudness variation (RMS std in dB)
    - Peak consistency (peak std CV→stability)
    """

    @staticmethod
    def calculate_from_crest_factors(crest_db: np.ndarray) -> float:
        """
        Calculate dynamic range variation from crest factors.

        Args:
            crest_db: Array of crest factors in dB

        Returns:
            Dynamic range variation (0-1), normalized to 6dB std range
        """
        if len(crest_db) < 2:
            return 0.5

        valid_mask = np.isfinite(crest_db)
        crest_valid = crest_db[valid_mask]

        if len(crest_valid) > 1:
            crest_std = np.std(crest_valid)
            # Normalize to 0-1 (typical range: 0-6 dB std dev)
            return MetricUtils.normalize_to_range(crest_std, 6.0, clip=True)
        else:
            return 0.5

    @staticmethod
    def calculate_from_loudness_db(loudness_db: np.ndarray, max_range: float = 10.0) -> float:
        """
        Calculate loudness variation from dB values.

        Args:
            loudness_db: Array of loudness values in dB
            max_range: Maximum expected range (default 10dB)

        Returns:
            Loudness variation (0-10 dB typical, clipped)
        """
        if len(loudness_db) < 1:
            return 3.0

        loudness_std = np.std(loudness_db)
        return MetricUtils.clip_to_range(loudness_std, 0, max_range)

    @staticmethod
    def calculate_from_peaks(peaks: np.ndarray) -> float:
        """
        Calculate peak consistency using CV→stability conversion.

        Args:
            peaks: Array of peak values

        Returns:
            Peak consistency (0-1)
        """
        if len(peaks) < 2:
            return 0.5

        peak_std = np.std(peaks)
        peak_mean = np.mean(peaks)

        if peak_mean > 0:
            return MetricUtils.stability_from_cv(peak_std, peak_mean)
        else:
            return 0.5
