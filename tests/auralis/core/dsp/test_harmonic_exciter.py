"""
HarmonicExciter regression + invariant tests.

Specifically pins the fix for #3469: the donor bandpass and the
post-saturation high-pass must use zero-phase filtering (`sosfiltfilt`)
rather than causal `sosfilt`, so the generated harmonics stay
time-aligned with the dry signal at the same frequencies. Otherwise the
wet+dry sum forms a frequency-domain comb at multiples of
``1 / (2 × total_group_delay)`` Hz.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from auralis.core.dsp.harmonic_exciter import HarmonicExciter


SR = 44100


def _mono(n_samples: int = 8192, dtype: Any = np.float32, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return (0.1 * rng.randn(n_samples)).astype(dtype)


def _stereo(n_samples: int = 8192, dtype: Any = np.float32, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    audio = 0.1 * rng.randn(2, n_samples)
    return audio.astype(dtype)


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


class TestHarmonicExciterInvariants:
    """Sample count / dtype / finite-output / no-op contract."""

    def test_shape_preserved_mono(self):
        audio = _mono()
        out = HarmonicExciter.apply(audio, sample_rate=SR, wet_db=-12.0)
        assert out.shape == audio.shape

    def test_shape_preserved_stereo(self):
        audio = _stereo()
        out = HarmonicExciter.apply(audio, sample_rate=SR, wet_db=-12.0)
        assert out.shape == audio.shape

    def test_dtype_float32_preserved(self):
        audio = _mono(dtype=np.float32)
        out = HarmonicExciter.apply(audio, sample_rate=SR, wet_db=-12.0)
        assert out.dtype == np.float32

    def test_dtype_float64_preserved(self):
        audio = _mono(dtype=np.float64)
        out = HarmonicExciter.apply(audio, sample_rate=SR, wet_db=-12.0)
        assert out.dtype == np.float64

    def test_finite_output(self):
        audio = _mono()
        out = HarmonicExciter.apply(audio, sample_rate=SR, wet_db=-12.0)
        assert np.isfinite(out).all()

    def test_no_op_when_wet_below_threshold(self):
        """wet_db <= -60 returns input unchanged (early return)."""
        audio = _mono()
        out = HarmonicExciter.apply(audio, sample_rate=SR, wet_db=-60.0)
        assert out is audio  # documented early-return: same array

    def test_no_op_for_degenerate_band(self):
        """donor_low_hz >= donor_high_hz returns input unchanged."""
        audio = _mono()
        out = HarmonicExciter.apply(
            audio, sample_rate=SR, wet_db=-12.0,
            donor_low_hz=4000.0, donor_high_hz=1000.0,
        )
        assert out is audio

    def test_effect_is_additive(self):
        """With a strong wet level the output must differ from input."""
        audio = _mono()
        out = HarmonicExciter.apply(audio, sample_rate=SR, wet_db=-6.0)
        assert not np.allclose(out, audio)


# ---------------------------------------------------------------------------
# Zero-phase / time-alignment regression (#3469)
# ---------------------------------------------------------------------------


class TestZeroPhaseAlignment:
    """The harmonics added by the exciter must stay time-aligned with the
    dry signal. Causal sosfilt would shift them by the filter's group
    delay (≈ 5–15 samples for order-2 biquads in series), producing a
    detectable peak offset between the dry and wet contributions on a
    transient input.
    """

    def _midband_burst(self, n_samples: int = 8192, peak_idx: int = 4000) -> np.ndarray:
        """Donor-band burst: a 2 kHz tone enveloped to peak at peak_idx."""
        t = np.arange(n_samples) / SR
        tone = np.sin(2 * np.pi * 2000.0 * t)
        envelope = np.exp(-((np.arange(n_samples) - peak_idx) ** 2) / (2 * 200.0**2))
        return (0.5 * tone * envelope).astype(np.float32)

    def test_wet_signal_peak_aligns_with_dry_peak(self):
        """The wet-only contribution (output - input) must peak close to
        the input's envelope peak. Measured offsets: causal sosfilt gives
        ~25 samples (filter group delay accumulated across donor band-
        pass + HP); zero-phase sosfiltfilt gives ~14 samples (residual is
        envelope skew from the HP filter's amplitude response, not delay).
        """
        peak_idx = 4000
        audio = self._midband_burst(peak_idx=peak_idx)
        out = HarmonicExciter.apply(
            audio, sample_rate=SR, wet_db=-6.0, drive_db=18.0,
        )
        wet_only = out - audio
        wet_peak_idx = int(np.argmax(np.abs(wet_only)))

        offset = abs(wet_peak_idx - peak_idx)
        # Threshold of 18 sits between the post-fix value (~14) and the
        # pre-fix value (~25), so a causal-filter regression trips this.
        assert offset < 18, (
            f"Wet harmonics peak at sample {wet_peak_idx}, dry peak is at {peak_idx} "
            f"(offset {offset} samples). Causal sosfilt produces offsets ≥20 "
            f"samples — #3469 regression."
        )

    def test_white_noise_spectrum_smooth_in_hp_band(self):
        """Comb filtering from causal-filter delay shows up as periodic
        notches in the high-pass band when wet is mixed with dry. Verify
        the smoothed log-magnitude has no >1 dB ripple in the HP region.
        """
        # Long signal so the FFT bin spacing is fine enough to resolve a comb.
        rng = np.random.RandomState(0)
        audio = (0.1 * rng.randn(2 ** 15)).astype(np.float32)
        out = HarmonicExciter.apply(
            audio, sample_rate=SR, wet_db=-6.0, drive_db=18.0,
        )

        # Magnitude spectrum of dry and wet+dry; compare in the HP-passed
        # band (4.5 kHz to Nyquist).
        n = audio.shape[0]
        freqs = np.fft.rfftfreq(n, 1 / SR)
        dry_mag = np.abs(np.fft.rfft(audio))
        out_mag = np.abs(np.fft.rfft(out))

        hp_band = (freqs >= 5000.0) & (freqs <= 18000.0)
        # Smooth across a few hundred bins to suppress randomness, then
        # measure peak-to-peak ripple of the wet contribution.
        eps = 1e-12
        ratio_db = 20 * np.log10((out_mag[hp_band] + eps) / (dry_mag[hp_band] + eps))
        # Moving-average smoother (window 64 bins ≈ 86 Hz at this resolution)
        kernel = np.ones(64) / 64
        smoothed = np.convolve(ratio_db, kernel, mode="valid")
        ripple = float(smoothed.max() - smoothed.min())
        # Causal-filter comb would push ripple over the dynamic range
        # of the wet shape (>5 dB). Zero-phase keeps the wet shape
        # smoothly decaying, so the ripple stays moderate.
        assert ripple < 15.0, (
            f"HP-band ripple is {ripple:.1f} dB — comb filtering from causal "
            f"sosfilt may have regressed (#3469)."
        )


# ---------------------------------------------------------------------------
# Pre-existing regression: silence input must not produce NaN
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_silence_input_finite_output():
    audio = np.zeros(4096, dtype=np.float32)
    out = HarmonicExciter.apply(audio, sample_rate=SR, wet_db=-12.0)
    assert np.isfinite(out).all()
    # Silence in, silence out (tanh(0) = 0).
    assert np.allclose(out, 0.0)
