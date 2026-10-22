"""
EnvelopeFollower: one implementation, dtype-preserving, JIT == pure Python
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Replaces the dtype regression tests for the former VectorizedEnvelopeFollower
(#4225, #4934). The envelope recursion used to exist three times; the dtype
fixes only reached one copy. `process_buffer` is now the only buffer path.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest

from auralis.dsp.dynamics import envelope
from auralis.dsp.dynamics.envelope import EnvelopeFollower


def _follower() -> EnvelopeFollower:
    return EnvelopeFollower(sample_rate=44100, attack_ms=5.0, release_ms=50.0)


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_process_buffer_preserves_dtype(dtype):
    levels = np.random.default_rng(0).random(1000).astype(dtype)

    assert _follower().process_buffer(levels).dtype == dtype


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_empty_input_preserves_dtype(dtype):
    result = _follower().process_buffer(np.array([], dtype=dtype))

    assert result.dtype == dtype
    assert len(result) == 0


def test_buffer_matches_the_scalar_recursion():
    levels = np.random.default_rng(1).random(2000)
    scalar = _follower()
    expected = np.array([scalar.process(x) for x in levels])

    buffered = _follower().process_buffer(levels)

    np.testing.assert_allclose(buffered, expected, rtol=1e-12, atol=1e-12)


def test_jit_kernel_matches_plain_python():
    """Whichever kernel was selected at import must agree with the plain loop."""
    levels = np.random.default_rng(2).random(2000)
    coeffs = (0.9, 0.99)

    selected = envelope._follow_kernel(levels, 0.25, *coeffs)
    plain = envelope._follow_envelope(levels, 0.25, *coeffs)

    np.testing.assert_allclose(selected, plain, rtol=1e-12, atol=1e-12)


def test_state_carries_across_buffers():
    levels = np.random.default_rng(3).random(1000)
    whole = _follower().process_buffer(levels)

    split = _follower()
    halves = np.concatenate([split.process_buffer(levels[:400]), split.process_buffer(levels[400:])])

    np.testing.assert_allclose(halves, whole, rtol=1e-12, atol=1e-12)


def test_reset_clears_state():
    follower = _follower()
    follower.process_buffer(np.ones(100))
    follower.reset()

    assert follower.envelope == 0.0
