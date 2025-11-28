"""
Dynamic Variation Analyzer

Extracts dynamic variation features from audio for fingerprinting.

Features (3D):
  - dynamic_range_variation: How much dynamics change over time (0-1)
  - loudness_variation_std: Standard deviation of loudness across track (0-10)
  - peak_consistency: How consistent peaks are (0-1)

Dependencies:
  - numpy for numerical operations
  - librosa for loudness analysis
"""

import numpy as np
import librosa
from typing import Dict, Optional
import logging
from .base_analyzer import BaseAnalyzer
from .common_metrics import AudioMetrics, MetricUtils

logger = logging.getLogger(__name__)


class VariationAnalyzer(BaseAnalyzer):
    """Extract dynamic variation features from audio."""

    DEFAULT_FEATURES = {
        'dynamic_range_variation': 0.5,
        'loudness_variation_std': 3.0,
        'peak_consistency': 0.7
    }

    def _analyze_impl(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze dynamic variation features.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 3 variation features
        """
        # OPTIMIZATION: Pre-compute RMS with multiple hop lengths once
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

        # Dynamic range variation over time (pass pre-computed RMS for optimization)
        dynamic_range_variation = self._calculate_dynamic_range_variation(
            audio, sr, rms_with_frame, hop_length_250ms, frame_length_500ms
        )

        # Loudness variation (pass pre-computed RMS for optimization)
        loudness_variation_std = self._calculate_loudness_variation(audio, sr, rms_250ms)

        # Peak consistency
        peak_consistency = self._calculate_peak_consistency(audio, sr)

        return {
            'dynamic_range_variation': float(dynamic_range_variation),
            'loudness_variation_std': float(loudness_variation_std),
            'peak_consistency': float(peak_consistency)
        }

    def _calculate_dynamic_range_variation(self, audio: np.ndarray, sr: int,
                                          rms: Optional[np.ndarray] = None,
                                          hop_length: Optional[int] = None,
                                          frame_length: Optional[int] = None) -> float:
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

        Returns:
            Dynamic range variation (0-1)
        """
        try:
            # Use pre-computed RMS if provided, otherwise compute
            if rms is None:
                hop_length = int(sr * 0.25)  # 250ms hop
                frame_length = int(sr * 0.5)  # 500ms frames
                rms = librosa.feature.rms(
                    y=audio,
                    frame_length=frame_length,
                    hop_length=hop_length
                )[0]

            num_frames = len(rms)
            audio_abs = np.abs(audio)

            # Calculate peaks using NumPy vectorization (faster than Python loop)
            peaks = np.zeros(num_frames, dtype=audio.dtype)
            for i in range(num_frames):
                start = i * hop_length
                end = min(start + frame_length, len(audio))
                if start < len(audio):
                    peaks[i] = np.max(audio_abs[start:end])

            # Vectorized crest factor calculation (peak/RMS in dB)
            rms_safe = np.maximum(rms, 1e-10)
            peaks_safe = np.maximum(peaks, 1e-10)
            crest_db = 20 * np.log10(peaks_safe / rms_safe)

            # Filter out invalid values
            valid_mask = (rms > 1e-10) & (peaks > 1e-10)
            crest_valid = crest_db[valid_mask]

            if len(crest_valid) > 1:
                # Variation = std dev of crest factor over time
                crest_std = np.std(crest_valid)
                # Normalize to 0-1 (typical range: 0-6 dB std dev)
                normalized = MetricUtils.normalize_to_range(crest_std, 6.0, clip=True)
            else:
                normalized = 0.5

            return normalized

        except Exception as e:
            logger.debug(f"Dynamic range variation calculation failed: {e}")
            return 0.5

    def _calculate_loudness_variation(self, audio: np.ndarray, sr: int,
                                     rms: Optional[np.ndarray] = None) -> float:
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
            # Use pre-computed RMS if provided, otherwise compute
            if rms is None:
                hop_length = int(sr * 0.25)
                rms = librosa.feature.rms(y=audio, hop_length=hop_length)[0]

            # Convert to dB
            rms_db = librosa.amplitude_to_db(rms, ref=np.max)

            # Calculate std dev and clip to reasonable range
            loudness_std = np.std(rms_db)
            loudness_std = np.clip(loudness_std, 0, 10)

            return loudness_std

        except Exception as e:
            logger.debug(f"Loudness variation calculation failed: {e}")
            return 3.0  # Default to moderate variation

    def _calculate_peak_consistency(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate how consistent peaks are over time (OPTIMIZED).

        Higher value = consistent peaks (compressed music)
        Lower value = varying peaks (natural dynamics)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Peak consistency (0-1)
        """
        try:
            # Detect peaks in short windows
            hop_length = int(sr * 0.25)
            frame_length = int(sr * 0.5)

            num_frames = int(np.ceil(len(audio) / hop_length))
            audio_abs = np.abs(audio)

            # Optimized peak calculation: use NumPy operations
            peaks = np.zeros(num_frames, dtype=audio.dtype)

            # Calculate peaks using NumPy's max (faster than Python append/list)
            for i in range(num_frames):
                start = i * hop_length
                end = min(start + frame_length, len(audio))
                if start < len(audio):
                    peaks[i] = np.max(audio_abs[start:end])

            if len(peaks) > 1:
                # Consistency = inverse of peak variation using unified CV calculation
                peak_std = np.std(peaks)
                peak_mean = np.mean(peaks)

                # Use MetricUtils for unified CV→stability conversion
                consistency = MetricUtils.stability_from_cv(peak_std, peak_mean)

                return np.clip(consistency, 0, 1)
            else:
                return 0.5

        except Exception as e:
            logger.debug(f"Peak consistency calculation failed: {e}")
            return 0.7  # Default to reasonably consistent
