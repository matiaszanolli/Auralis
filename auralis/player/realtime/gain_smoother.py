# -*- coding: utf-8 -*-

"""
Adaptive Gain Smoother
~~~~~~~~~~~~~~~~~~~~~~

Advanced gain smoothing to prevent audio artifacts

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


class AdaptiveGainSmoother:
    """Advanced gain smoothing to prevent audio artifacts"""

    def __init__(self, attack_alpha: float = 0.01, release_alpha: float = 0.001):
        self.attack_alpha = attack_alpha    # How fast to increase gain
        self.release_alpha = release_alpha  # How fast to decrease gain
        self.current_gain = 1.0
        self.target_gain = 1.0

    def set_target(self, target: float):
        """Set target gain"""
        self.target_gain = max(0.0, min(10.0, target))  # Clamp to reasonable range

    def process(self, num_samples: int) -> float:
        """Get smoothed gain for current chunk"""
        if abs(self.current_gain - self.target_gain) < 1e-6:
            return self.current_gain

        # Use different smoothing rates for attack vs release
        if self.target_gain > self.current_gain:
            alpha = self.attack_alpha  # Faster attack
        else:
            alpha = self.release_alpha  # Slower release

        # Exponential smoothing
        self.current_gain += (self.target_gain - self.current_gain) * alpha

        return self.current_gain
