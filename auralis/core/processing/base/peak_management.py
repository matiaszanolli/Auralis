"""
Peak Management
~~~~~~~~~~~~~~~

Safety limiter and peak normalizer for audio processing.
Consolidates safety checks and peak normalization across pipelines.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from ....dsp.dynamics.soft_clipper import soft_clip
from .db_conversion import DBConversion
from .processing_logger import ProcessingLogger


class SafetyLimiter:
    """
    Unified safety limiter to prevent digital clipping.
    Consolidates safety checks across normalization pipelines.
    """

    SAFETY_THRESHOLD_DB = -0.1   # dBFS - threshold for applying limiter (prevent digital clipping)
    SOFT_CLIP_THRESHOLD = 0.89   # Linear amplitude threshold for soft_clip (~-1 dB)

    @staticmethod
    def apply_if_needed(audio: np.ndarray) -> tuple[np.ndarray, bool]:
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
            ProcessingLogger.safety_check("Safety Limiter (post)", final_peak_db)

            return audio, True

        # Copy on bypass (#5107). `auralis/core/stages/__init__.py::no_op()`
        # defines the contract every named stage honours — an early-return
        # bypass never hands back the caller's array — and this is the same
        # maybe-process shape one package over. Today's callers happen to pass
        # an already-copied buffer, so nothing is exposed; the copy makes that
        # a property of this function rather than of its call sites.
        return audio.copy(), False


class PeakNormalizer:
    """
    Unified peak normalization logic.
    Consolidates peak-based gain adjustments across processing modes.
    """

    @staticmethod
    def normalize_to_target(audio: np.ndarray, target_peak_db: float,
                           preset_name: str | None = None) -> tuple[np.ndarray, float]:
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
            ProcessingLogger.post_stage("Peak Normalization", 0.0, target_peak_db, f"Preset: {preset_name}")

        if peak > 0.001:  # Avoid division by zero
            target_peak = DBConversion.to_linear(target_peak_db)
            # float() the scalar before scaling. NumPy promotes
            # float32_array * np.float64_scalar to float64, and callers do
            # hand np.float64 targets through here — e.g.
            # AdaptiveLoudnessControl.calculate_adaptive_peak_target() returns
            # one — which silently broke the float32-in/float32-out dtype
            # invariant. A Python float keeps the array's own dtype.
            audio = audio * float(target_peak / peak)
            ProcessingLogger.post_stage("Peak Normalization", peak_db, target_peak_db, "Peak")
            return audio, peak_db

        # Fourth site of the same bypass-without-copy shape, found by the
        # sibling sweep for #5107 (the issue listed three). Near-silent input
        # only, but the contract is the same.
        return audio.copy(), peak_db
