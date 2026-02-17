"""
Adaptive Gain Smoother
~~~~~~~~~~~~~~~~~~~~~~

Advanced gain smoothing to prevent audio artifacts

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np


class AdaptiveGainSmoother:
    """Advanced gain smoothing to prevent audio artifacts"""

    def __init__(self, attack_alpha: float = 0.01, release_alpha: float = 0.001) -> None:
        self.attack_alpha = attack_alpha    # How fast to increase gain
        self.release_alpha = release_alpha  # How fast to decrease gain
        self.current_gain = 1.0
        self.target_gain = 1.0

    def set_target(self, target: float) -> None:
        """Set target gain"""
        self.target_gain = max(0.0, min(10.0, target))  # Clamp to reasonable range

    def process(self, num_samples: int) -> np.ndarray:
        """Get per-sample smoothed gain ramp for a chunk of *num_samples* samples.

        Returns a 1-D float32 array of shape ``(num_samples,)``.  Each element
        is the gain to apply to the corresponding sample, smoothly transitioning
        from ``current_gain`` toward ``target_gain`` using exponential smoothing.

        The analytical closed form of the first-order IIR recurrence
            g[n] = g[n-1] + (target - g[n-1]) * alpha
        is used so the entire ramp is computed in one vectorised operation
        instead of a per-sample Python loop:
            g[n] = target + (g[0] - target) * (1 - alpha)^n
        ``current_gain`` is advanced to the end-of-chunk value after the call.
        """
        if num_samples == 0:
            return np.empty(0, dtype=np.float32)

        if abs(self.current_gain - self.target_gain) < 1e-6:
            # Already at target — constant ramp, no state update needed
            return np.full(num_samples, self.current_gain, dtype=np.float32)

        # Different smoothing rates for attack vs release
        alpha = self.attack_alpha if self.target_gain > self.current_gain else self.release_alpha

        # Analytical solution: g[n] = target + (g[0] - target) * (1 - alpha)^n
        # n is 1-indexed: sample 0 of the output uses the update after step 1.
        n = np.arange(1, num_samples + 1, dtype=np.float64)
        gains = self.target_gain + (self.current_gain - self.target_gain) * (1.0 - alpha) ** n

        # Advance internal state to end-of-chunk value
        self.current_gain = float(gains[-1])

        return gains.astype(np.float32)
