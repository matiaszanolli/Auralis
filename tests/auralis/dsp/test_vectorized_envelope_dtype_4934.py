"""
Regression: VectorizedEnvelopeFollower preserves caller dtype (#4225, #4934)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#4225 fixed process_buffer_vectorized's hard-coded float32 output allocation
(np.zeros_like(input_levels) instead of np.zeros(len, dtype=np.float32)), but
left the sibling process_buffer_numba unchanged — it still ended with
`output.astype(np.float32, copy=False)`. Since process_buffer() tries numba
first and only falls back to the vectorized path on exception, the #4225-fixed
path is the one that almost never actually runs when numba is available.

:copyright: (C) 2026 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from auralis.dsp.dynamics.vectorized_envelope import VectorizedEnvelopeFollower


def _follower(use_numba: bool) -> VectorizedEnvelopeFollower:
    return VectorizedEnvelopeFollower(
        sample_rate=44100, attack_ms=5.0, release_ms=50.0, use_numba=use_numba
    )


class TestProcessBufferNumbaPreservesDtype:
    """The #4934 fix: the numba path, not just the vectorized one."""

    def test_float64_input_yields_float64_output(self):
        follower = _follower(use_numba=True)
        input_levels = np.random.rand(1000).astype(np.float64)

        result = follower.process_buffer_numba(input_levels)

        assert result.dtype == np.float64, (
            f"expected float64 preserved end-to-end, got {result.dtype}"
        )

    def test_float32_input_yields_float32_output(self):
        follower = _follower(use_numba=True)
        input_levels = np.random.rand(1000).astype(np.float32)

        result = follower.process_buffer_numba(input_levels)

        assert result.dtype == np.float32

    def test_process_buffer_dispatches_to_numba_and_preserves_dtype(self):
        """End-to-end via process_buffer() (the actual call site used by
        the since-deleted AdaptiveLimiter, #4873), not the numba method
        directly — confirms the
        default use_numba=True path is the one under test, matching how
        production code actually calls this class."""
        follower = _follower(use_numba=True)
        input_levels = np.random.rand(500).astype(np.float64)

        result = follower.process_buffer(input_levels)

        assert result.dtype == np.float64


class TestProcessBufferVectorizedPreservesDtype:
    """#4225's original fix, re-verified here alongside its numba sibling."""

    def test_float64_input_yields_float64_output(self):
        follower = _follower(use_numba=False)
        input_levels = np.random.rand(1000).astype(np.float64)

        result = follower.process_buffer_vectorized(input_levels)

        assert result.dtype == np.float64

    def test_empty_input_preserves_dtype(self):
        """#4934's secondary fix: empty input used to always return a bare
        float64 np.array([]) regardless of input dtype."""
        follower = _follower(use_numba=False)
        input_levels = np.array([], dtype=np.float32)

        result = follower.process_buffer_vectorized(input_levels)

        assert result.dtype == np.float32
        assert len(result) == 0


class TestBothPathsProduceEquivalentValues:
    """Dtype aside, numba and vectorized must agree numerically."""

    def test_numba_and_vectorized_agree(self):
        input_levels = np.random.rand(2000).astype(np.float64)

        numba_follower = _follower(use_numba=True)
        vectorized_follower = _follower(use_numba=False)

        numba_result = numba_follower.process_buffer_numba(input_levels)
        vectorized_result = vectorized_follower.process_buffer_vectorized(input_levels)

        np.testing.assert_allclose(numba_result, vectorized_result, rtol=1e-6, atol=1e-9)
