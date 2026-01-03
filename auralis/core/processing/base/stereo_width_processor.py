# -*- coding: utf-8 -*-

"""
Stereo Width Processor
~~~~~~~~~~~~~~~~~~~~~~

Unified stereo width processing with safety checks.
Consolidates 70% duplicate logic between adaptive and continuous modes.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from ....dsp.unified import adjust_stereo_width
from ....utils.logging import debug
from .db_conversion import DBConversion


class StereoWidthProcessor:
    """
    Unified stereo width processing with safety checks.
    Consolidates 70% duplicate logic between adaptive and continuous modes.
    """

    @staticmethod
    def validate_stereo(audio: np.ndarray) -> bool:
        """
        Check if audio is valid stereo.

        Args:
            audio: Audio array

        Returns:
            True if audio is 2D with 2 channels, False otherwise
        """
        return audio.ndim == 2 and audio.shape[1] == 2

    @staticmethod
    def get_peak_db(audio: np.ndarray) -> float:
        """
        Get peak amplitude in dB.

        Args:
            audio: Audio array

        Returns:
            Peak in dB using DBConversion
        """
        peak = np.max(np.abs(audio))
        return DBConversion.to_db(peak)

    @staticmethod
    def apply_stereo_width_safe(
        audio: np.ndarray,
        current_width: float,
        target_width: float,
        peak_db: float,
        safety_mode: str = "adaptive"
    ) -> np.ndarray:
        """
        Apply stereo width adjustment with safety checks to prevent peak clipping.

        Args:
            audio: Input audio array (must be stereo)
            current_width: Current stereo width (0-1)
            target_width: Target stereo width (0-1)
            peak_db: Current peak in dB
            safety_mode: Safety strategy ("adaptive" = limit expansion for loud material,
                                        "conservative" = skip expansion if peak > threshold)

        Returns:
            Audio with adjusted stereo width
        """
        # Strategy 1: Limit expansion for already-loud material (adaptive mode)
        if safety_mode == "adaptive":
            # For loud material with positive peaks, limit expansion
            if peak_db > 3.0 and target_width > current_width:
                max_width_increase = 0.6
                target_width = min(target_width, current_width + max_width_increase)
                debug(f"[Stereo Width] Limited expansion for loud material: target reduced to {target_width:.2f}")

        # Strategy 2: Skip expansion if peak is critically high (conservative mode)
        elif safety_mode == "conservative":
            if peak_db > 3.0 and target_width > current_width:
                debug(f"[Stereo Width] SKIPPED expansion due to high peak ({peak_db:.2f} dB)")
                return audio  # Return unmodified

        # Apply stereo width only if change is meaningful
        if abs(current_width - target_width) > 0.1:
            audio = adjust_stereo_width(audio, target_width)
            new_peak_db = StereoWidthProcessor.get_peak_db(audio)
            debug(f"[Stereo Width] Peak: {peak_db:.2f} → {new_peak_db:.2f} dB "
                  f"(width: {current_width:.2f} → {target_width:.2f})")

        return audio
