# -*- coding: utf-8 -*-

"""
Variation Analysis Utilities

Shared dynamic variation feature calculations for batch and streaming analyzers.
Consolidates dynamic range variation, loudness variation, and peak consistency
calculations to eliminate duplication across variation_analyzer.py and
streaming_variation_analyzer.py.

Features:
  - dynamic_range_variation: How much dynamics change over time (0-1)
  - loudness_variation_std: Standard deviation of loudness across track (0-10)
  - peak_consistency: How consistent peaks are (0-1)
"""

import numpy as np
import librosa
import logging
from typing import Tuple, Optional, cast

logger = logging.getLogger(__name__)


class VariationOperations:
    """Centralized variation feature calculations."""

    @staticmethod
    def get_frame_peaks(
        audio: np.ndarray,
        hop_length: int,
        frame_length: int
    ) -> np.ndarray:
        """
        Vectorized frame peak detection.

        Computes maximum absolute value for each frame in single vectorized pass.
        This replaces two separate loops that were computing the same operation.

        Args:
            audio: Input audio signal
            hop_length: Hop size between frames
            frame_length: Frame window length

        Returns:
            Array of peak values for each frame (shape: (num_frames,))
        """
        audio_abs = np.abs(audio)
        num_frames = (len(audio) - frame_length) // hop_length + 1

        # Vectorized approach: reshape to frames and compute max across axis 1
        # Create frame indices for all frames
        frame_starts = np.arange(num_frames) * hop_length
        frame_indices = frame_starts[:, np.newaxis] + np.arange(frame_length)

        # Clip indices to valid range
        frame_indices = np.clip(frame_indices, 0, len(audio) - 1)

        # Vectorized indexing: extract all frames and compute max
        frames = audio_abs[frame_indices]
        peaks = np.max(frames, axis=1)

        return cast(np.ndarray, peaks)

    @staticmethod
    def calculate_dynamic_range_variation(
        audio: np.ndarray,
        sr: int,
        rms: Optional[np.ndarray] = None,
        hop_length: Optional[int] = None,
        frame_length: Optional[int] = None,
        frame_peaks: Optional[np.ndarray] = None
    ) -> float:
        """
        Calculate how much dynamic range changes over time.

        Higher value = more variation (classical, progressive)
        Lower value = consistent dynamics (pop, electronic)

        Args:
            audio: Audio signal
            sr: Sample rate
            rms: Pre-computed RMS values (optional optimization)
            hop_length: Hop length for RMS computation (used if rms provided)
            frame_length: Frame length for RMS computation (used if rms provided)
            frame_peaks: Pre-computed frame peaks (optional optimization)

        Returns:
            Dynamic range variation (0-1)
        """
        try:
            # Import here to avoid circular dependency
            from ..common_metrics import VariationMetrics

            # Use pre-computed RMS if provided, otherwise compute
            if rms is None:
                hop_length = int(sr * 0.25)  # 250ms hop
                frame_length = int(sr * 0.5)  # 500ms frames
                rms = librosa.feature.rms(
                    y=audio,
                    frame_length=frame_length,
                    hop_length=hop_length
                )[0]

            # Use pre-computed peaks if provided, otherwise compute
            if frame_peaks is None:
                assert hop_length is not None and frame_length is not None
                frame_peaks = VariationOperations.get_frame_peaks(audio, hop_length, frame_length)

            # Vectorized crest factor calculation (peak/RMS in dB)
            rms_safe = np.maximum(rms, 1e-10)
            peaks_safe = np.maximum(frame_peaks, 1e-10)
            crest_db = 20 * np.log10(peaks_safe / rms_safe)

            # Use unified VariationMetrics for calculation
            return VariationMetrics.calculate_from_crest_factors(crest_db)

        except Exception as e:
            logger.debug(f"Dynamic range variation calculation failed: {e}")
            return 0.5

    @staticmethod
    def calculate_loudness_variation(
        audio: np.ndarray,
        sr: int,
        rms: Optional[np.ndarray] = None
    ) -> float:
        """
        Calculate standard deviation of loudness over time.

        Higher value = more loudness variation (classical, film scores)
        Lower value = consistent loudness (pop, rock)

        Args:
            audio: Audio signal
            sr: Sample rate
            rms: Pre-computed RMS values (optional optimization)

        Returns:
            Loudness variation std dev (0-10 dB range typical)
        """
        try:
            # Import here to avoid circular dependency
            from ..common_metrics import VariationMetrics

            # Use pre-computed RMS if provided, otherwise compute
            if rms is None:
                hop_length = int(sr * 0.25)
                rms = librosa.feature.rms(y=audio, hop_length=hop_length)[0]

            # Convert to dB
            rms_db = librosa.amplitude_to_db(rms, ref=np.max)

            # Use unified VariationMetrics for calculation
            return VariationMetrics.calculate_from_loudness_db(rms_db)

        except Exception as e:
            logger.debug(f"Loudness variation calculation failed: {e}")
            return 3.0  # Default to moderate variation

    @staticmethod
    def calculate_peak_consistency(
        audio: np.ndarray,
        sr: int,
        frame_peaks: Optional[np.ndarray] = None
    ) -> float:
        """
        Calculate how consistent peaks are over time (OPTIMIZED).

        Higher value = consistent peaks (compressed music)
        Lower value = varying peaks (natural dynamics)

        Args:
            audio: Audio signal
            sr: Sample rate
            frame_peaks: Pre-computed frame peaks (optional optimization)

        Returns:
            Peak consistency (0-1)
        """
        try:
            # Import here to avoid circular dependency
            from ..common_metrics import VariationMetrics

            # Use pre-computed peaks if provided, otherwise compute
            if frame_peaks is None:
                hop_length = int(sr * 0.25)
                frame_length = int(sr * 0.5)
                frame_peaks = VariationOperations.get_frame_peaks(audio, hop_length, frame_length)

            # Use unified VariationMetrics for calculation
            return VariationMetrics.calculate_from_peaks(frame_peaks)

        except Exception as e:
            logger.debug(f"Peak consistency calculation failed: {e}")
            return 0.7  # Default to reasonably consistent

    @staticmethod
    def calculate_all(audio: np.ndarray, sr: int) -> Tuple[float, float, float]:
        """
        Calculate all three variation features in one call with pre-computed values.

        This is more efficient than calling individual methods as it computes
        expensive operations (RMS, frame peaks) only once.

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Tuple of (dynamic_range_variation, loudness_variation_std, peak_consistency)
        """
        try:
            # Pre-compute all shared values once
            hop_length_250ms = int(sr * 0.25)
            frame_length_500ms = int(sr * 0.5)

            # RMS for 250ms hop (used in both dynamic_range and loudness_variation)
            rms_250ms = librosa.feature.rms(y=audio, hop_length=hop_length_250ms)[0]

            # RMS with frame length for dynamic range calculation
            rms_with_frame = librosa.feature.rms(
                y=audio,
                frame_length=frame_length_500ms,
                hop_length=hop_length_250ms
            )[0]

            # Pre-compute frame peaks once (vectorized), reuse in both calculations
            frame_peaks = VariationOperations.get_frame_peaks(audio, hop_length_250ms, frame_length_500ms)

            # Calculate all metrics using pre-computed values
            dynamic_range_variation = VariationOperations.calculate_dynamic_range_variation(
                audio, sr, rms_with_frame, hop_length_250ms, frame_length_500ms, frame_peaks
            )
            loudness_variation_std = VariationOperations.calculate_loudness_variation(
                audio, sr, rms_250ms
            )
            peak_consistency = VariationOperations.calculate_peak_consistency(
                audio, sr, frame_peaks
            )

            return (dynamic_range_variation, loudness_variation_std, peak_consistency)

        except Exception as e:
            logger.debug(f"Variation analysis failed: {e}")
            # Return defaults if anything fails
            return (0.5, 3.0, 0.7)
