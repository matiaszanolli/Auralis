"""
Adaptive Loudness Control
~~~~~~~~~~~~~~~~~~~~~~~~~~

LUFS-based adaptive gain and peak target calculation.

Prevents over-loudness by adapting makeup gain and normalization targets
based on source loudness characteristics.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


import numpy as np

from .loudness_targets import LOUD_MASTER_TARGET_LUFS


class AdaptiveLoudnessControl:
    """
    LUFS-based adaptive loudness control.

    Automatically adjusts makeup gain and target peak normalization
    based on source loudness to prevent over-loud masters.
    """

    # Target loudness for masters (LUFS)
    TARGET_LUFS = LOUD_MASTER_TARGET_LUFS

    # LUFS thresholds for adaptive behavior
    VERY_LOUD_THRESHOLD = -12.0  # Already very loud
    MODERATELY_LOUD_THRESHOLD = -14.0  # Moderately loud

    # Width (LU / dB) of the smoothstep knee centred on each threshold, so the
    # makeup gain eases between regimes instead of stepping (#5704).
    LOUDNESS_KNEE_LU = 0.5
    CREST_KNEE_DB = 1.0

    # Crest-factor ceilings on the makeup gain: transient-heavy material gets
    # less so its impact survives. Centred at 12 dB (6 -> 5 dB) and 15 dB (-> 4 dB).
    MAX_GAIN_DB = 6.0
    CREST_STEPS = ((12.0, 1.0), (15.0, 1.0))  # (crest centre dB, max-gain reduction dB)

    @staticmethod
    def calculate_adaptive_gain(
        source_lufs: float,
        intensity: float = 1.0,
        crest_factor_db: float | None = None,
        peak_db: float | None = None
    ) -> tuple[float, str]:
        """
        Calculate adaptive makeup gain from source LUFS, dynamic range and peak.

        Continuous in ``source_lufs``, ``crest_factor_db`` and ``peak_db`` (#5704):
        the share of the gap to ``TARGET_LUFS`` that becomes gain is 0 for
        sources above ``VERY_LOUD_THRESHOLD``, 0.5 through the moderately-loud
        band and ``intensity`` below ``MODERATELY_LOUD_THRESHOLD``, with a
        smoothstep knee at each threshold; the crest ceiling steps down the same
        way. (A bass/transient reduction used to follow, but it sat behind a
        test that was always true for the only branch that reached it, so it never
        changed a result and has been removed.)

        Args:
            source_lufs: Source loudness in LUFS
            intensity: Processing intensity (0.0-1.0)
            crest_factor_db: Peak-to-RMS ratio in dB (optional, for transient preservation)
            peak_db: Peak level in dB (optional, for headroom-aware gain limiting)

        Returns:
            Tuple of (makeup_gain_db, reasoning_note)
        """
        # Deferred: core.processing imports this package.
        from ...core.processing.cross_dimensional_guard import smooth_gate

        cls = AdaptiveLoudnessControl
        half = cls.LOUDNESS_KNEE_LU / 2
        quietness = -source_lufs
        to_moderate = smooth_gate(quietness, -cls.VERY_LOUD_THRESHOLD - half, -cls.VERY_LOUD_THRESHOLD + half)
        to_quiet = smooth_gate(
            quietness, -cls.MODERATELY_LOUD_THRESHOLD - half, -cls.MODERATELY_LOUD_THRESHOLD + half
        )
        share = 0.5 * to_moderate + (intensity - 0.5) * to_quiet
        gain = (cls.TARGET_LUFS - source_lufs) * share

        max_gain = cls.MAX_GAIN_DB
        suffix = ""
        if crest_factor_db is not None:
            for centre, reduction in cls.CREST_STEPS:
                max_gain -= reduction * smooth_gate(
                    crest_factor_db, centre - cls.CREST_KNEE_DB / 2, centre + cls.CREST_KNEE_DB / 2
                )
            if max_gain < cls.MAX_GAIN_DB:
                suffix = f" (crest {crest_factor_db:.1f} dB: max {max_gain:.1f} dB)"
        gain = max(0.0, min(gain, max_gain))

        # Peak-aware limiting: never boost past the headroom to the -1.5 dB soft
        # clipper ceiling (material that is quiet by LUFS but already near 0 dBFS).
        if peak_db is not None:
            available_headroom = -1.5 - peak_db
            if available_headroom < gain:
                old_gain, gain = gain, max(0.0, available_headroom)
                suffix += f" (peak {peak_db:.1f} dB: limited from {old_gain:.1f} to {gain:.1f} dB)"

        if source_lufs > cls.VERY_LOUD_THRESHOLD:
            return gain, f"Already loud ({source_lufs:.1f} LUFS): {gain:.1f} dB makeup gain{suffix}"
        if source_lufs > cls.MODERATELY_LOUD_THRESHOLD:
            return gain, f"Moderately loud: gentle {gain:.1f} dB boost{suffix}"
        return gain, f"Quiet source: {gain:.1f} dB boost to target{suffix}"

    @staticmethod
    def calculate_adaptive_peak_target(source_lufs: float) -> tuple[float, float]:
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
