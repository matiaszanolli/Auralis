"""
Shared LookaheadBuffer for AdaptiveCompressor/AdaptiveLimiter (#4309)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

AdaptiveCompressor._apply_lookahead and AdaptiveLimiter._apply_lookahead_delay
were a byte-identical ~15-line ring-buffer implementation duplicated across
two files. Both now delegate to the shared LookaheadBuffer helper.

Consolidating surfaced a real divergence the issue's own "no functional
divergence found" note missed: the compressor had an
`if lookahead_samples == 0: return audio` early-return guard that the
limiter's copy lacked. With `lookahead_ms=0.0` (a value LimiterSettings
explicitly allows, clamped to [0, 50]), the old limiter code did
`audio[:-0]`, which NumPy evaluates as `audio[:0]` (empty), so
_apply_lookahead_delay silently returned a zero-length array — the
processed audio dropped entirely. This is now fixed as a consequence of
using the compressor's (correct) guard for both.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.compressor import AdaptiveCompressor
from auralis.dsp.dynamics.limiter import AdaptiveLimiter
from auralis.dsp.dynamics.lookahead_buffer import LookaheadBuffer
from auralis.dsp.dynamics.settings import CompressorSettings, LimiterSettings


@pytest.mark.regression
class TestSharedLookaheadBuffer:
    def test_compressor_and_limiter_use_the_same_helper_class(self):
        compressor = AdaptiveCompressor(
            CompressorSettings(enable_lookahead=True, lookahead_ms=5.0), sample_rate=44100
        )
        limiter = AdaptiveLimiter(LimiterSettings(lookahead_ms=5.0), sample_rate=44100)

        assert isinstance(compressor._lookahead, LookaheadBuffer)
        assert isinstance(limiter._lookahead, LookaheadBuffer)

    def test_compressor_lookahead_buffer_property_still_works(self):
        """Backward-compat: .lookahead_buffer must remain directly readable."""
        compressor = AdaptiveCompressor(
            CompressorSettings(enable_lookahead=True, lookahead_ms=5.0), sample_rate=44100
        )
        assert compressor.lookahead_buffer is None
        compressor._apply_lookahead(np.random.randn(4410).astype(np.float32))
        assert compressor.lookahead_buffer is not None


@pytest.mark.regression
class TestLimiterZeroLookaheadFix:
    """Regression test for the latent bug consolidation surfaced (#4309)."""

    def test_zero_lookahead_ms_preserves_sample_count(self):
        settings = LimiterSettings(lookahead_ms=0.0)
        limiter = AdaptiveLimiter(settings, sample_rate=44100)
        assert limiter.lookahead_samples == 0

        audio = np.random.randn(1000).astype(np.float32) * 0.1
        delayed = limiter._apply_lookahead_delay(audio)

        assert len(delayed) == len(audio)
        np.testing.assert_array_equal(delayed, audio)

    def test_zero_lookahead_ms_process_preserves_sample_count(self):
        """End-to-end through process(), not just the delay helper."""
        settings = LimiterSettings(lookahead_ms=0.0, oversampling=1, isr_enabled=False)
        limiter = AdaptiveLimiter(settings, sample_rate=44100)

        audio = (np.random.randn(2000, 2) * 0.1).astype(np.float32)
        processed, _info = limiter.process(audio)

        assert len(processed) == len(audio)


@pytest.mark.regression
class TestLimiterNdimResetNowGuarded:
    """The limiter's copy previously lacked the ndim-reset guard the
    compressor had — verify it no longer crashes on a mono/stereo switch."""

    def test_mono_then_stereo_no_crash(self):
        settings = LimiterSettings(lookahead_ms=5.0)
        limiter = AdaptiveLimiter(settings, sample_rate=44100)

        mono = np.random.randn(4410).astype(np.float32)
        stereo = np.random.randn(4410, 2).astype(np.float32)

        result_mono = limiter._apply_lookahead_delay(mono)
        assert result_mono.ndim == 1
        assert len(result_mono) == len(mono)

        result_stereo = limiter._apply_lookahead_delay(stereo)
        assert result_stereo.ndim == 2
        assert len(result_stereo) == len(stereo)
