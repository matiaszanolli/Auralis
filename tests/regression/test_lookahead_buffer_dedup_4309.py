"""
Shared LookaheadBuffer helper (#4309)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`AdaptiveCompressor._apply_lookahead` and `AdaptiveLimiter._apply_lookahead_delay`
were a byte-identical ~15-line ring-buffer implementation duplicated across two
files. Both were made to delegate to the shared `LookaheadBuffer` helper.

Consolidating surfaced a real divergence the issue's own "no functional
divergence found" note missed: the compressor had an
`if lookahead_samples == 0: return audio` early-return guard that the limiter's
copy lacked, so with `lookahead_ms=0.0` the old limiter code did `audio[:-0]` —
which NumPy evaluates as `audio[:0]` (empty) — and silently returned a
zero-length array.

#4873 deleted `AdaptiveLimiter` as unreachable from the shipped app, so the
limiter-side assertions went with it. What survives here is the compressor
half plus the shared helper's own behaviour: the extraction is what keeps a
future second copy from re-diverging, and it is still worth pinning even with
one consumer left.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.compressor import AdaptiveCompressor
from auralis.dsp.dynamics.lookahead_buffer import LookaheadBuffer
from auralis.dsp.dynamics.settings import CompressorSettings


@pytest.mark.regression
class TestSharedLookaheadBuffer:
    def test_compressor_uses_the_shared_helper_class(self):
        compressor = AdaptiveCompressor(
            CompressorSettings(enable_lookahead=True, lookahead_ms=5.0), sample_rate=44100
        )

        assert isinstance(compressor._lookahead, LookaheadBuffer)

    def test_compressor_lookahead_buffer_property_still_works(self):
        """Backward-compat: .lookahead_buffer must remain directly readable."""
        compressor = AdaptiveCompressor(
            CompressorSettings(enable_lookahead=True, lookahead_ms=5.0), sample_rate=44100
        )
        assert compressor.lookahead_buffer is None
        compressor._apply_lookahead(np.random.randn(4410).astype(np.float32))
        assert compressor.lookahead_buffer is not None


@pytest.mark.regression
class TestZeroLookaheadGuard:
    """The guard whose absence in the limiter's copy was the #4309 finding.

    Kept pointed at the surviving consumer so the correct behaviour stays
    pinned rather than being deleted along with the buggy copy.
    """

    def test_zero_lookahead_ms_preserves_sample_count(self):
        settings = CompressorSettings(enable_lookahead=True, lookahead_ms=0.0)
        compressor = AdaptiveCompressor(settings, sample_rate=44100)
        assert compressor.lookahead_samples == 0

        audio = np.random.randn(1000).astype(np.float32) * 0.1
        delayed = compressor._apply_lookahead(audio)

        assert len(delayed) == len(audio)
        np.testing.assert_array_equal(delayed, audio)

    def test_zero_lookahead_ms_process_preserves_sample_count(self):
        """End-to-end through process(), not just the delay helper."""
        settings = CompressorSettings(enable_lookahead=True, lookahead_ms=0.0)
        compressor = AdaptiveCompressor(settings, sample_rate=44100)

        audio = (np.random.randn(2000, 2) * 0.1).astype(np.float32)
        processed, _info = compressor.process(audio)

        assert len(processed) == len(audio)


@pytest.mark.regression
class TestNdimResetGuard:
    """The ndim-reset guard the limiter's copy lacked — pinned on the helper's
    surviving consumer so a mono/stereo switch still cannot crash."""

    def test_mono_then_stereo_no_crash(self):
        settings = CompressorSettings(enable_lookahead=True, lookahead_ms=5.0)
        compressor = AdaptiveCompressor(settings, sample_rate=44100)

        mono = np.random.randn(4410).astype(np.float32)
        stereo = np.random.randn(4410, 2).astype(np.float32)

        result_mono = compressor._apply_lookahead(mono)
        assert result_mono.ndim == 1
        assert len(result_mono) == len(mono)

        result_stereo = compressor._apply_lookahead(stereo)
        assert result_stereo.ndim == 2
        assert len(result_stereo) == len(stereo)
