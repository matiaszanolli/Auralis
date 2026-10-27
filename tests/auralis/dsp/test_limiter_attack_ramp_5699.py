"""Regression tests: BrickWallLimiter attack is a ramp, not a step (#5699)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#5562 moved the look-ahead window in front of the peak, but the envelope still
dropped to `threshold / peak` in ONE sample (`prev_gain = tg  # attack:
instant`), a discontinuity of `delta_gain * x[n]` on every limited peak.
The reduction must now ramp in over the look-ahead and still cap every sample.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.brick_wall_limiter import create_brick_wall_limiter

SR = 44100
THRESHOLD_DB = -0.3
CEILING = 10 ** (THRESHOLD_DB / 20)
# The issue's bound for a ~-5 dB reduction; a linear ramp over 88 samples
# steps by ~0.005.
MAX_GAIN_STEP = 0.02


@pytest.fixture
def limiter():
    return create_brick_wall_limiter(SR, threshold_db=THRESHOLD_DB)


def _sine_with_spike(spike_at: int = 20000, length: int = 44100) -> np.ndarray:
    t = np.arange(length) / SR
    mono = (0.5 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    audio = np.stack([mono, mono], axis=1)
    audio[spike_at, :] = 1.8
    return audio


def _fresh():
    return create_brick_wall_limiter(SR, threshold_db=THRESHOLD_DB)


def _applied_gain(carrier: np.ndarray) -> np.ndarray:
    """Gain a fresh limiter applies per sample to a constant-level carrier."""
    out = _fresh().process(carrier)[:, 0].astype(np.float64)
    return out / carrier[:, 0].astype(np.float64)


class TestAttackIsARamp:
    def test_isolated_peak_has_no_gain_step(self, limiter):
        """The issue's probe: 0.5 sine + one 1.8 sample (a -5.4 dB reduction)."""
        carrier = np.full((44100, 2), 0.5, dtype=np.float32)
        carrier[20000, :] = 1.8
        steps = np.abs(np.diff(_applied_gain(carrier)))
        assert steps.max() < MAX_GAIN_STEP, (
            f"largest single-sample gain step {steps.max():.4f} "
            f"at index {int(steps.argmax())}"
        )

        out = limiter.process(_sine_with_spike())
        assert float(np.max(np.abs(out))) <= CEILING + 1e-6

    def test_gain_reaches_the_target_by_the_peak(self, limiter):
        carrier = np.full((44100, 2), 0.5, dtype=np.float32)
        carrier[20000, :] = 1.8
        gain = _applied_gain(carrier)

        assert gain[20000] * 1.8 <= CEILING + 1e-6
        # Ramping, not holding: well before the peak the reduction is small,
        # and it deepens monotonically toward it.
        lookahead = limiter.lookahead_samples
        ramp = gain[20000 - lookahead + 1 : 20001]
        assert ramp[0] > 0.99
        assert np.all(np.diff(ramp) <= 1e-9)

    def test_sustained_over_threshold_material_holds_the_ceiling(self, limiter):
        rng = np.random.default_rng(5699)
        burst = (rng.standard_normal((30000, 2)) * 0.6).astype(np.float32)
        audio = np.concatenate(
            [np.zeros((2000, 2), np.float32), burst, np.zeros((2000, 2), np.float32)]
        )
        out = limiter.process(audio)

        assert float(np.max(np.abs(out))) <= CEILING + 1e-6
        assert out.shape == audio.shape

    def test_burst_gain_has_no_large_steps(self):
        carrier = np.full((20000, 2), 0.4, dtype=np.float32)
        carrier[5000:5200, :] = 1.3
        carrier[9000:9010, :] = 1.6
        gain = _applied_gain(carrier)

        assert np.abs(np.diff(gain)).max() < MAX_GAIN_STEP
        assert float(np.max(gain * carrier[:, 0])) <= CEILING + 1e-6


class TestStateAndShape:
    def test_split_call_matches_single_call(self):
        audio = _sine_with_spike()
        whole = create_brick_wall_limiter(SR, threshold_db=THRESHOLD_DB).process(audio)

        split_at = 33333  # well clear of the spike's look-ahead and release
        part = create_brick_wall_limiter(SR, threshold_db=THRESHOLD_DB)
        stitched = np.concatenate(
            [part.process(audio[:split_at]), part.process(audio[split_at:])]
        )

        np.testing.assert_allclose(stitched, whole, atol=1e-6)

    def test_peak_at_start_of_a_call_is_still_capped(self, limiter):
        audio = np.full((4000, 2), 0.3, dtype=np.float32)
        audio[3, :] = 1.8
        out = limiter.process(audio)

        assert float(np.max(np.abs(out))) <= CEILING + 1e-6

    @pytest.mark.parametrize("dtype", [np.float32, np.float64])
    def test_dtype_and_length_preserved(self, limiter, dtype):
        audio = _sine_with_spike().astype(dtype)
        out = limiter.process(audio)

        assert out.dtype == dtype
        assert out.shape == audio.shape

    def test_mono_input(self, limiter):
        audio = _sine_with_spike()[:, 0].copy()
        out = limiter.process(audio)

        assert out.shape == audio.shape
        assert float(np.max(np.abs(out))) <= CEILING + 1e-6

    def test_below_threshold_audio_is_untouched(self, limiter):
        audio = _sine_with_spike()
        audio[20000, :] = 0.5
        out = limiter.process(audio)

        np.testing.assert_array_equal(out, audio)
