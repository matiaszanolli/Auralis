"""
Stereo Width Processor
~~~~~~~~~~~~~~~~~~~~~~

Unified stereo width processing with safety checks.
Consolidates 70% duplicate logic between adaptive and continuous modes.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from ....dsp.utils.stereo import WIDTH_FACTOR_UNITY, adjust_stereo_width_multiband
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
        sample_rate: int,
        safety_mode: str = "adaptive",
    ) -> np.ndarray:
        """
        Apply stereo width adjustment with safety checks to prevent peak clipping.

        Args:
            audio: Input audio array (must be stereo)
            current_width: Measured DECORRELATION of the input (0 = mono). Kept
                for logging/diagnostics only — see the scale note below.
            target_width: Target WIDTH FACTOR (side-gain axis, 0.5 = unchanged)
            peak_db: Current peak in dB
            sample_rate: Sample rate, for the multiband crossovers. Required
                (#4622) — passed straight through to
                adjust_stereo_width_multiband(), where a missing/wrong value
                silently mis-places every frequency band.
            safety_mode: Safety strategy ("adaptive" = limit expansion for loud material,
                                        "conservative" = skip expansion if peak > threshold)

        Returns:
            Audio with adjusted stereo width

        Scales (#4503): ``current_width`` and ``target_width`` are NOT on the
        same axis — the first is a measurement (decorrelation), the second an
        instruction (side gain). Both sit in 0..1 with 0.5 near the middle,
        which is why the old ``target_width > current_width`` and
        ``abs(current_width - target_width)`` tests looked plausible and were
        meaningless. Every decision below is made against
        :data:`WIDTH_FACTOR_UNITY`, the point at which a width factor leaves the
        signal untouched.
        """
        # Strategy 1: Limit expansion for already-loud material (adaptive mode)
        if safety_mode == "adaptive":
            # For loud material with positive peaks, limit expansion
            if peak_db > 3.0 and target_width > WIDTH_FACTOR_UNITY:
                max_width_increase = 0.6
                target_width = min(target_width, WIDTH_FACTOR_UNITY + max_width_increase)
                debug(f"[Stereo Width] Limited expansion for loud material: target reduced to {target_width:.2f}")

        # Strategy 2: Skip expansion if peak is critically high (conservative mode)
        elif safety_mode == "conservative":
            if peak_db > 3.0 and target_width > WIDTH_FACTOR_UNITY:
                debug(f"[Stereo Width] SKIPPED expansion due to high peak ({peak_db:.2f} dB)")
                return audio  # Return unmodified

        # Apply stereo width only if the requested change is meaningful, i.e.
        # the width factor is far enough from unity to be worth the filtering.
        if abs(target_width - WIDTH_FACTOR_UNITY) > 0.1:
            # Multiband so sub-300 Hz stays (near-)mono (#4504).
            audio = adjust_stereo_width_multiband(audio, target_width, sample_rate)
            new_peak_db = StereoWidthProcessor.get_peak_db(audio)
            debug(f"[Stereo Width] Peak: {peak_db:.2f} → {new_peak_db:.2f} dB "
                  f"(width factor: {target_width:.2f}, decorrelation was {current_width:.2f})")

        return audio
