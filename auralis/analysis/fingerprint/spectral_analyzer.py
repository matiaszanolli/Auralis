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
  - common_metrics for unified utilities
"""

import numpy as np
import librosa
from typing import Dict, Optional
import logging
from .base_analyzer import BaseAnalyzer
from .common_metrics import MetricUtils, SafeOperations, AggregationUtils

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
        # OPTIMIZATION: Pre-compute STFT once, reuse for all spectral features
        # This eliminates 2x redundant STFT computation (100-200ms savings)
        S = librosa.stft(audio)
        magnitude = np.abs(S)

        # Spectral centroid (brightness) - pass pre-computed magnitude
        spectral_centroid = self._calculate_spectral_centroid(audio, sr, magnitude=magnitude)

        # Spectral rolloff (high-frequency content) - pass pre-computed magnitude
        spectral_rolloff = self._calculate_spectral_rolloff(audio, sr, magnitude=magnitude)

        # Spectral flatness (noise vs tonal) - pass pre-computed magnitude
        spectral_flatness = self._calculate_spectral_flatness(audio, magnitude=magnitude)

        return {
            'spectral_centroid': float(spectral_centroid),
            'spectral_rolloff': float(spectral_rolloff),
            'spectral_flatness': float(spectral_flatness)
        }

    def _calculate_spectral_centroid(self, audio: np.ndarray, sr: int,
                                    magnitude: Optional[np.ndarray] = None) -> float:
        """
        Calculate spectral centroid (center of mass of spectrum).

        Higher value = brighter sound (cymbals, high guitar)
        Lower value = darker sound (bass, low guitar)

        Args:
            audio: Audio signal (used if magnitude is None)
            sr: Sample rate
            magnitude: Pre-computed magnitude spectrum from STFT (optional optimization)

        Returns:
            Normalized spectral centroid (0-1)
        """
        try:
            # Calculate centroid (prefer pre-computed magnitude if provided)
            if magnitude is not None:
                # From pre-computed magnitude
                freqs = librosa.fft_frequencies(sr=sr, n_fft=2 * (magnitude.shape[0] - 1))
                centroid = np.average(freqs[:, np.newaxis], axis=0,
                                    weights=magnitude) if magnitude.shape[0] > 0 else np.array([0.0])
            else:
                # From audio
                centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]

            # Aggregate to track level (median across time)
            centroid_median = AggregationUtils.aggregate_frames_to_track(centroid, method='median')

            # Normalize to 0-1 (typical range: 0-8000 Hz)
            return MetricUtils.normalize_to_range(centroid_median, 8000.0, clip=True)

        except Exception as e:
            logger.debug(f"Spectral centroid calculation failed: {e}")
            return 0.5

    def _calculate_spectral_rolloff(self, audio: np.ndarray, sr: int,
                                   magnitude: Optional[np.ndarray] = None) -> float:
        """
        Calculate spectral rolloff (frequency below which 85% of energy is contained).

        Higher value = more high-frequency content (bright, airy)
        Lower value = less high-frequency content (dark, muffled)

        Args:
            audio: Audio signal (used if magnitude is None)
            sr: Sample rate
            magnitude: Pre-computed magnitude spectrum from STFT (optional optimization)

        Returns:
            Normalized spectral rolloff (0-1)
        """
        try:
            if magnitude is not None:
                # Calculate from pre-computed magnitude
                freqs = librosa.fft_frequencies(sr=sr, n_fft=2 * (magnitude.shape[0] - 1))

                # Normalize and compute cumulative energy per frame
                if magnitude.shape[1] > 0:
                    norm = SafeOperations.safe_divide(
                        np.ones_like(magnitude),
                        np.sum(magnitude, axis=0, keepdims=True)
                    )
                    magnitude_norm = magnitude * norm
                    cumsum = np.cumsum(magnitude_norm, axis=0)

                    # Find frequency at 85% cumulative energy
                    rolloff = np.array([
                        freqs[np.where(cumsum[:, i] >= 0.85)[0][0]]
                        if np.any(cumsum[:, i] >= 0.85)
                        else freqs[-1]
                        for i in range(magnitude.shape[1])
                    ])
                else:
                    rolloff = np.array([0.0])
            else:
                # Calculate from audio using librosa
                rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr, roll_percent=0.85)[0]

            # Aggregate to track level (median across time)
            rolloff_median = AggregationUtils.aggregate_frames_to_track(rolloff, method='median')

            # Normalize to 0-1 (typical range: 0-10000 Hz)
            return MetricUtils.normalize_to_range(rolloff_median, 10000.0, clip=True)

        except Exception as e:
            logger.debug(f"Spectral rolloff calculation failed: {e}")
            return 0.5

    def _calculate_spectral_flatness(self, audio: np.ndarray,
                                    magnitude: Optional[np.ndarray] = None) -> float:
        """
        Calculate spectral flatness (noise-like vs tonal).

        Higher value = noise-like (white noise, distortion)
        Lower value = tonal (clean instruments, vocals)

        Args:
            audio: Audio signal (used if magnitude is None)
            magnitude: Pre-computed magnitude spectrum from STFT (optional optimization)

        Returns:
            Spectral flatness (0-1)
        """
        try:
            if magnitude is not None:
                # Calculate from pre-computed magnitude (geometric mean / arithmetic mean)
                magnitude_safe = np.maximum(magnitude, SafeOperations.EPSILON)

                # Geometric mean (exp of mean log)
                geom_mean = np.exp(np.mean(np.log(magnitude_safe), axis=0))

                # Arithmetic mean
                arith_mean = np.mean(magnitude_safe, axis=0)

                # Flatness using safe divide
                flatness = SafeOperations.safe_divide(geom_mean, arith_mean)
            else:
                # Calculate from audio using librosa
                flatness = librosa.feature.spectral_flatness(y=audio)[0]

            # Aggregate to track level (median across time)
            flatness_median = AggregationUtils.aggregate_frames_to_track(flatness, method='median')

            # Already in 0-1 range
            return float(np.clip(flatness_median, 0, 1))

        except Exception as e:
            logger.debug(f"Spectral flatness calculation failed: {e}")
            return 0.3  # Default to tonal
