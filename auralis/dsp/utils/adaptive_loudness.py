# -*- coding: utf-8 -*-

"""
Adaptive Loudness Control
~~~~~~~~~~~~~~~~~~~~~~~~~~

LUFS-based adaptive gain and peak target calculation.

Prevents over-loudness by adapting makeup gain and normalization targets
based on source loudness characteristics.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Tuple
import numpy as np


class AdaptiveLoudnessControl:
    """
    LUFS-based adaptive loudness control.

    Automatically adjusts makeup gain and target peak normalization
    based on source loudness to prevent over-loud masters.
    """

    # Target loudness for masters (LUFS)
    TARGET_LUFS = -11.0

    # LUFS thresholds for adaptive behavior
    VERY_LOUD_THRESHOLD = -12.0  # Already very loud
    MODERATELY_LOUD_THRESHOLD = -14.0  # Moderately loud

    @staticmethod
    def calculate_adaptive_gain(source_lufs: float, intensity: float = 1.0) -> Tuple[float, str]:
        """
        Calculate adaptive makeup gain based on source LUFS.

        Args:
            source_lufs: Source loudness in LUFS
            intensity: Processing intensity (0.0-1.0)

        Returns:
            Tuple of (makeup_gain_db, reasoning_note)
        """
        if source_lufs > AdaptiveLoudnessControl.VERY_LOUD_THRESHOLD:
            # Already very loud - no makeup gain
            return (
                0.0,
                f"Already loud ({source_lufs:.1f} LUFS): no makeup gain"
            )

        elif source_lufs > AdaptiveLoudnessControl.MODERATELY_LOUD_THRESHOLD:
            # Moderately loud - gentle boost (50% of target difference)
            gain = (AdaptiveLoudnessControl.TARGET_LUFS - source_lufs) * 0.5
            return (
                gain,
                f"Moderately loud: gentle {gain:.1f} dB boost"
            )

        else:
            # Quiet source - full boost to target
            gain = (AdaptiveLoudnessControl.TARGET_LUFS - source_lufs) * intensity
            # Clamp to reasonable range
            gain = max(0.0, min(gain, 6.0))
            return (
                gain,
                f"Quiet source: {gain:.1f} dB boost to target"
            )

    @staticmethod
    def calculate_adaptive_peak_target(source_lufs: float) -> Tuple[float, float]:
        """
        Calculate adaptive peak normalization target based on source LUFS.

        Louder sources get lower peak targets to avoid clipping and over-compression.

        Args:
            source_lufs: Source loudness in LUFS

        Returns:
            Tuple of (target_peak_linear, target_peak_db)
        """
        if source_lufs > AdaptiveLoudnessControl.VERY_LOUD_THRESHOLD:
            # Already very loud - conservative peak target
            target_peak = 0.85
            target_peak_db = 20 * np.log10(target_peak)
            return target_peak, target_peak_db

        elif source_lufs > AdaptiveLoudnessControl.MODERATELY_LOUD_THRESHOLD:
            # Moderately loud - moderate peak target
            target_peak = 0.88
            target_peak_db = 20 * np.log10(target_peak)
            return target_peak, target_peak_db

        else:
            # Quiet source - can go a bit higher
            target_peak = 0.90
            target_peak_db = 20 * np.log10(target_peak)
            return target_peak, target_peak_db

    @staticmethod
    def should_apply_makeup_gain(
        source_lufs: float,
        current_rms_db: float,
        rms_diff_from_target: float
    ) -> Tuple[bool, float, str]:
        """
        Determine if makeup gain should be applied based on source characteristics.

        Args:
            source_lufs: Source loudness in LUFS
            current_rms_db: Current RMS level in dB
            rms_diff_from_target: Difference from target RMS in dB

        Returns:
            Tuple of (should_apply, gain_amount, reasoning)
        """
        # Use LUFS-based adaptive gain instead of RMS-based threshold
        makeup_gain, reasoning = AdaptiveLoudnessControl.calculate_adaptive_gain(source_lufs)

        if makeup_gain > 0.5:
            return True, makeup_gain, reasoning
        else:
            return False, 0.0, reasoning

    @staticmethod
    def get_adaptive_processing_params(source_lufs: float, intensity: float = 1.0) -> dict:
        """
        Get complete adaptive processing parameters based on source LUFS.

        Args:
            source_lufs: Source loudness in LUFS
            intensity: Processing intensity (0.0-1.0)

        Returns:
            Dictionary with adaptive parameters
        """
        makeup_gain, gain_reasoning = AdaptiveLoudnessControl.calculate_adaptive_gain(
            source_lufs, intensity
        )
        target_peak, target_peak_db = AdaptiveLoudnessControl.calculate_adaptive_peak_target(
            source_lufs
        )

        return {
            'makeup_gain_db': makeup_gain,
            'target_peak_linear': target_peak,
            'target_peak_db': target_peak_db,
            'source_lufs': source_lufs,
            'reasoning': gain_reasoning,
            'intensity': intensity,
        }
