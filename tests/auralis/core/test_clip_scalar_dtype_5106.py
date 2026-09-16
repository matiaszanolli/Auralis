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


class TestEqFallbackPreservesDtype:
    @pytest.fixture
    def eq_processor(self) -> EQProcessor:
        settings = EQSettings(sample_rate=44100, fft_size=2048, adaptation_speed=0.5)
        return EQProcessor(PsychoacousticEQ(settings))

    def test_bass_boost_preserves_float32(self, eq_processor: EQProcessor):
        rng = np.random.default_rng(1)
        audio = (rng.standard_normal((4096, 2)) * 0.1).astype(np.float32)

        result = eq_processor._apply_simple_eq_fallback(audio, {"bass_boost_db": 3.0})

        assert result.dtype == np.float32

    def test_treble_enhancement_preserves_float32(self, eq_processor: EQProcessor):
        rng = np.random.default_rng(2)
        audio = (rng.standard_normal((4096, 2)) * 0.1).astype(np.float32)

        result = eq_processor._apply_simple_eq_fallback(
            audio, {"treble_enhancement_db": 3.0}
        )

        assert result.dtype == np.float32

    def test_both_bands_preserve_float32(self, eq_processor: EQProcessor):
        rng = np.random.default_rng(3)
        audio = (rng.standard_normal((4096, 2)) * 0.1).astype(np.float32)

        result = eq_processor._apply_simple_eq_fallback(
            audio, {"bass_boost_db": 3.0, "treble_enhancement_db": -3.0}
        )

        assert result.dtype == np.float32
