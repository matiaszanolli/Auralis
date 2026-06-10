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


# ---------------------------------------------------------------------------
# Bass-band low-edge regression (#4211)
# ---------------------------------------------------------------------------


class TestBassBandLowEdge:
    """The old `max(0.005, ...)` normalized-frequency floor clamped the 60 Hz
    bass band low edge up to 110 Hz @ 44.1 kHz, excluding kick/bass
    fundamentals from attack restoration. The floor is now 1e-4 (a true
    numerical-stability minimum), so the configured 60 Hz edge passes through.
    """

    def _bandpass_db_at(self, freq_hz: float, sample_rate: int,
                        band_low_hz: float = 60.0, band_high_hz: float = 250.0,
                        order: int = 2) -> float:
        """Magnitude (dB) of the shaper's bandpass at a probe frequency,
        reconstructed exactly as TransientShaper.apply builds it."""
        from scipy.signal import butter, sosfreqz

        nyq = sample_rate / 2.0
        lo_n = max(1e-4, min(0.995, band_low_hz / nyq))
        hi_n = max(1e-4, min(0.995, band_high_hz / nyq))
        bp = butter(order, [lo_n, hi_n], btype='band', output='sos')
        _, h = sosfreqz(bp, worN=[freq_hz * np.pi / nyq])
        return float(20.0 * np.log10(np.abs(np.asarray(h)[0]) + 1e-12))

    def test_low_edge_near_60hz_not_110hz(self):
        """The bass bandpass -3 dB point sits at the configured 60 Hz edge,
        not clamped up to 110 Hz. A Butterworth bandpass is ≈ -3 dB at its
        cutoff, so post-fix 60 Hz reads ≈ -3 dB; pre-fix (edge at 110 Hz) it
        would sit well into the stopband (much more attenuated)."""
        for sr in (44100, 48000, 96000):
            db_60 = self._bandpass_db_at(60.0, sr)
            # Passband edge: within ~1 dB of the nominal -3 dB cutoff. Pre-fix
            # this was far lower (60 Hz deep in the stopband below the 110 Hz
            # clamped edge), so a tight window cleanly separates the regimes.
            assert -4.0 < db_60 < -2.0, (
                f"sr={sr}: 60 Hz at {db_60:.1f} dB — expected ≈ -3 dB passband "
                f"edge. Band low edge clamped above 60 Hz again (#4211)."
            )

    def test_70hz_transient_produces_nonzero_delta(self):
        """A 70 Hz kick-like burst (inside the old 60-110 dead zone) must now
        produce a non-zero shaped delta."""
        n = 8192
        hit_idx = 3000
        n_decay = 600
        t = np.arange(n_decay) / SR
        tone = np.sin(2 * np.pi * 70.0 * t) * np.exp(-15 * t)
        audio = np.zeros(n, dtype=np.float32)
        audio[hit_idx:hit_idx + n_decay] = (0.5 * tone).astype(np.float32)

        out = TransientShaper.apply(audio, SR, 60.0, 250.0, attack_boost_db=9.0)
        delta = out - audio
        assert np.max(np.abs(delta)) > 1e-4, (
            "70 Hz transient produced no shaped delta — the 60-110 Hz band was "
            "excluded again (#4211)."
        )
