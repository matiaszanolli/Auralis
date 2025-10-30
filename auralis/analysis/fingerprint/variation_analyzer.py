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
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class VariationAnalyzer:
    """Extract dynamic variation features from audio."""

    def analyze(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """
        Analyze dynamic variation features.

        Args:
            audio: Audio signal (mono)
            sr: Sample rate

        Returns:
            Dict with 3 variation features
        """
        try:
            # Dynamic range variation over time
            dynamic_range_variation = self._calculate_dynamic_range_variation(audio, sr)

            # Loudness variation (std dev)
            loudness_variation_std = self._calculate_loudness_variation(audio, sr)

            # Peak consistency
            peak_consistency = self._calculate_peak_consistency(audio, sr)

            return {
                'dynamic_range_variation': float(dynamic_range_variation),
                'loudness_variation_std': float(loudness_variation_std),
                'peak_consistency': float(peak_consistency)
            }

        except Exception as e:
            logger.warning(f"Variation analysis failed: {e}")
            return {
                'dynamic_range_variation': 0.5,
                'loudness_variation_std': 3.0,
                'peak_consistency': 0.7
            }

    def _calculate_dynamic_range_variation(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate how much dynamic range changes over time.

        Higher value = more variation (classical, progressive)
        Lower value = consistent dynamics (pop, electronic)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Dynamic range variation (0-1)
        """
        try:
            # Calculate RMS in short windows (500ms)
            hop_length = int(sr * 0.25)  # 250ms hop
            frame_length = int(sr * 0.5)  # 500ms frames

            rms = librosa.feature.rms(
                y=audio,
                frame_length=frame_length,
                hop_length=hop_length
            )[0]

            # Calculate crest factor per frame
            # Need to compute peak per frame
            num_frames = len(rms)
            crest_per_frame = []

            for i in range(num_frames):
                start = i * hop_length
                end = min(start + frame_length, len(audio))
                frame = audio[start:end]

                if len(frame) > 0:
                    peak = np.max(np.abs(frame))
                    rms_val = rms[i]
                    # Avoid division by zero and log(0)
                    if rms_val > 1e-10 and peak > 1e-10:
                        crest_db = 20 * np.log10(peak / rms_val)
                        crest_per_frame.append(crest_db)

            if len(crest_per_frame) > 1:
                # Variation = std dev of crest factor over time
                crest_std = np.std(crest_per_frame)

                # Normalize to 0-1
                # Typical range: 0-6 dB std dev
                # Low variation: < 2 dB (consistent)
                # High variation: > 4 dB (dynamic)
                normalized = crest_std / 6.0
                normalized = np.clip(normalized, 0, 1)
            else:
                normalized = 0.5

            return normalized

        except Exception as e:
            logger.debug(f"Dynamic range variation calculation failed: {e}")
            return 0.5

    def _calculate_loudness_variation(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate standard deviation of loudness over time.

        Higher value = more loudness variation (classical, film scores)
        Lower value = consistent loudness (pop, rock)

        Args:
            audio: Audio signal
            sr: Sample rate

        Returns:
            Loudness variation std dev (0-10 dB range typical)
        """
        try:
            # Calculate RMS in short windows
            hop_length = int(sr * 0.25)
            rms = librosa.feature.rms(y=audio, hop_length=hop_length)[0]

            # Convert to dB
            rms_db = librosa.amplitude_to_db(rms, ref=np.max)

            # Calculate std dev
            loudness_std = np.std(rms_db)

            # Clip to reasonable range
            # Typical: 2-8 dB std dev
            loudness_std = np.clip(loudness_std, 0, 10)

            return loudness_std

        except Exception as e:
            logger.debug(f"Loudness variation calculation failed: {e}")
            return 3.0  # Default to moderate variation

    def _calculate_peak_consistency(self, audio: np.ndarray, sr: int) -> float:
        """
        Calculate how consistent peaks are over time.

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
            peaks = []

            for i in range(num_frames):
                start = i * hop_length
                end = min(start + frame_length, len(audio))
                frame = audio[start:end]

                if len(frame) > 0:
                    peak = np.max(np.abs(frame))
                    peaks.append(peak)

            if len(peaks) > 1:
                # Consistency = inverse of peak variation
                peak_std = np.std(peaks)
                peak_mean = np.mean(peaks)

                if peak_mean > 0:
                    cv = peak_std / peak_mean  # Coefficient of variation
                    consistency = 1.0 / (1.0 + cv)
                else:
                    consistency = 0.5

                return np.clip(consistency, 0, 1)
            else:
                return 0.5

        except Exception as e:
            logger.debug(f"Peak consistency calculation failed: {e}")
            return 0.7  # Default to reasonably consistent
