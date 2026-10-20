"""Regression tests: WOLA overlap-add restores output sample 0 (#5575)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`_process_with_psychoacoustic_eq` accumulates a Hann-windowed overlap-add
and divides by the accumulated window weight. A symmetric Hann's first
sample is exactly 0.0, and output sample 0 is covered only by frame 0 at
window position 0 — so weight and numerator were both 0 there and the eps
divide returned 0 instead of the signal (the #4852 fade-in fix recovered
samples 1..hop but not sample 0). Zero-coverage samples are now restored
from frame 0's unwindowed EQ output.
"""

import numpy as np
import pytest

from auralis.core.processing.eq_processor import EQProcessor
from auralis.dsp.eq.psychoacoustic_eq import EQSettings, PsychoacousticEQ


@pytest.fixture
def processor() -> EQProcessor:
    settings = EQSettings(sample_rate=44100, fft_size=2048, adaptation_speed=0.5)
    return EQProcessor(PsychoacousticEQ(settings))


def _flat_curve() -> dict[str, float]:
    return {
        'sub_bass': 1.0, 'bass': 1.0, 'low_mid': 1.0, 'mid': 1.0,
        'high_mid': 1.0, 'presence': 1.0, 'brilliance': 1.0,
    }


class TestWolaSampleZero:
    def test_constant_input_returns_constant_at_sample_zero(self, processor):
        """The audit probe: constant 0.3 with a flat EQ must come back 0.3 at
        index 0 — not the 0.0 the eps-divide produced."""
        chunk_size = 4096
        audio = np.full((chunk_size * 3, 2), 0.3, dtype=np.float32)

        out = processor._process_with_psychoacoustic_eq(
            audio, _flat_curve(), content_profile=None
        )

        assert out.shape == audio.shape
        assert out.dtype == audio.dtype
        # Interior was already correct (#4852); sample 0 is the fix.
        assert out[0, 0] == pytest.approx(0.3, abs=1e-3)
        assert out[0, 1] == pytest.approx(0.3, abs=1e-3)
        np.testing.assert_allclose(out[10:100], 0.3, atol=1e-3)

    def test_mono_variant_also_restored(self, processor):
        audio = np.full(chunk_size := 4096, 0.3, dtype=np.float32)

        out = processor._process_with_psychoacoustic_eq(
            audio, _flat_curve(), content_profile=None
        )

        assert out[0] == pytest.approx(0.3, abs=1e-3)
        assert out.shape == audio.shape

    def test_signal_starting_at_nonzero_is_preserved(self, processor):
        """A track that starts abruptly at a non-zero level keeps its first
        sample (within EQ tolerance) instead of a 1-sample dropout."""
        chunk_size = 4096
        audio = np.full((chunk_size * 2, 2), 0.25, dtype=np.float32)
        audio[0, :] = 0.25

        out = processor._process_with_psychoacoustic_eq(
            audio, _flat_curve(), content_profile=None
        )

        assert abs(float(out[0, 0])) > 0.1
