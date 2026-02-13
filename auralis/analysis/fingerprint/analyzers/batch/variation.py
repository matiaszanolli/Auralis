"""
Dynamic Variation Analyzer

Extracts dynamic variation features from audio for fingerprinting.

Features (3D):
  - dynamic_range_variation: How much dynamics change over time (0-1)
  - loudness_variation_std: Standard deviation of loudness across track (0-10)
  - peak_consistency: How consistent peaks are (0-1)

Dependencies:
  - variation_utilities for centralized variation calculations
  - base_analyzer for base analysis interface
"""

import logging

import numpy as np

from ...utilities.variation_ops import VariationOperations
from ..base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class VariationAnalyzer(BaseAnalyzer):
    """Extract dynamic variation features from audio."""

    DEFAULT_FEATURES = {
        'dynamic_range_variation': 0.5,
        'loudness_variation_std': 3.0,
        'peak_consistency': 0.7
    }

    def _analyze_impl(self, audio: np.ndarray, sr: int) -> dict[str, float]:
        """
        Analyze dynamic variation features.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 3 variation features
        """
        # Use centralized VariationOperations for all calculations
        # Pre-computes RMS and frame peaks once and reuses (efficiency optimized)
        dynamic_range_variation, loudness_variation_std, peak_consistency = VariationOperations.calculate_all(audio, sr)

        return {
            'dynamic_range_variation': float(dynamic_range_variation),
            'loudness_variation_std': float(loudness_variation_std),
            'peak_consistency': float(peak_consistency)
        }
