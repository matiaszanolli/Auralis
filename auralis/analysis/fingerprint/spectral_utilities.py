# -*- coding: utf-8 -*-

"""
Spectral Analysis Utilities

Shared spectral feature calculations for batch and streaming analyzers.
Consolidates spectral centroid, spectral rolloff, and spectral flatness
calculations to eliminate duplication across spectral_analyzer.py and
streaming_spectral_analyzer.py.

Features:
  - spectral_centroid: "Brightness" - center of mass of spectrum (0-1)
  - spectral_rolloff: High-frequency content - 85% of energy below this freq (0-1)
  - spectral_flatness: Noise-like (high) vs tonal (low) (0-1)
"""

import numpy as np
import librosa
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class SpectralOperations:
    """Centralized spectral feature calculations."""

    @staticmethod
    def calculate_spectral_centroid(audio: np.ndarray, sr: int,
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
            # Import here to avoid circular dependency
            from .common_metrics import MetricUtils, AggregationUtils

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

    @staticmethod
    def calculate_spectral_rolloff(audio: np.ndarray, sr: int,
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
            # Import here to avoid circular dependency
            from .common_metrics import MetricUtils, SafeOperations, AggregationUtils

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

                    # OPTIMIZATION: Vectorized rolloff calculation using argmax
                    # Find frequency at 85% cumulative energy for all frames simultaneously
                    # argmax returns first True index on boolean condition
                    rolloff_indices = np.argmax(cumsum >= 0.85, axis=0)

                    # Handle edge case: frames where cumsum never reaches 0.85
                    # argmax returns 0 for all-False, so manually check and set to last freq
                    never_reached = np.all(cumsum < 0.85, axis=0)
                    rolloff_indices[never_reached] = len(freqs) - 1

                    # Map indices to frequencies
                    rolloff = freqs[np.clip(rolloff_indices, 0, len(freqs) - 1)]
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

    @staticmethod
    def calculate_spectral_flatness(audio: np.ndarray,
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
            # Import here to avoid circular dependency
            from .common_metrics import SafeOperations, AggregationUtils

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

    @staticmethod
    def calculate_all(audio: np.ndarray, sr: int) -> Tuple[float, float, float]:
        """
        Calculate all three spectral features in one call with pre-computed STFT.

        This is more efficient than calling individual methods as it computes
        the expensive STFT only once.

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Tuple of (spectral_centroid, spectral_rolloff, spectral_flatness)
        """
        try:
            # Pre-compute STFT once
            S = librosa.stft(audio)
            magnitude = np.abs(S)

            # Calculate all metrics using pre-computed magnitude
            centroid = SpectralOperations.calculate_spectral_centroid(audio, sr, magnitude=magnitude)
            rolloff = SpectralOperations.calculate_spectral_rolloff(audio, sr, magnitude=magnitude)
            flatness = SpectralOperations.calculate_spectral_flatness(audio, magnitude=magnitude)

            return (centroid, rolloff, flatness)

        except Exception as e:
            logger.debug(f"Spectral analysis failed: {e}")
            # Return defaults if anything fails
            return (0.5, 0.5, 0.3)
