"""
Spectral Character Analyzer

Extracts spectral features from audio for fingerprinting.

Features (3D):
  - spectral_centroid: "Brightness" - center of mass of spectrum (0-1)
  - spectral_rolloff: High-frequency content - 85% of energy below this freq (0-1)
  - spectral_flatness: Noise-like (high) vs tonal (low) (0-1)

Dependencies:
  - librosa for spectral analysis
  - numpy for numerical operations
"""

import numpy as np
import librosa
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class SpectralAnalyzer:
    """Extract spectral character features from audio."""

    def analyze(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze spectral features.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 3 spectral features
        """
        try:
            # Spectral centroid (brightness)
            spectral_centroid = self._calculate_spectral_centroid(audio, sr)

            # Spectral rolloff (high-frequency content)
            spectral_rolloff = self._calculate_spectral_rolloff(audio, sr)

            # Spectral flatness (noise vs tonal)
            spectral_flatness = self._calculate_spectral_flatness(audio)

            return {
                'spectral_centroid': float(spectral_centroid),
                'spectral_rolloff': float(spectral_rolloff),
                'spectral_flatness': float(spectral_flatness)
            }

        except Exception as e:
            logger.warning(f"Spectral analysis failed: {e}")
            return {
                'spectral_centroid': 0.5,
                'spectral_rolloff': 0.5,
                'spectral_flatness': 0.3
            }

    def _calculate_spectral_centroid(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate spectral centroid (center of mass of spectrum).

        Higher value = brighter sound (cymbals, high guitar)
        Lower value = darker sound (bass, low guitar)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Normalized spectral centroid (0-1)
        """
        try:
            # Calculate spectral centroid
            centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]

            # Take median across time (track-level characteristic)
            centroid_median = np.median(centroid)

            # Normalize to 0-1
            # Typical range: 0-8000 Hz
            # Dark (bass-heavy): 500-1500 Hz
            # Balanced: 1500-3000 Hz
            # Bright (treble-heavy): 3000-8000 Hz
            normalized = centroid_median / 8000.0
            normalized = np.clip(normalized, 0, 1)

            return normalized

        except Exception as e:
            logger.debug(f"Spectral centroid calculation failed: {e}")
            return 0.5

    def _calculate_spectral_rolloff(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate spectral rolloff (frequency below which 85% of energy is contained).

        Higher value = more high-frequency content (bright, airy)
        Lower value = less high-frequency content (dark, muffled)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Normalized spectral rolloff (0-1)
        """
        try:
            # Calculate spectral rolloff (85% default)
            rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr, roll_percent=0.85)[0]

            # Take median across time
            rolloff_median = np.median(rolloff)

            # Normalize to 0-1
            # Typical range: 0-10000 Hz
            # Dark: < 3000 Hz
            # Bright: > 6000 Hz
            normalized = rolloff_median / 10000.0
            normalized = np.clip(normalized, 0, 1)

            return normalized

        except Exception as e:
            logger.debug(f"Spectral rolloff calculation failed: {e}")
            return 0.5

    def _calculate_spectral_flatness(self, audio: np.ndarray) -> float:
        """
        Calculate spectral flatness (noise-like vs tonal).

        Higher value = noise-like (white noise, distortion)
        Lower value = tonal (clean instruments, vocals)

        Args:
            audio: Audio signal

        Returns:
            Spectral flatness (0-1)
        """
        try:
            # Calculate spectral flatness
            flatness = librosa.feature.spectral_flatness(y=audio)[0]

            # Take median across time
            flatness_median = np.median(flatness)

            # Already in 0-1 range
            return np.clip(flatness_median, 0, 1)

        except Exception as e:
            logger.debug(f"Spectral flatness calculation failed: {e}")
            return 0.3  # Default to tonal
