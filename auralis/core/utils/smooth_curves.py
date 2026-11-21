"""
Smooth Curve Utilities
~~~~~~~~~~~~~~~~~~~~~~~

Smooth curve utilities for audio DSP parameter mapping.

Provides consistent S-curve and bell curve implementations to eliminate
code duplication across DSP processing methods.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import math

import numpy as np

# Corpus calibration of the continuous space: robust center and scale of crest factor (dB) and
# integrated loudness (LUFS) over a deterministic 512-track sample (July 2026). One home, so a
# re-calibration moves the continuous mapper, AdaptiveMode and the offline chunk path together (#6596).
CREST_CENTER_DB = 13.4207
CREST_SCALE_DB = 1.7884
LUFS_CENTER = -14.3887
LUFS_SCALE = 2.7732


def smooth_unit(value: float, center: float, scale: float) -> float:
    """Map an unbounded measurement smoothly into the open interval ``(0, 1)``.

    ``0.5 + 0.5 * tanh((value - center) / (2 * scale))``, the one logistic S-curve the mastering
    stages share (#6596); a curve written as ``tanh((x - c) / width)`` is ``smooth_unit(x, c, width / 2)``.

    NaN maps to the neutral midpoint: ``tanh(nan)`` is ``nan``, and one NaN
    coordinate makes every generated parameter NaN (#5505). ±Inf saturates to
    the interval's ends, exactly like a large-but-finite input already does
    through ``tanh`` — collapsing Inf to the midpoint conflated "undefined"
    with "extreme" (#5534).
    """
    value = float(value)
    if math.isnan(value):
        return 0.5
    if value == math.inf:
        return 1.0
    if value == -math.inf:
        return 0.0
    return 0.5 + 0.5 * math.tanh((value - center) / (2.0 * scale))


class SmoothCurveUtilities:
    """
    Smooth curve utilities for audio DSP parameter mapping.

    This class consolidates repeated smooth curve calculations throughout
    the mastering pipeline, providing consistent implementations of:
    - S-curves for smooth 0→1 transitions via cosine
    - Ramp-to-curve mapping for value ranges

    All methods are stateless static methods for easy reuse.
    """

    @staticmethod
    def s_curve(normalized: float) -> float:
        """
        S-curve (0→1 smoothly via cosine).

        Applies a smooth transition curve that accelerates from 0 and
        decelerates toward 1, avoiding abrupt changes. This creates
        more musical parameter transitions compared to linear ramps.

        Args:
            normalized: Input value 0.0-1.0

        Returns:
            Smoothed value 0.0-1.0

        Formula:
            0.5 * (1.0 - cos(π * x))

        Examples:
            >>> SmoothCurveUtilities.s_curve(0.0)
            0.0
            >>> SmoothCurveUtilities.s_curve(0.5)
            0.5
            >>> SmoothCurveUtilities.s_curve(1.0)
            1.0

        Notes:
            - Input outside [0.0, 1.0] is NOT clamped automatically
            - Use ramp_to_s_curve() if you need automatic clamping
            - This is the core smoothing function used throughout mastering
        """
        return float(0.5 * (1.0 - np.cos(np.pi * normalized)))

    @staticmethod
    def ramp_to_s_curve(value: float, min_val: float, max_val: float) -> float:
        """
        Map value from [min_val, max_val] range to smooth S-curve 0-1.

        Combines linear normalization with S-curve smoothing for natural
        parameter transitions. Automatically clamps to [0.0, 1.0] to prevent
        overruns from out-of-range input values.

        Steps:
            1. Normalize to 0-1: (value - min) / (max - min)
            2. Clamp to [0.0, 1.0] to handle edge cases
            3. Apply S-curve smoothing

        Args:
            value: Input value in arbitrary range
            min_val: Minimum value (maps to 0.0)
            max_val: Maximum value (maps to 1.0)

        Returns:
            Smoothed curve value 0.0-1.0

        Examples:
            >>> SmoothCurveUtilities.ramp_to_s_curve(-14.0, -16.0, -12.0)
            0.5  # Mid-range maps to 0.5
            >>> SmoothCurveUtilities.ramp_to_s_curve(-16.0, -16.0, -12.0)
            0.0  # Min value maps to 0.0
            >>> SmoothCurveUtilities.ramp_to_s_curve(-12.0, -16.0, -12.0)
            1.0  # Max value maps to 1.0
            >>> SmoothCurveUtilities.ramp_to_s_curve(-20.0, -16.0, -12.0)
            0.0  # Out-of-range clamped to 0.0

        Notes:
            - Handles divide-by-zero if min_val == max_val (returns 0.0)
            - Automatically clamps to prevent values < 0.0 or > 1.0
            - Used for LUFS, crest factor, and frequency percentage mappings
        """
        if max_val == min_val:
            # Prevent divide by zero - return floor value
            return 0.0

        normalized = (value - min_val) / (max_val - min_val)
        normalized = np.clip(normalized, 0.0, 1.0)
        return SmoothCurveUtilities.s_curve(normalized)

    @staticmethod
    def vocal_mask_factor(
        bass_pct: float, mid_pct: float, upper_mid_pct: float,
        ratio_low: float, ratio_range: float,
    ) -> float:
        """Severity (0-1) of a vocal buried under a dominant bass.

        Uses the bass-to-voice energy ratio ``bass_pct / (mid_pct +
        upper_mid_pct)``: well-mastered records sit near 2.0, while a buried
        vocal (e.g. Patricio Rey's Gulp at bass 60% / voice 9%) runs 5-9. Ramps
        from 0 at ``ratio_low`` to 1 at ``ratio_low + ratio_range`` via the
        shared S-curve, so balanced bass-heavy genres stay untouched.

        Shared by the clarity-boost (presence lift) and bass-balance (mud cut)
        stages so both sides of the unmasking move key off one definition.

        Args:
            bass_pct: Fingerprint bass percentage (0-1).
            mid_pct: Fingerprint mid percentage (0-1).
            upper_mid_pct: Fingerprint upper-mid percentage (0-1).
            ratio_low: Bass/voice ratio at which unmasking begins (→ 0.0).
            ratio_range: Span above ratio_low mapping to full severity (→ 1.0).

        Returns:
            Masking severity 0.0-1.0 (0.0 when voice energy is negligible).
        """
        voice_pct = mid_pct + upper_mid_pct
        if voice_pct <= 1e-3:
            return 0.0
        mask_ratio = bass_pct / voice_pct
        return SmoothCurveUtilities.ramp_to_s_curve(
            max(0.0, mask_ratio - ratio_low), 0.0, ratio_range
        )

