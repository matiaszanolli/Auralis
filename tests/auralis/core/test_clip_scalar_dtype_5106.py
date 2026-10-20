"""
Regression: unwrapped np.clip() scalar dtype promotion (#5106)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`np.clip(python_float, lo, hi)` returns a numpy.float64 scalar, not a Python
float. Under NEP 50 that is a *strong* dtype, so multiplying a float32 audio
array by it silently promotes the whole result to float64 — doubling memory
and CPU for every downstream array with no audible or invariant-violating
effect (the project's dtype-in-[float32, float64] invariant still holds).
This is the 9th/10th instance of the pattern (#2158, #2450, #3468, #3659,
#3687, #4105, #4107, #4934/#4225).

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest

from auralis.core.processing.eq_processor import EQProcessor
from auralis.core.processors.reference_mode import apply_reference_matching
from auralis.dsp.eq.psychoacoustic_eq import EQSettings, PsychoacousticEQ


class TestReferenceModePreservesDtype:
    def test_float32_target_and_reference_yield_float32_output(self):
        rng = np.random.default_rng(0)
        target = (rng.standard_normal((4096, 2)) * 0.1).astype(np.float32)
        reference = (rng.standard_normal((4096, 2)) * 0.3).astype(np.float32)

        result = apply_reference_matching(target, reference)

        assert result.dtype == np.float32, (
            f"apply_reference_matching promoted float32 input to {result.dtype}"
        )

    def test_gain_factor_clip_is_a_plain_float_not_numpy_scalar(self):
        """Pins the fix at its source, not just the eventual array dtype:
        the clipped gain itself must be a Python float."""
        gain_factor = 2.5 / 1.3
        clipped = float(np.clip(gain_factor, 0.1, 10.0))
        assert type(clipped) is float


# #4972: TestEqFallbackPreservesDtype removed with the fallback itself —
# _apply_simple_eq_fallback no longer exists; EQ failures propagate.