"""
AdaptiveLimiter Oversample/Downsample Round-Trip Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for issue #4907:

The previous zero-stuff + fixed moving-average `_oversample`/`_downsample`
pair algebraically reduced to a 3-tap FIR at the base rate with the wrong
passband shape: +2.5 dB on DC-like content and -7.0 dB near Nyquist. This
altered level and frequency response even when the limiter's gain curve is
identically 1.0, and the false +2.5 dB gain occurred *after* the gain curve
was applied, defeating peak-control intent.
"""

import numpy as np
import pytest

from auralis.dsp.dynamics.limiter import AdaptiveLimiter
from auralis.dsp.dynamics.settings import LimiterSettings


@pytest.mark.regression
class TestAdaptiveLimiterOversampleRoundTrip:
    """Regression tests for the _oversample/_downsample round trip (#4907)."""

    def _make_limiter(self, oversampling=4):
        settings = LimiterSettings(
            threshold_db=-1.0,
            oversampling=oversampling,
            isr_enabled=False,
            lookahead_ms=0.0,
        )
        return AdaptiveLimiter(settings, sample_rate=44100)

    def _round_trip(self, limiter, audio):
        return limiter._downsample(limiter._oversample(audio))

    def test_dc_round_trip_preserves_amplitude(self):
        """A DC-like (near-constant) signal must not be amplified. The old
        3-tap kernel produced +2.5 dB (a ~1.33x gain) on this content."""
        limiter = self._make_limiter()
        amplitude = 0.5
        audio = np.full(2000, amplitude, dtype=np.float64)

        result = self._round_trip(limiter, audio)

        # Filter transients live at the edges of the finite-length window;
        # assert on the settled middle region.
        settled = result[200:1800]
        assert np.allclose(settled, amplitude, atol=1e-6), (
            f"DC content was altered by the oversample round trip: "
            f"got {settled.min():.6f}..{settled.max():.6f}, expected {amplitude}"
        )

    def test_dc_round_trip_no_gain_overshoot(self):
        """Explicitly guard against the old +2.5 dB DC gain regression."""
        limiter = self._make_limiter()
        amplitude = 0.5
        audio = np.full(2000, amplitude, dtype=np.float64)

        result = self._round_trip(limiter, audio)
        settled = result[200:1800]
        gain_db = 20 * np.log10(np.max(np.abs(settled)) / amplitude)

        assert gain_db < 0.1, f"DC gain overshoot: {gain_db:.2f} dB (expected ~0 dB)"

    def test_mid_frequency_round_trip_preserves_amplitude(self):
        """A mid-frequency tone (well below Nyquist, unlike a literal
        alternating +/-A signal) should pass through close to unity gain —
        the old kernel distorted the passband shape at all frequencies, not
        just DC and Nyquist."""
        limiter = self._make_limiter()
        sr = 44100
        t = np.arange(4000) / sr
        amplitude = 0.5
        audio = (amplitude * np.sin(2 * np.pi * 2000 * t)).astype(np.float64)

        result = self._round_trip(limiter, audio)
        settled = result[400:3600]
        settled_input = audio[400:3600]

        assert np.allclose(settled, settled_input, atol=0.02), (
            f"Mid-frequency content was altered by the oversample round trip: "
            f"max abs diff {np.max(np.abs(settled - settled_input)):.4f}"
        )

    def test_dtype_and_length_preserved(self):
        limiter = self._make_limiter()
        audio = np.random.randn(1000, 2).astype(np.float32) * 0.3

        result = self._round_trip(limiter, audio)

        assert result.dtype == np.float32
        assert result.shape == audio.shape

    def test_process_with_inert_gain_curve_does_not_amplify(self):
        """End-to-end: with the threshold far above the signal (gain curve
        stays at 1.0 throughout), process() must not raise the signal's peak
        level via the oversample round trip."""
        settings = LimiterSettings(
            threshold_db=0.0,
            oversampling=4,
            isr_enabled=False,
            lookahead_ms=0.0,
        )
        limiter = AdaptiveLimiter(settings, sample_rate=44100)
        audio = np.full((2000, 2), 0.3, dtype=np.float64)

        result, _ = limiter.process(audio)
        settled = result[200:1800]

        assert np.max(np.abs(settled)) <= 0.3 + 1e-6, (
            f"Inert (gain=1.0) limiter amplified DC content to "
            f"{np.max(np.abs(settled)):.4f} (expected <= 0.3)"
        )
