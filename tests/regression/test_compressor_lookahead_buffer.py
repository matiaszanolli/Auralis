"""
Regression: Compressor lookahead buffer reset on ndim change (#2614)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Verifies two fixes from commit 0c5ebd6d:
1. Buffer reset when audio ndim changes (mono→stereo or vice versa)
2. .copy() for buffer updates to prevent aliasing

Without (1), a mono buffer applied to stereo audio causes a shape
mismatch crash. Without (2), the buffer aliases the input array
and can be silently mutated by downstream processing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.compressor import AdaptiveCompressor
from auralis.dsp.dynamics.settings import CompressorSettings


@pytest.fixture
def compressor():
    """Compressor with lookahead enabled."""
    settings = CompressorSettings(enable_lookahead=True, lookahead_ms=5.0)
    return AdaptiveCompressor(settings, sample_rate=44100)


class TestLookaheadNdimReset:
    """Buffer must reset when audio dimensionality changes."""

    def test_mono_then_stereo_no_crash(self, compressor):
        """Processing mono then stereo must not crash (regression #2614)."""
        mono = np.random.randn(4410).astype(np.float32)   # 100ms mono
        stereo = np.random.randn(4410, 2).astype(np.float32)  # 100ms stereo

        # First call initialises a 1-D buffer
        result_mono = compressor._apply_lookahead(mono)
        assert result_mono.ndim == 1
        assert len(result_mono) == len(mono)

        # Second call must reset buffer to 2-D without crashing
        result_stereo = compressor._apply_lookahead(stereo)
        assert result_stereo.ndim == 2
        assert len(result_stereo) == len(stereo)

    def test_stereo_then_mono_no_crash(self, compressor):
        """Processing stereo then mono must not crash."""
        stereo = np.random.randn(4410, 2).astype(np.float32)
        mono = np.random.randn(4410).astype(np.float32)

        compressor._apply_lookahead(stereo)
        result = compressor._apply_lookahead(mono)

        assert result.ndim == 1
        assert len(result) == len(mono)

    def test_buffer_shape_matches_last_audio(self, compressor):
        """After ndim change, buffer shape must match the new audio."""
        mono = np.random.randn(4410).astype(np.float32)
        stereo = np.random.randn(4410, 2).astype(np.float32)

        compressor._apply_lookahead(mono)
        assert compressor.lookahead_buffer is not None
        assert compressor.lookahead_buffer.ndim == 1

        compressor._apply_lookahead(stereo)
        assert compressor.lookahead_buffer.ndim == 2
        assert compressor.lookahead_buffer.shape[1] == 2


class TestLookaheadCopySemantics:
    """Buffer must be an independent copy, not an alias of the input."""

    def test_buffer_is_independent_of_input(self, compressor):
        """Mutating input after processing must not change the buffer (#2614)."""
        audio = np.ones(4410, dtype=np.float32)

        compressor._apply_lookahead(audio)
        buffer_before = compressor.lookahead_buffer.copy()

        # Mutate the original input
        audio[:] = 999.0

        # Buffer must be unchanged
        np.testing.assert_array_equal(compressor.lookahead_buffer, buffer_before)

    def test_partial_buffer_update_is_independent(self, compressor):
        """Partial buffer path (.copy() on line 208) must also be independent."""
        # First call with large audio to initialise buffer
        large = np.ones(4410, dtype=np.float32)
        compressor._apply_lookahead(large)

        # Second call with audio shorter than buffer → partial update path
        small = np.ones(100, dtype=np.float32) * 2.0
        compressor._apply_lookahead(small)
        buffer_after = compressor.lookahead_buffer.copy()

        # Mutate the small input
        small[:] = 999.0

        np.testing.assert_array_equal(compressor.lookahead_buffer, buffer_after)
