"""
Envelope Follower
~~~~~~~~~~~~~~~~~

One-pole attack/release envelope follower for dynamics processing.

The recursion is inherently sequential (each sample depends on the previous
envelope), so it cannot be vectorized with NumPy; `process_buffer` runs it as a
single kernel that is JIT-compiled with Numba when that is importable and runs
as plain Python otherwise. The kernel allocates its output with `zeros_like`, so
the caller's dtype is preserved (#4225, #4934).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable
from typing import Any

import numpy as np


def _follow_envelope(
    input_levels: np.ndarray,
    initial_envelope: float,
    attack_coeff: float,
    release_coeff: float,
) -> np.ndarray:
    """Run the attack/release recursion over *input_levels* from *initial_envelope*."""
    output = np.zeros_like(input_levels)
    current_env = initial_envelope

    for i in range(len(input_levels)):
        input_val = input_levels[i]
        if input_val > current_env:
            # Attack (faster)
            current_env = input_val + (current_env - input_val) * attack_coeff
        else:
            # Release (slower)
            current_env = input_val + (current_env - input_val) * release_coeff
        output[i] = current_env

    return output


_follow_kernel: Callable[..., np.ndarray]
try:
    from numba import jit

    _follow_kernel = jit(nopython=True, cache=True)(_follow_envelope)
except ImportError:
    _follow_kernel = _follow_envelope


class EnvelopeFollower:
    """Attack/release envelope follower for dynamics processing"""

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
        """Process an entire buffer of input levels, carrying state across calls."""
        if len(input_levels) == 0:
            return np.zeros_like(input_levels)

        output: Any = _follow_kernel(
            input_levels, self.envelope, self.attack_coeff, self.release_coeff
        )
        self.envelope = float(output[-1])
        return output  # type: ignore[no-any-return]

    def reset(self) -> None:
        """Reset envelope state"""
        self.envelope = 0.0
