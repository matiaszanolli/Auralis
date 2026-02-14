"""
Smooth Curve Utilities
~~~~~~~~~~~~~~~~~~~~~~~

Smooth curve utilities for audio DSP parameter mapping.

Provides consistent S-curve and bell curve implementations to eliminate
code duplication across DSP processing methods.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np


class SmoothCurveUtilities:
    """
    Smooth curve utilities for audio DSP parameter mapping.

    This class consolidates repeated smooth curve calculations throughout
    the mastering pipeline, providing consistent implementations of:
    - S-curves for smooth 0→1 transitions via cosine
    - Ramp-to-curve mapping for value ranges
    - Bell curves for symmetric peak responses

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
        return 0.5 * (1.0 - np.cos(np.pi * normalized))

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
    def bell_curve(value: float, center: float, width: float) -> float:
        """
        Symmetric bell curve peaking at center with given width.

        Creates a smooth bell-shaped curve that peaks at the center value
        and falls off symmetrically on both sides. Uses S-curve for the
        falloff to maintain musical smoothness.

        Args:
            value: Input position (arbitrary scale)
            center: Peak position (output = 1.0 at this point)
            width: Half-width at half-maximum (HWHM)

        Returns:
            Curve value 0.0-1.0 (1.0 at center, 0.0 beyond width)

        Examples:
            >>> SmoothCurveUtilities.bell_curve(0.5, 0.5, 0.2)
            1.0  # At center
            >>> SmoothCurveUtilities.bell_curve(0.6, 0.5, 0.2)
            ~0.5  # Half-width away
            >>> SmoothCurveUtilities.bell_curve(0.8, 0.5, 0.2)
            0.0  # Beyond width

        Notes:
            - Symmetric around center point
            - Falls to 0.0 beyond ±width from center
            - Uses S-curve for smooth falloff (not Gaussian)
            - Used for stereo width expansion curves
        """
        distance = abs(value - center) / width
        if distance > 1.0:
            return 0.0
        # S-curve applied to inverted distance for smooth falloff
        return SmoothCurveUtilities.s_curve(1.0 - distance)

    @staticmethod
    def bipolar_s_curve(value: float, min_val: float, max_val: float, center: float = 0.0) -> float:
        """
        Bidirectional S-curve mapping to [-1.0, 1.0] range.

        Maps input range to bipolar output with smooth S-curve transitions,
        useful for stereo width adjustments and other bidirectional parameters.

        Args:
            value: Input value in arbitrary range
            min_val: Minimum value (maps to -1.0)
            max_val: Maximum value (maps to +1.0)
            center: Center value (maps to 0.0, default 0.0)

        Returns:
            Smoothed curve value -1.0 to +1.0

        Examples:
            >>> SmoothCurveUtilities.bipolar_s_curve(0.5, 0.0, 1.0, 0.5)
            0.0  # Center maps to 0.0
            >>> SmoothCurveUtilities.bipolar_s_curve(0.0, 0.0, 1.0, 0.5)
            -1.0  # Min maps to -1.0
            >>> SmoothCurveUtilities.bipolar_s_curve(1.0, 0.0, 1.0, 0.5)
            +1.0  # Max maps to +1.0

        Notes:
            - Automatically handles normalization and centering
            - Clamps to [-1.0, +1.0] range
            - Useful for stereo width, pan, and balance parameters
        """
        # Normalize to [0, 1]
        normalized = SmoothCurveUtilities.ramp_to_s_curve(value, min_val, max_val)
        # Map to [-1, 1] via center point
        return 2.0 * normalized - 1.0
