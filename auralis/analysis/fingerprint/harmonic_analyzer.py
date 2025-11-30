"""
Harmonic Content Analyzer

Extracts harmonic features from audio for fingerprinting.

Features (3D):
  - harmonic_ratio: Ratio of harmonic to percussive content (0-1)
  - pitch_stability: How in-tune/stable the pitch is (0-1)
  - chroma_energy: Tonal complexity/richness (0-1)

Dependencies:
  - harmonic_utilities for shared harmonic calculations
  - base_analyzer for error handling framework
  - numpy for numerical operations
"""

import numpy as np
from typing import Dict
import logging
from .base_analyzer import BaseAnalyzer
from .harmonic_utilities import HarmonicOperations, RUST_DSP_AVAILABLE

logger = logging.getLogger(__name__)

# Re-export RUST_DSP_AVAILABLE for backward compatibility
__all__ = ['HarmonicAnalyzer', 'RUST_DSP_AVAILABLE']


class HarmonicAnalyzer(BaseAnalyzer):
    """Extract harmonic content features from audio."""

    DEFAULT_FEATURES = {
        'harmonic_ratio': 0.5,
        'pitch_stability': 0.7,
        'chroma_energy': 0.5
    }

    def _analyze_impl(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze harmonic features.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 3 harmonic features
        """
        # Use centralized HarmonicOperations for all calculations
        harmonic_ratio, pitch_stability, chroma_energy = HarmonicOperations.calculate_all(audio, sr)

        return {
            'harmonic_ratio': harmonic_ratio,
            'pitch_stability': pitch_stability,
            'chroma_energy': chroma_energy
        }
