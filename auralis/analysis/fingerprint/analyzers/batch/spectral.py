"""
Spectral Character Analyzer

Extracts spectral features from audio for fingerprinting.

Features (3D):
  - spectral_centroid: "Brightness" - center of mass of spectrum (0-1)
  - spectral_rolloff: High-frequency content - 85% of energy below this freq (0-1)
  - spectral_flatness: Noise-like (high) vs tonal (low) (0-1)

Dependencies:
  - spectral_utilities for centralized spectral calculations
  - base_analyzer for base analysis interface
"""

import logging
from typing import Dict

import numpy as np

from ...utilities.spectral_ops import SpectralOperations
from ..base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class SpectralAnalyzer(BaseAnalyzer):
    """Extract spectral character features from audio."""

    DEFAULT_FEATURES = {
        'spectral_centroid': 0.5,
        'spectral_rolloff': 0.5,
        'spectral_flatness': 0.3
    }

    def _analyze_impl(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze spectral features.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 3 spectral features
        """
        # Use centralized SpectralOperations for all calculations
        # Pre-computes STFT once and reuses for all features (100-200ms savings)
        spectral_centroid, spectral_rolloff, spectral_flatness = SpectralOperations.calculate_all(audio, sr)

        return {
            'spectral_centroid': float(spectral_centroid),
            'spectral_rolloff': float(spectral_rolloff),
            'spectral_flatness': float(spectral_flatness)
        }
