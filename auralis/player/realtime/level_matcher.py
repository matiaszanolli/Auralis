"""
Real-time Level Matcher
~~~~~~~~~~~~~~~~~~~~~~~

Real-time RMS level matching with reference audio

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

import numpy as np

from ...utils.logging import debug, info
from ..config import PlayerConfig
from .gain_smoother import AdaptiveGainSmoother


class RealtimeLevelMatcher:
    """Real-time RMS level matching with reference audio"""

    def __init__(self, config: PlayerConfig):
        self.config = config
        self.enabled = False
        self.reference_rms: float | None = None
        self.target_rms_alpha = 0.01  # Smoothing for RMS calculation
        self.current_target_rms = 0.0

        # Gain smoothing for artifact-free transitions
        self.gain_smoother = AdaptiveGainSmoother(
            attack_alpha=0.02,   # Fairly quick attack
            release_alpha=0.005  # Slower release to avoid pumping
        )

        debug("RealtimeLevelMatcher initialized")

    def set_reference_audio(self, reference: np.ndarray | None) -> bool:
        """Set reference audio for level matching"""
        if reference is None:
            self.reference_rms = None
            self.enabled = False
            return False

        # Calculate RMS of reference audio
        self.reference_rms = np.sqrt(np.mean(reference ** 2))
        self.enabled = True
        info(f"Reference RMS set: {self.reference_rms:.6f}")
        return True

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio chunk with level matching"""
        if not self.enabled or self.reference_rms is None or self.reference_rms == 0:
            return audio

        # Calculate current RMS
        current_rms = np.sqrt(np.mean(audio ** 2))

        if current_rms == 0:
            return audio

        # Smooth the target RMS to avoid sudden changes
        target_rms = self.reference_rms
        self.current_target_rms += (target_rms - self.current_target_rms) * self.target_rms_alpha

        # Calculate gain needed
        gain = self.current_target_rms / current_rms

        # Apply gain smoothing
        self.gain_smoother.set_target(gain)
        smooth_gain = self.gain_smoother.process(len(audio))

        # Apply gain with soft limiting to prevent clipping
        processed = audio * smooth_gain

        # Soft limiter to prevent harsh clipping
        max_val = np.max(np.abs(processed))
        if max_val > 0.95:
            limiter_gain = 0.95 / max_val
            processed *= limiter_gain

        return processed

    def get_stats(self) -> dict[str, Any]:
        """Get level matching statistics"""
        return {
            'enabled': self.enabled,
            'reference_loaded': self.reference_rms is not None,
            'reference_rms': self.reference_rms or 0.0,
            'current_gain': self.gain_smoother.current_gain,
            'target_gain': self.gain_smoother.target_gain,
        }
