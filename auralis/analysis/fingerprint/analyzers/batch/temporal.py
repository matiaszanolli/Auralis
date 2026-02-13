"""
Temporal/Rhythmic Feature Analyzer

Extracts temporal and rhythmic features from audio for fingerprinting.

Features (4D):
  - tempo_bpm: Beats per minute (tempo detection)
  - rhythm_stability: How consistent the rhythm is (0-1)
  - transient_density: Prominence of drums/percussion (0-1)
  - silence_ratio: Proportion of silence/space in music (0-1)

Dependencies:
  - temporal_utilities for shared temporal calculations
  - base_analyzer for error handling framework
  - numpy for numerical operations
"""

import logging

import numpy as np

from ...utilities.temporal_ops import TemporalOperations
from ..base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class TemporalAnalyzer(BaseAnalyzer):
    """Extract temporal and rhythmic features from audio."""

    DEFAULT_FEATURES = {
        'tempo_bpm': 120.0,
        'rhythm_stability': 0.5,
        'transient_density': 0.5,
        'silence_ratio': 0.1
    }

    def _analyze_impl(self, audio: np.ndarray, sr: int) -> dict[str, float]:
        """
        Analyze temporal/rhythmic features.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 4 temporal features
        """
        # Use centralized TemporalOperations for all calculations
        tempo_bpm, rhythm_stability, transient_density, silence_ratio = TemporalOperations.calculate_all(
            audio, sr
        )

        return {
            'tempo_bpm': tempo_bpm,
            'rhythm_stability': rhythm_stability,
            'transient_density': transient_density,
            'silence_ratio': silence_ratio
        }
