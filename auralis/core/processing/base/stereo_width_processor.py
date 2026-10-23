"""
Stereo Width Processor
~~~~~~~~~~~~~~~~~~~~~~

Unified stereo width processing with safety checks. Both modes'
``_apply_stereo_width`` stage methods call :meth:`StereoWidthProcessor.apply_stereo_width_safe`
— the single implementation carrying the #5108 smooth-gate clipping knee
(#6192).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np

from ....dsp.utils.stereo import WIDTH_FACTOR_UNITY, adjust_stereo_width_multiband
from ....utils.logging import debug
from ..continuous_guards import WIDTH_PEAK_KNEE_END, WIDTH_PEAK_KNEE_START
from .db_conversion import DBConversion


class StereoWidthProcessor:
    """
    Unified stereo width processing with safety checks.
    The one stereo-width implementation shared by adaptive and continuous modes.
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
    ) -> np.ndarray:
        """
        Apply stereo width adjustment with the shared clipping guard.

        Widening is eased toward unity across a ``smooth_gate`` knee (#5108)
        as the pre-adjustment peak approaches clipping, instead of switching
        off: two masters 0.01 dB apart straddling the knee used to receive
        either full widening or none — an audible stereo-image difference from
        an inaudible input difference, in a peak region the pipeline's own
        -0.3 dBFS ceiling makes common. Only widening is gated; a narrowing
        request cannot push peaks up, so it passes through untouched.

        The two hard strategies this helper used to carry are gone with the
        consolidation (#6192): the "adaptive" clamp fired on ``peak_db > 3.0``,
        unreachable for normalised float audio, and "conservative" had no
        caller. The old ``abs(target_width - unity) > 0.1`` dead-zone is gone
        too — a second hard step (0.11 side gain at the boundary) of exactly
        the class #5108 removed;
        :func:`adjust_stereo_width_multiband` keeps its own 0.01 no-op cutoff,
        three orders of magnitude below a just-noticeable level difference.

        Args:
            audio: Input audio array (must be stereo)
            current_width: Measured DECORRELATION of the input (0 = mono). Kept
                for logging/diagnostics only — see the scale note below.
            target_width: Target WIDTH FACTOR (side-gain axis, 0.5 = unchanged)
            peak_db: Pre-adjustment peak in dB — the quantity the knee gates on
            sample_rate: Sample rate, for the multiband crossovers. Required
                (#4622) — passed straight through to
                adjust_stereo_width_multiband(), where a missing/wrong value
                silently mis-places every frequency band.

        Returns:
            Audio with adjusted stereo width (sample count preserved)

        Scales (#4503): ``current_width`` and ``target_width`` are NOT on the
        same axis — the first is a measurement (decorrelation), the second an
        instruction (side gain). Both sit in 0..1 with 0.5 near the middle,
        which is why the old ``target_width > current_width`` and
        ``abs(current_width - target_width)`` tests looked plausible and were
        meaningless. Every decision below is made against
        :data:`WIDTH_FACTOR_UNITY`, the point at which a width factor leaves the
        signal untouched.
        """
        if target_width > WIDTH_FACTOR_UNITY:
            # Deferred import: cross_dimensional_guard imports stage_snapshot,
            # which imports this package — module-level would cycle.
            from ..cross_dimensional_guard import smooth_gate

            # gate: 0 well below the knee (widen fully), 1 at/above it (unity).
            gate = smooth_gate(
                peak_db, WIDTH_PEAK_KNEE_START, WIDTH_PEAK_KNEE_END
            )
            target_width = target_width + (WIDTH_FACTOR_UNITY - target_width) * gate
            if gate > 0.0:
                debug(
                    f"[Stereo Width] peak {peak_db:.2f} dB — widening eased "
                    f"toward unity (gate={gate:.2f}, target={target_width:.3f})"
                )

        # Multiband so sub-300 Hz stays (near-)mono (#4504). Within 0.01 of
        # unity adjust_stereo_width_multiband short-circuits to a copy, so
        # near-unity requests stay cheap without a coarser gate here.
        audio = adjust_stereo_width_multiband(audio, target_width, sample_rate)
        new_peak_db = StereoWidthProcessor.get_peak_db(audio)
        debug(f"[Stereo Width] Peak: {peak_db:.2f} → {new_peak_db:.2f} dB "
              f"(width factor: {target_width:.2f}, decorrelation was {current_width:.2f})")

        return audio
