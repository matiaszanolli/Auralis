"""Regression tests: no 0.5 dB dead-band in chunk loudness normalization (#5578)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_normalize_chunk_loudness` applied the LUFS correction only when
`abs(adjustment) > 0.5` — a 0.49 dB error applied nothing, 0.51 dB applied in
full, so near-target material got an unprincipled ±0.5 dB level and adjacent
chunks straddling the threshold got 0.5 dB steps. The correction is now
ramped through `smooth_gate` (#4860's continuous-parameter rule).
"""

import numpy as np
import pytest

from auralis.core.processing.continuous_dsp_ops import ContinuousDSPOpsMixin
from auralis.dsp.utils.adaptive import calculate_loudness_units


def _tone(dbfs: float, seconds: float = 3.0, sr: int = 44100) -> np.ndarray:
    t = np.arange(int(sr * seconds)) / sr
    amp = 10 ** (dbfs / 20)
    return np.column_stack([amp * np.sin(2 * np.pi * 997 * t)] * 2).astype(np.float32)


class _Cfg:
    internal_sample_rate = 44100


@pytest.fixture
def ops() -> ContinuousDSPOpsMixin:
    # _normalize_chunk_loudness only reads self.config.internal_sample_rate.
    ops = ContinuousDSPOpsMixin.__new__(ContinuousDSPOpsMixin)
    ops.config = _Cfg()
    return ops


class TestNormalizeChunkLoudnessRamp:
    def test_049_and_051_gain_within_0_1_db(self, ops):
        """Adjustments of 0.49 and 0.51 dB must produce nearly the same
        applied gain — the old hard gate made them differ by ~0.5 dB."""
        audio = _tone(-20.0)
        current = calculate_loudness_units(audio, 44100)

        out_049 = ops._normalize_chunk_loudness(audio.copy(), current + 0.49)
        out_051 = ops._normalize_chunk_loudness(audio.copy(), current + 0.51)

        gain_049 = 20 * np.log10(np.max(np.abs(out_049)) / np.max(np.abs(audio)))
        gain_051 = 20 * np.log10(np.max(np.abs(out_051)) / np.max(np.abs(audio)))
        assert abs(gain_051 - gain_049) < 0.1

    def test_zero_adjustment_returns_input_unchanged(self, ops):
        audio = _tone(-20.0)
        current = calculate_loudness_units(audio, 44100)

        out = ops._normalize_chunk_loudness(audio.copy(), current)

        np.testing.assert_array_equal(out, audio)

    def test_silence_stays_silent(self, ops):
        silence = np.zeros((44100, 2), dtype=np.float32)
        out = ops._normalize_chunk_loudness(silence.copy(), -10.0)
        np.testing.assert_array_equal(out, silence)

    def test_large_adjustment_still_applies_in_full(self, ops):
        """The ramp must not soften real corrections: a 6 dB error still
        applies ~6 dB."""
        audio = _tone(-26.0)
        current = calculate_loudness_units(audio, 44100)

        out = ops._normalize_chunk_loudness(audio.copy(), current + 6.0)
        gain = 20 * np.log10(np.max(np.abs(out)) / np.max(np.abs(audio)))
        assert 5.0 < gain < 6.5
