# -*- coding: utf-8 -*-

"""
Envelope Follower
~~~~~~~~~~~~~~~~~

High-quality envelope follower for dynamics processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np


class EnvelopeFollower:
    """High-quality envelope follower for dynamics processing"""

    def __init__(self, sample_rate: int, attack_ms: float, release_ms: float):
        """
        Initialize envelope follower

        Args:
            sample_rate: Audio sample rate
            attack_ms: Attack time in milliseconds
            release_ms: Release time in milliseconds
        """
        self.sample_rate = sample_rate
        self.envelope = 0.0

        # Convert time constants to coefficients
        self.attack_coeff = np.exp(-1.0 / (attack_ms * 0.001 * sample_rate))
        self.release_coeff = np.exp(-1.0 / (release_ms * 0.001 * sample_rate))

    def process(self, input_level: float) -> float:
        """Process input level and return envelope"""
        if input_level > self.envelope:
            # Attack (faster)
            self.envelope = input_level + (self.envelope - input_level) * self.attack_coeff
        else:
            # Release (slower)
            self.envelope = input_level + (self.envelope - input_level) * self.release_coeff

        return self.envelope

    def process_buffer(self, input_levels: np.ndarray) -> np.ndarray:
        """Process entire buffer of input levels"""
        output = np.zeros_like(input_levels)

        for i, level in enumerate(input_levels):
            output[i] = self.process(level)

        return output

    def reset(self) -> None:
        """Reset envelope state"""
        self.envelope = 0.0


def create_envelope_follower(sample_rate: int, attack_ms: float,
                             release_ms: float) -> EnvelopeFollower:
    """
    Factory function to create envelope follower

    Args:
        sample_rate: Audio sample rate
        attack_ms: Attack time in milliseconds
        release_ms: Release time in milliseconds

    Returns:
        Configured EnvelopeFollower instance
    """
    return EnvelopeFollower(sample_rate, attack_ms, release_ms)
