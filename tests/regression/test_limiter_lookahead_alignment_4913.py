"""
AdaptiveLimiter/AdaptiveCompressor Lookahead Alignment Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #4913:

AdaptiveLimiter computed its peak envelope from the *undelayed* audio (a
forward-looking window) but multiplied the *delayed* signal by the
resulting gain curve, double-applying the lookahead. The gain computed for
window [k, k+L) ended up gating `audio[k - L]`, not `audio[k]` itself: the
limiter both missed the peaks it was supposed to catch and ducked unrelated
material `L` samples early. The fix drops `_apply_lookahead_delay` from the
signal path (matching `BrickWallLimiter`'s non-causal batch convention,
since the whole buffer is already available) and applies the forward-
looking gain curve directly to the undelayed audio.

A secondary defect in the same function: `_process_core` runs on the
*oversampled* signal while `lookahead_samples` is computed at the base
rate, so the effective lookahead was `lookahead_ms / oversampling`.

`AdaptiveCompressor` had the mirror-image defect: levels were computed
from, and gain applied to, the same delayed signal — self-consistent, but
the delay bought nothing (pure added latency, zero gain-computer benefit).
The fix applies the same convention: drop the delay from the signal path.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.compressor import AdaptiveCompressor
from auralis.dsp.dynamics.limiter import AdaptiveLimiter
from auralis.dsp.dynamics.settings import CompressorSettings, LimiterSettings


@pytest.mark.regression
class TestLimiterSpikeAlignment:
    """A single-sample spike must be gated at its own output position, not
    ducked `lookahead` samples early with the spike itself left untouched."""

    def _make_limiter(self, lookahead_ms=5.0, threshold_db=-6.0):
        settings = LimiterSettings(
            threshold_db=threshold_db,
            release_ms=5.0,
            lookahead_ms=lookahead_ms,
            isr_enabled=False,
            oversampling=1,
        )
        return AdaptiveLimiter(settings, sample_rate=44100)

    def test_spike_gain_reduction_lands_at_spike_index_not_lookahead_early(self):
        limiter = self._make_limiter()
        lookahead = limiter.lookahead_samples
        assert lookahead > 0

        sr = 44100
        k = sr // 2
        audio = np.full(sr, 0.1, dtype=np.float64)  # quiet baseline, below threshold
        audio[k] = 0.99  # single-sample spike, well above threshold

        result, _info = limiter.process(audio)

        # Before the fix, `audio[k]` (the spike) was multiplied into
        # `delayed_audio[k + lookahead]`, not `delayed_audio[k]` -- so
        # `result[k]` was actually `audio[k - lookahead]` (quiet baseline)
        # gated by the gain curve computed FOR the spike, ducking it down
        # near the baseline's own level (~0.1) instead of showing the
        # (attenuated) spike. After the fix, `result[k]` is `audio[k]`
        # itself, gain-reduced but still clearly spike-like -- far above
        # the quiet baseline, not collapsed onto it.
        assert result[k] > 0.3, (
            f"Spike at index {k} reads as baseline-level ({result[k]:.4f}), "
            f"not an attenuated spike -- gain curve likely misaligned"
        )
        assert result[k] < 0.99 * 0.98, (
            f"Spike at index {k} was not limited at all: {result[k]:.4f}"
        )

    def test_oversampled_lookahead_window_scales_with_factor(self):
        """`lookahead_samples` is computed at the base rate; `_process_core`
        may run on the oversampled signal, so the window must scale by the
        oversampling factor or the effective lookahead silently shrinks to
        `lookahead_ms / oversampling` (#4913 secondary defect)."""
        settings = LimiterSettings(
            lookahead_ms=5.0, oversampling=4, isr_enabled=False, threshold_db=-6.0
        )
        limiter = AdaptiveLimiter(settings, sample_rate=44100)
        base_lookahead = limiter.lookahead_samples
        assert base_lookahead > 0

        audio = np.zeros(2000, dtype=np.float64)
        audio[0] = 1.0  # single spike so the forward window has a nonzero span

        envelope_base = limiter._compute_peak_envelope(audio, oversampling=1)
        envelope_os = limiter._compute_peak_envelope(audio, oversampling=settings.oversampling)

        engaged_base = np.count_nonzero(envelope_base > 0)
        engaged_os = np.count_nonzero(envelope_os > 0)

        assert engaged_base == base_lookahead
        assert engaged_os == base_lookahead * settings.oversampling


@pytest.mark.regression
class TestCompressorLookaheadNoLongerAddsOutputLatency:
    """AdaptiveCompressor's mirror-image defect: with the fix, gain is
    computed from and applied to the same undelayed audio, so
    `enable_lookahead` no longer shifts the output relative to
    `enable_lookahead=False` (#4913)."""

    def _settings(self, enable_lookahead):
        return CompressorSettings(
            threshold_db=-12.0,
            ratio=4.0,
            attack_ms=0.01,
            release_ms=50.0,
            enable_lookahead=enable_lookahead,
            lookahead_ms=5.0,
        )

    def test_lookahead_enabled_matches_disabled_sample_for_sample(self):
        compressor = AdaptiveCompressor(self._settings(True), sample_rate=44100)
        lookahead = compressor.lookahead_samples
        assert lookahead > 0

        sr = 44100
        k = sr // 2
        audio = np.concatenate(
            [np.full(k, 0.05), np.full(sr - k, 0.9)]
        ).astype(np.float64)

        result, _info = compressor.process(audio.copy())

        compressor_no_la = AdaptiveCompressor(self._settings(False), sample_rate=44100)
        result_no_la, _info_no_la = compressor_no_la.process(audio.copy())

        # Before the fix, `enable_lookahead=True` delayed both the level
        # detector and the signal it gated by `lookahead` samples relative
        # to `enable_lookahead=False` -- a self-consistent shift, but pure
        # added latency for zero gain-computer benefit. The fix makes the
        # lookahead delay a no-op in the signal path, so the two must now
        # agree sample-for-sample.
        np.testing.assert_allclose(result, result_no_la, atol=1e-9)
