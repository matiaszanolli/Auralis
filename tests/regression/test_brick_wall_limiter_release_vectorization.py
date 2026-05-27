"""
BrickWallLimiter Release-Envelope Vectorization Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #3751:
The per-sample release-envelope loop was replaced with a segmented vectorization
(geometric release over no-limiting runs + scalar loop only on peaks). These
tests pin the new ``_release_envelope`` to the exact scalar recurrence it
replaces, and verify the engine invariants (sample count, dtype, cross-chunk
continuity) the limiter must preserve.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.brick_wall_limiter import (
    BrickWallLimiter,
    BrickWallLimiterSettings,
    create_brick_wall_limiter,
)


def _reference_release(target_gains, rc, seed, dtype):
    """Literal scalar reference of the recurrence the vectorization replaces."""
    n = len(target_gains)
    gain = np.empty(n, dtype=dtype)
    prev = seed
    for i in range(n):
        tg = target_gains[i]
        if tg < prev:
            prev = tg  # attack: instant
        else:
            prev = prev * rc + tg * (1.0 - rc)  # release toward tg
        gain[i] = prev
    return gain


@pytest.mark.regression
class TestReleaseEnvelopeMatchesScalarReference:
    """The vectorized envelope must equal the scalar recurrence (#3751)."""

    @pytest.mark.parametrize("dtype", [np.float32, np.float64])
    @pytest.mark.parametrize(
        "pattern",
        ["all_unity", "all_limiting", "sparse_peaks", "dense_random", "alternating"],
    )
    def test_matches_reference(self, dtype, pattern):
        rng = np.random.RandomState(1234)
        n = 5000

        if pattern == "all_unity":
            target_gains = np.ones(n, dtype=dtype)
        elif pattern == "all_limiting":
            target_gains = rng.uniform(0.2, 0.95, n).astype(dtype)
        elif pattern == "sparse_peaks":
            target_gains = np.ones(n, dtype=dtype)
            idx = rng.choice(n, size=50, replace=False)
            target_gains[idx] = rng.uniform(0.3, 0.9, size=50).astype(dtype)
        elif pattern == "dense_random":
            target_gains = np.where(
                rng.rand(n) < 0.5, rng.uniform(0.3, 0.99, n), 1.0
            ).astype(dtype)
        else:  # alternating — pathological worst case for the segmenting
            target_gains = np.where(
                np.arange(n) % 2 == 0, 0.7, 1.0
            ).astype(dtype)

        limiter = create_brick_wall_limiter()
        # Capture seed BEFORE the call (the method mutates current_gain).
        seed = limiter.current_gain
        rc = limiter.release_coef

        got = limiter._release_envelope(target_gains, np.dtype(dtype))
        expected = _reference_release(target_gains, rc, seed, dtype)

        assert got.dtype == np.dtype(dtype)
        atol = 1e-6 if dtype == np.float32 else 1e-12
        np.testing.assert_allclose(got, expected, atol=atol, rtol=1e-5)
        # Final state must also match what the scalar loop would persist.
        assert limiter.current_gain == pytest.approx(float(expected[-1]), abs=atol)

    def test_chunked_equals_whole_signal(self):
        """Processing in chunks (state carried) equals one-shot (#2390 continuity)."""
        rng = np.random.RandomState(7)
        n = 6000
        target_gains = np.where(
            rng.rand(n) < 0.2, rng.uniform(0.3, 0.95, n), 1.0
        ).astype(np.float64)

        whole = create_brick_wall_limiter()._release_envelope(
            target_gains, np.dtype(np.float64)
        )

        chunked_limiter = create_brick_wall_limiter()
        pieces = []
        for sl in (slice(0, 1500), slice(1500, 4000), slice(4000, n)):
            pieces.append(
                chunked_limiter._release_envelope(target_gains[sl], np.dtype(np.float64))
            )
        chunked = np.concatenate(pieces)

        np.testing.assert_allclose(chunked, whole, atol=1e-12)


@pytest.mark.regression
class TestBrickWallLimiterInvariants:
    """End-to-end invariants the limiter must preserve (#2519, #3658, #3750)."""

    @pytest.mark.parametrize("dtype", [np.float32, np.float64])
    def test_sample_count_and_dtype_preserved_mono(self, dtype):
        limiter = create_brick_wall_limiter()
        audio = (np.random.RandomState(0).randn(44100) * 2.0).astype(dtype)
        out = limiter.process(audio)
        assert out.shape == audio.shape
        assert out.dtype == dtype

    @pytest.mark.parametrize("dtype", [np.float32, np.float64])
    def test_sample_count_and_dtype_preserved_stereo(self, dtype):
        limiter = create_brick_wall_limiter()
        audio = (np.random.RandomState(0).randn(44100, 2) * 2.0).astype(dtype)
        out = limiter.process(audio)
        assert out.shape == audio.shape
        assert out.dtype == dtype

    def test_peaks_are_limited(self):
        """A signal above the ceiling is brought down near the threshold."""
        settings = BrickWallLimiterSettings(threshold_db=-6.0)
        limiter = BrickWallLimiter(settings)
        threshold_linear = 10 ** (-6.0 / 20)
        audio = np.ones(44100, dtype=np.float64) * 0.9  # well above ceiling
        out = limiter.process(audio)
        # After the lookahead+release settles, sustained level must not exceed
        # the ceiling (allow a small release-tail margin near the very start).
        settled = out[2000:]
        assert np.max(np.abs(settled)) <= threshold_linear + 1e-3
        assert np.all(np.isfinite(out))

    def test_no_limiting_passes_through(self):
        """A signal below the ceiling is left essentially unchanged."""
        limiter = create_brick_wall_limiter(threshold_db=-0.5)
        audio = (np.random.RandomState(3).randn(10000) * 0.05).astype(np.float64)
        out = limiter.process(audio)
        np.testing.assert_allclose(out, audio, atol=1e-9)

    def test_lookahead_zero_does_not_crash(self):
        """lookahead_ms=0 is clamped and must not raise (#3750)."""
        limiter = create_brick_wall_limiter(lookahead_ms=0.0)
        audio = (np.random.RandomState(5).randn(2048) * 1.5).astype(np.float32)
        out = limiter.process(audio)
        assert out.shape == audio.shape
        assert out.dtype == np.float32

    def test_empty_audio_returns_copy(self):
        limiter = create_brick_wall_limiter()
        empty = np.array([], dtype=np.float32)
        out = limiter.process(empty)
        assert out.shape == empty.shape
        assert out is not empty
