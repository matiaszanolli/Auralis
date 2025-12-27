"""
Harmonic Content Analyzer - Rust DSP Backend

Extracts harmonic features from audio for fingerprinting using Rust DSP.

Features (3D):
  - harmonic_ratio: Ratio of harmonic to percussive content (0-1)
  - pitch_stability: How in-tune/stable the pitch is (0-1)
  - chroma_energy: Tonal complexity/richness (0-1)

Dependencies:
  - harmonic_utilities for shared harmonic calculations (uses Rust DSP)
  - base_analyzer for error handling framework
  - numpy for numerical operations
"""

import logging
from typing import Dict

import numpy as np

from ...utilities.harmonic_ops import HarmonicOperations
from ..base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)

__all__ = ['HarmonicAnalyzer']


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
