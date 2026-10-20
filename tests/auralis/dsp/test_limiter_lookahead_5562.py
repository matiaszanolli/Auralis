"""Regression tests: BrickWallLimiter look-ahead direction (#5562)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`maximum_filter1d`'s origin convention is the opposite of what the code
assumed: positive origin produced a POST-peak hold (max over
[i-lookahead+1, i]), so with instant attack the gain dropped from 1.0 to
threshold/peak in a single sample AT the peak — a broadband click — and the
documented ramped look-ahead never happened (#3308's "fix" flipped the sign
into the same backward window).

With the corrected negative origin, the gain must start reducing
`lookahead` samples BEFORE the peak and hold through it.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.brick_wall_limiter import create_brick_wall_limiter


@pytest.fixture
def limiter():
    return create_brick_wall_limiter(
        threshold_db=-0.3, lookahead_ms=2.0, release_ms=50.0, sample_rate=44100
    )


def _floor_signal_with_spike(spike_at: int, length: int = 44100) -> np.ndarray:
    audio = np.full((length, 2), 0.5, dtype=np.float32)
    audio[spike_at, :] = 1.5
    return audio


class TestLookaheadDirection:
    def test_gain_reduces_before_the_peak(self, limiter):
        """The look-ahead must pre-reduce: gain < 1 for the lookahead window
        before the spike, not just at/after it."""
        spike = 10000
        audio = _floor_signal_with_spike(spike)
        out = limiter.process(audio)
        gain = out[:, 0] / 0.5

        lookahead_samples = limiter.lookahead_samples
        pre_window = gain[spike - lookahead_samples:spike]
        # The -(lookahead//2) origin centres the ramp one sample inside the
        # full window, so ~lookahead-1 of the pre-spike samples are reduced.
        reduced = int((pre_window < 0.999).sum())
        assert reduced >= lookahead_samples - 2, (
            f"only {reduced}/{lookahead_samples} pre-spike samples reduced — "
            "the lookahead window is looking backward (post-peak hold)"
        )

    def test_gain_steps_down_before_not_after_the_peak(self, limiter):
        """The OLD behaviour: gain 1.0 at spike-1, 0.644 at the spike (a hard
        step). The fixed window reverses that ordering."""
        spike = 10000
        audio = _floor_signal_with_spike(spike)
        out = limiter.process(audio)
        gain = out[:, 0] / 0.5

        assert gain[spike - 1] < 0.9, "no pre-reduction at spike-1"
        # After the peak the envelope holds the reduced gain (release is
        # 50 ms; the first few samples after the spike stay reduced).
        assert gain[spike + 1] < 0.9

    def test_peak_is_capped_at_the_ceiling(self, limiter):
        spike = 10000
        audio = _floor_signal_with_spike(spike)
        out = limiter.process(audio)

        # The spike sample must not exceed the -0.3 dBFS ceiling (0.9661).
        assert float(np.max(np.abs(out))) <= 0.9661 + 1e-3
