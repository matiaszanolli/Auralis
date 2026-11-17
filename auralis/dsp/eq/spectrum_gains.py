"""
Adaptive gain calculation for PsychoacousticEQ (split from psychoacoustic_eq.py, #5838): target
gains and the smoothing that carries gains across chunks.
"""

import threading
from typing import Any

import numpy as np

from ..utils.adaptive import smooth_parameter_transition
from .curves import apply_content_adaptation


class SpectrumGainsMixin:
    """State is created by PsychoacousticEQ.__init__."""

    sample_rate: int
    fft_size: int
    settings: Any
    critical_bands: Any
    freq_to_band_map: Any
    current_gains: np.ndarray
    _state_lock: "threading.Lock"

    def calculate_adaptive_gains(self,
                                target_curve: np.ndarray,
                                content_profile: dict[str, Any] | None = None) -> np.ndarray:
        """
        Calculate the EQ gains for a target curve: the curve times each band's perceptual weight,
        optionally adapted to the content profile, then smoothed across chunks. The frame's own
        spectrum plays no part (#5703), so none is analysed (#6306).

        Args:
            target_curve: Target frequency response curve
            content_profile: Optional content analysis for adaptation

        Returns:
            Array of gain values in dB for each critical band
        """
        # Calculate initial gains based on target curve
        target_gains = self._calculate_target_gains(target_curve)

        # Content-aware adaptation
        if content_profile:
            target_gains = apply_content_adaptation(
                target_gains,
                content_profile,
                self.critical_bands
            )

        # Smooth transitions to avoid artifacts
        adaptive_gains = self._smooth_gains(target_gains)

        return adaptive_gains

    def _calculate_target_gains(self, target_curve: np.ndarray) -> np.ndarray:
        """Calculate target gains for each band.

        ``target_curve`` contains *relative* dB gains (boost/cut) per band,
        NOT absolute magnitude levels.  The previous formula
        ``target_level - current_level`` treated them as absolute targets,
        producing nonsensical gains (e.g. 3 - 40 = -37) that were silently
        clipped to -12 dB, causing a systematic ~3 dB excess cut (#3428).

        The gain is the curve times the band's perceptual weight, independent
        of the frame's content. A former "masking" test halved it whenever a
        band's mean level sat below its own peak minus 20 dB — that measures
        tonality, not masking, and flipped the EQ amount frame to frame on
        mixed material (#5703).
        """
        target_gains = np.zeros(len(self.critical_bands))

        for i, band in enumerate(self.critical_bands):
            # target_curve values are relative dB gains (boost/cut)
            required_gain = target_curve[i] if i < len(target_curve) else 0.0

            # Apply perceptual weighting
            weighted_gain = required_gain * band.weight

            target_gains[i] = np.clip(weighted_gain, -12.0, 12.0)  # Limit gain range

        return target_gains

    def _smooth_gains(self, target_gains: np.ndarray) -> np.ndarray:
        """Smooth gain transitions to avoid artifacts (#3747: locked).

        Reads and writes `self.current_gains` — atomic under the
        state lock so concurrent callers see consistent inter-chunk
        smoothing (the prior unprotected read-modify-write would
        produce jittery band-EQ wobble under shared-instance use)."""
        with self._state_lock:
            adaptive_gains = np.zeros_like(target_gains)
            for i in range(len(target_gains)):
                adaptive_gains[i] = smooth_parameter_transition(
                    self.current_gains[i],
                    target_gains[i],
                    self.settings.adaptation_speed
                )

            # Update current gains
            self.current_gains = adaptive_gains.copy()

            return adaptive_gains
