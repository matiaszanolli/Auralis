"""
Stereo Field Analyzer

Extracts stereo field features from audio for fingerprinting.

Features (2D):
  - stereo_width: Mono (0) to wide stereo (1)
  - phase_correlation: -1 (out of phase) to +1 (in phase)

Dependencies:
  - numpy for numerical operations
  - base_analyzer for unified error handling
"""

import logging

import numpy as np

from ...metrics import MetricUtils
from ..base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class StereoAnalyzer(BaseAnalyzer):
    """Extract stereo field features from audio."""

    DEFAULT_FEATURES = {
        'stereo_width': 0.5,
        'phase_correlation': 0.5
    }

    def _analyze_impl(self, audio: np.ndarray, sr: int) -> dict[str, float]:
        """
        Analyze stereo field features.

        Args:
            audio: Audio signal (stereo or mono)
            sr: Sample rate (unused, kept for API consistency)

        Returns:
            Dict with 2 stereo features
        """
        # Check if stereo or mono
        if len(audio.shape) == 1 or audio.shape[0] == 1:
            # Mono audio
            return {
                'stereo_width': 0.0,
                'phase_correlation': 1.0  # Perfect correlation (mono)
            }

        # Stereo audio - extract left and right channels
        if audio.shape[0] == 2:
            # (channels, samples)
            left = audio[0]
            right = audio[1]
        elif audio.shape[1] == 2:
            # (samples, channels)
            left = audio[:, 0]
            right = audio[:, 1]
        else:
            logger.warning(f"Unexpected audio shape: {audio.shape}")
            return {
                'stereo_width': 0.5,
                'phase_correlation': 0.5
            }

        # Calculate stereo width
        stereo_width = self._calculate_stereo_width(left, right)

        # Calculate phase correlation
        phase_correlation = self._calculate_phase_correlation(left, right)

        return {
            'stereo_width': float(stereo_width),
            'phase_correlation': float(phase_correlation)
        }

    def _calculate_stereo_width(self, left: np.ndarray, right: np.ndarray) -> float:
        """
        Calculate stereo width.

        0 = Mono (L == R)
        1 = Wide stereo (L very different from R)

        Args:
            left: Left channel
            right: Right channel

        Returns:
            Stereo width (0-1)
        """
        try:
            # Calculate mid and side signals
            mid = (left + right) / 2.0
            side = (left - right) / 2.0

            # Calculate energy of each
            mid_energy = np.sum(mid ** 2)
            side_energy = np.sum(side ** 2)

            total_energy = mid_energy + side_energy

            if total_energy > 0:
                # Stereo width = ratio of side to total
                width = side_energy / total_energy
            else:
                width = 0.0

            return float(np.clip(width, 0, 1))

        except Exception as e:
            logger.debug(f"Stereo width calculation failed: {e}")
            return 0.5

    def _calculate_phase_correlation(self, left: np.ndarray, right: np.ndarray) -> float:
        """
        Calculate phase correlation between left and right channels.

        +1 = Perfect correlation (in phase, mono)
         0 = Uncorrelated (decorrelated stereo)
        -1 = Perfect anti-correlation (out of phase)

        Args:
            left: Left channel
            right: Right channel

        Returns:
            Phase correlation (-1 to +1)
        """
        try:
            # Pearson correlation coefficient
            if len(left) != len(right):
                min_len = min(len(left), len(right))
                left = left[:min_len]
                right = right[:min_len]

            # Normalize
            left_norm = left - np.mean(left)
            right_norm = right - np.mean(right)

            # Calculate correlation
            numerator = np.sum(left_norm * right_norm)
            denominator = np.sqrt(np.sum(left_norm ** 2) * np.sum(right_norm ** 2))

            if denominator > 0:
                correlation = numerator / denominator
            else:
                correlation = 1.0  # Silence = perfect correlation

            # Clip correlation to -1 to +1 range using MetricUtils
            return MetricUtils.clip_to_range(correlation, -1, 1)

        except Exception as e:
            logger.debug(f"Phase correlation calculation failed: {e}")
            return 0.5
