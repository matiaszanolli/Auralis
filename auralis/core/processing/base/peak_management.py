# -*- coding: utf-8 -*-

"""
Peak Management
~~~~~~~~~~~~~~~

Safety limiter and peak normalizer for audio processing.
Consolidates safety checks and peak normalization across pipelines.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Optional, Tuple

import numpy as np

from ....dsp.dynamics.soft_clipper import soft_clip
from .db_conversion import DBConversion
from .processing_logger import ProcessingLogger


class SafetyLimiter:
    """
    Unified safety limiter to prevent digital clipping.
    Consolidates safety checks across normalization pipelines.
    """

    SAFETY_THRESHOLD_DB = 1.0    # dBFS - threshold for applying limiter (allow more boost headroom)
    SOFT_CLIP_THRESHOLD = 0.89   # Linear amplitude threshold for soft_clip (~-1 dB)

    @staticmethod
    def apply_if_needed(audio: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        Apply soft clipping limiter if peak exceeds safety threshold.

        The soft clipping curve (tanh) provides gentle, musical peak limiting
        that prevents digital clipping without introducing hard distortion.

        Args:
            audio: Input audio array

        Returns:
            Tuple of (processed audio, was_limiter_applied: bool)
        """
        final_peak = np.max(np.abs(audio))
        final_peak_db = DBConversion.to_db(final_peak)

        if final_peak_db > SafetyLimiter.SAFETY_THRESHOLD_DB:
            ProcessingLogger.safety_check("Safety Limiter", final_peak_db)
            audio = soft_clip(audio, threshold=SafetyLimiter.SOFT_CLIP_THRESHOLD)

            # Measure result
            final_peak = np.max(np.abs(audio))
            final_peak_db = DBConversion.to_db(final_peak)
            print(f"[Safety Limiter] Peak reduced to {final_peak_db:.2f} dB")

            return audio, True

        return audio, False


class PeakNormalizer:
    """
    Unified peak normalization logic.
    Consolidates peak-based gain adjustments across processing modes.
    """

    @staticmethod
    def normalize_to_target(audio: np.ndarray, target_peak_db: float,
                           preset_name: Optional[str] = None) -> Tuple[np.ndarray, float]:
        """
        Normalize audio peak to target level.

        Args:
            audio: Input audio array
            target_peak_db: Target peak level in dB
            preset_name: Optional preset name for logging

        Returns:
            Tuple of (normalized audio, previous_peak_db)
        """
        peak = np.max(np.abs(audio))
        peak_db = DBConversion.to_db(peak)

        if preset_name:
            print(f"[Peak Normalization] Preset: {preset_name}, Target: {target_peak_db:.2f} dB")

        if peak > 0.001:  # Avoid division by zero
            target_peak = DBConversion.to_linear(target_peak_db)
            audio = audio * (target_peak / peak)
            ProcessingLogger.post_stage("Peak Normalization", peak_db, target_peak_db, "Peak")
            return audio, peak_db

        return audio, peak_db
