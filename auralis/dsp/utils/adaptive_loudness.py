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
    def calculate_adaptive_gain(
        source_lufs: float,
        intensity: float = 1.0,
        crest_factor_db: float = None,
        bass_pct: float = None,
        transient_density: float = None
    ) -> Tuple[float, str]:
        """
        Calculate adaptive makeup gain based on source LUFS, dynamic range, bass content, and transients.

        Args:
            source_lufs: Source loudness in LUFS
            intensity: Processing intensity (0.0-1.0)
            crest_factor_db: Peak-to-RMS ratio in dB (optional, for transient preservation)
            bass_pct: Bass energy percentage 0.0-1.0 (optional, for bass-heavy material)
            transient_density: Transient density 0.0-1.0 (optional, for bass-transient interaction)

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

            # Adaptive max gain clamp based on dynamic range
            # High crest factor = transient-heavy material needs more headroom
            if crest_factor_db is not None and crest_factor_db > 15.0:
                # Very dynamic material (e.g., 1980s recordings with powerful drums)
                # Reduce max gain to preserve transient impact
                max_gain = 4.0  # Conservative for high-dynamic-range material
                reasoning_suffix = f" (crest {crest_factor_db:.1f} dB: transient preservation)"
            elif crest_factor_db is not None and crest_factor_db > 12.0:
                # Moderately dynamic material
                max_gain = 5.0
                reasoning_suffix = f" (crest {crest_factor_db:.1f} dB: moderate preservation)"
            else:
                # Low dynamic range or no crest info - standard clamp
                max_gain = 6.0
                reasoning_suffix = ""

            # Clamp to adaptive range
            gain = max(0.0, min(gain, max_gain))

            # Bass-transient interaction reduction to prevent bass-kick overdrive
            # CRITICAL: Only reduce gain for loud/moderate material
            # Quiet material needs maximum gain, not reduction
            if source_lufs < -13.0:  # Quiet material - needs boost, not reduction
                # Skip bass reduction for quiet material
                pass
            elif bass_pct is not None and transient_density is not None:
                if bass_pct > 0.15 and transient_density > 0.35:  # Lowered thresholds
                    # Bass-transient interaction: multiplicative reduction
                    # High bass + high transients = aggressive reduction
                    # But reduce the factor by 30% for quieter material
                    loudness_factor = max(0.5, min(1.0, (source_lufs + 12) / 6))  # 0.5-1.0 scaling
                    interaction_factor = bass_pct * transient_density * 6.0 * loudness_factor
                    bass_reduction = interaction_factor
                    gain = max(0.0, gain - bass_reduction)
                    reasoning_suffix += f" (bass {bass_pct:.1%} × transients {transient_density:.2f}: -{bass_reduction:.1f} dB)"
                elif bass_pct > 0.25:  # Only reduce for heavy bass
                    # Bass-only reduction (low transients) - but gentler for quiet material
                    base_reduction = (bass_pct - 0.25) * 1.5  # Reduced from 2.84 to 1.5
                    loudness_factor = max(0.0, min(1.0, (source_lufs + 12) / 6))
                    bass_reduction = base_reduction * loudness_factor
                    gain = max(0.0, gain - bass_reduction)
                    reasoning_suffix += f" (bass {bass_pct:.1%}: -{bass_reduction:.1f} dB)"
            elif bass_pct is not None and bass_pct > 0.25:
                # Fallback: bass-only reduction if no transient data - only for non-quiet
                if source_lufs >= -13.0:
                    base_reduction = (bass_pct - 0.25) * 1.5
                    loudness_factor = max(0.0, min(1.0, (source_lufs + 12) / 6))
                    bass_reduction = base_reduction * loudness_factor
                    gain = max(0.0, gain - bass_reduction)
                    reasoning_suffix += f" (bass {bass_pct:.1%}: -{bass_reduction:.1f} dB)"

            return (
                gain,
                f"Quiet source: {gain:.1f} dB boost to target{reasoning_suffix}"
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
    def get_adaptive_processing_params(
        source_lufs: float,
        intensity: float = 1.0,
        crest_factor_db: float = None,
        bass_pct: float = None,
        transient_density: float = None
    ) -> dict:
        """
        Get complete adaptive processing parameters based on source LUFS, dynamics, bass, and transients.

        Args:
            source_lufs: Source loudness in LUFS
            intensity: Processing intensity (0.0-1.0)
            crest_factor_db: Peak-to-RMS ratio in dB (optional, for transient preservation)
            bass_pct: Bass energy percentage 0.0-1.0 (optional, for bass-heavy material)
            transient_density: Transient density 0.0-1.0 (optional, for bass-transient interaction)

        Returns:
            Dictionary with adaptive parameters
        """
        makeup_gain, gain_reasoning = AdaptiveLoudnessControl.calculate_adaptive_gain(
            source_lufs, intensity, crest_factor_db, bass_pct, transient_density
        )
        target_peak, target_peak_db = AdaptiveLoudnessControl.calculate_adaptive_peak_target(
            source_lufs
        )

        return {
            'makeup_gain_db': makeup_gain,
            'target_peak_linear': target_peak,
            'target_peak_db': target_peak_db,
            'source_lufs': source_lufs,
            'crest_factor_db': crest_factor_db,
            'bass_pct': bass_pct,
            'transient_density': transient_density,
            'reasoning': gain_reasoning,
            'intensity': intensity,
        }
