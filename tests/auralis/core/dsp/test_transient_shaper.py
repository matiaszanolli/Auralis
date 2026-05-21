"""
TransientShaper regression + invariant tests.

Pins the fix for #3470: the bandpass that drives the `audio + delta`
parallel-add path must use zero-phase filtering (`sosfiltfilt`),
otherwise the boost arrives later than the dry transient and the
shaper smears instead of sharpens. The envelope-follower one-pole
stays causal by design (it's a derived control signal, not summed
into the dry path).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from auralis.core.dsp.transient_shaper import TransientShaper


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


class TestTransientShaperInvariants:
    def test_shape_preserved_mono(self):
        audio = _mono()
        out = TransientShaper.apply(audio, SR, 60.0, 250.0, attack_boost_db=6.0)
        assert out.shape == audio.shape

    def test_shape_preserved_stereo(self):
        audio = _stereo()
        out = TransientShaper.apply(audio, SR, 60.0, 250.0, attack_boost_db=6.0)
        assert out.shape == audio.shape

    def test_dtype_float32_preserved(self):
        audio = _mono(dtype=np.float32)
        out = TransientShaper.apply(audio, SR, 60.0, 250.0, attack_boost_db=6.0)
        assert out.dtype == np.float32

    def test_dtype_float64_preserved(self):
        audio = _mono(dtype=np.float64)
        out = TransientShaper.apply(audio, SR, 60.0, 250.0, attack_boost_db=6.0)
        assert out.dtype == np.float64

    def test_finite_output(self):
        audio = _mono()
        out = TransientShaper.apply(audio, SR, 60.0, 250.0, attack_boost_db=6.0)
        assert np.isfinite(out).all()

    def test_no_op_when_boost_below_threshold(self):
        """attack_boost_db <= 0.05 returns input unchanged (early return)."""
        audio = _mono()
        out = TransientShaper.apply(audio, SR, 60.0, 250.0, attack_boost_db=0.0)
        assert out is audio

    def test_no_op_for_degenerate_band(self):
        audio = _mono()
        out = TransientShaper.apply(audio, SR, 250.0, 60.0, attack_boost_db=6.0)
        assert out is audio

    def test_effect_is_additive(self):
        """With percussive content, the output must differ from input."""
        # Click train in the kick range so the shaper actually detects onsets.
        n = 8192
        audio = np.zeros(n, dtype=np.float32)
        for click_idx in (1000, 3000, 5000, 7000):
            t = np.arange(200) / SR
            audio[click_idx:click_idx + 200] = (
                0.5 * np.sin(2 * np.pi * 120.0 * t) * np.exp(-50 * t)
            ).astype(np.float32)
        out = TransientShaper.apply(audio, SR, 60.0, 250.0, attack_boost_db=9.0)
        assert not np.allclose(out, audio)


# ---------------------------------------------------------------------------
# Zero-phase / time-alignment regression (#3470)
# ---------------------------------------------------------------------------


class TestZeroPhaseAlignment:
    """The transient boost delta added to dry must NOT arrive later than
    the dry transient itself. Causal sosfilt would delay it by the
    bandpass group delay (~5-10 samples for order-2). After the fix,
    `audio + delta` peak alignment is within envelope-follower lag."""

    def _kick_burst(self, n_samples: int = 8192, hit_idx: int = 4000) -> np.ndarray:
        """120 Hz tone with sharp attack envelope at hit_idx."""
        n_decay = 400
        t = np.arange(n_decay) / SR
        # Sharp attack, exponential decay — kick-drum-like.
        tone = np.sin(2 * np.pi * 120.0 * t) * np.exp(-25 * t)
        audio = np.zeros(n_samples, dtype=np.float32)
        audio[hit_idx:hit_idx + n_decay] = (0.5 * tone).astype(np.float32)
        return audio

    def test_delta_peak_aligns_with_dry_attack(self):
        """The delta = (output - audio) must peak close to the input
        attack onset. Causal sosfilt would push it 5-15 samples late;
        zero-phase keeps it tight (~envelope-follower attack lag).
        """
        hit_idx = 4000
        audio = self._kick_burst(hit_idx=hit_idx)
        out = TransientShaper.apply(
            audio, SR, band_low_hz=60.0, band_high_hz=250.0,
            attack_boost_db=9.0, fast_ms=5.0, slow_ms=50.0,
        )
        delta = out - audio
        # The delta is concentrated near the attack; the dry attack
        # starts at hit_idx, so we ask "where is the maximum |delta|
        # within ±100 samples of hit_idx?" The fast envelope's tau is
        # 5 ms = 220 samples, so anything > 200 samples lag is the
        # causal-filter bug.
        window_lo = max(0, hit_idx - 100)
        window_hi = hit_idx + 600
        local = np.abs(delta[window_lo:window_hi])
        local_peak = int(np.argmax(local)) + window_lo
        offset_after_attack = local_peak - hit_idx

        # Measured: post-fix offset ≈ 256 samples (envelope-follower lag at
        # fast_ms=5 ms). Pre-fix offset ≈ 388 samples (envelope lag plus
        # the causal bandpass group delay). Threshold 320 cleanly separates
        # the two regimes — fix → pass, bug → fail.
        assert 0 <= offset_after_attack < 320, (
            f"Delta peaks at sample {local_peak} (hit at {hit_idx}, "
            f"offset {offset_after_attack}). Pre-fix offset is ~388; the "
            f"causal sosfilt regression is back — #3470."
        )

    def test_silence_input_zero_output_change(self):
        """No transient in → no delta out (worst case = identity)."""
        audio = np.zeros(4096, dtype=np.float32)
        out = TransientShaper.apply(audio, SR, 60.0, 250.0, attack_boost_db=6.0)
        assert np.allclose(out, audio)
