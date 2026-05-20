"""
Transient Shaper
~~~~~~~~~~~~~~~~

Per-band attack restoration. Detects transient onsets in a frequency band and
applies a level-independent gain envelope that emphasizes attacks (and
optionally suppresses sustain). Operates like SPL Transient Designer or Native
Instruments Transient Master.

Use case: compressed bass instruments where the kick drum's energy is still
present but its attack has been levelled by the compression. The fundamentals
of the kick are still there — the *transient* of the beater hitting the head
has been smoothed out. This stage restores the attack without re-adding peaks
that the dynamic range would normally allow.

Algorithm (per band):
    1. Bandpass the signal to isolate the target frequency range.
    2. Compute two envelope followers:
         fast_env — short attack (~5 ms), short release (~30 ms)
         slow_env — long attack (~50 ms), longer release (~150 ms)
    3. attack_env = max(0, fast_env - slow_env), normalized by slow_env
       (positive only where the fast envelope is leaping ahead of the slow one
       — exactly the moment of a transient onset).
    4. gain_env = 1.0 + attack_amount × attack_env
    5. Apply the gain envelope to the BAND, then add the *modified band minus
       the original band* back to the dry signal (parallel pattern).

The parallel addition means we never replace any of the original signal, only
add the transient-boosted delta on top. Worst case (no transients detected) the
output equals the input.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from scipy.signal import butter, sosfilt


class TransientShaper:
    """Per-band attack restoration via fast/slow envelope differential."""

    @staticmethod
    def apply(
        audio: np.ndarray,
        sample_rate: int,
        band_low_hz: float,
        band_high_hz: float,
        attack_boost_db: float,
        fast_ms: float = 5.0,
        slow_ms: float = 50.0,
        order: int = 2,
    ) -> np.ndarray:
        """
        Restore attack transients in a frequency band.

        Args:
            audio: Stereo (channels, samples) or mono (samples,)
            sample_rate: Sample rate in Hz
            band_low_hz: Lower bound of the band to shape (e.g. 60 Hz for kick)
            band_high_hz: Upper bound (e.g. 250 Hz for kick)
            attack_boost_db: Maximum boost applied at peak attack moments.
                3 dB is subtle, 6 dB is obvious, 9 dB is dramatic. The actual
                boost at any sample scales with the strength of the detected
                transient — quiet sections see ~0 dB lift.
            fast_ms: Fast envelope time constant. Should be shorter than typical
                attack times you want to preserve (5 ms catches drum hits).
            slow_ms: Slow envelope time constant. Should be longer than typical
                attack times but shorter than typical decay times (50 ms tracks
                the overall band level).
            order: Bandpass filter order (default 2, gentle slope).

        Returns:
            Audio with shaped transients, same shape and dtype as input.
        """
        if attack_boost_db <= 0.05:
            return audio

        nyq = sample_rate / 2.0
        lo_n = max(0.005, min(0.995, band_low_hz / nyq))
        hi_n = max(0.005, min(0.995, band_high_hz / nyq))
        if lo_n >= hi_n:
            return audio

        bp = butter(order, [lo_n, hi_n], btype='band', output='sos')
        axis = -1 if audio.ndim > 1 else 0

        # Extract band; preserve dtype (sosfilt returns float64, same issue
        # as ParallelEQUtilities / HarmonicExciter).
        band = np.asarray(sosfilt(bp, audio, axis=axis), dtype=audio.dtype)

        # Envelope detector: one-pole low-pass on |band|. The time constant
        # determines how fast the envelope follows. Same fast/slow envelopes
        # ride on a per-channel basis so stereo timing is preserved.
        rect = np.abs(band)

        def _onepole(x: np.ndarray, tau_ms: float) -> np.ndarray:
            """One-pole low-pass with time constant tau (ms). Causal IIR."""
            alpha = float(np.exp(-1.0 / (sample_rate * tau_ms / 1000.0)))
            sos = np.array([[1.0 - alpha, 0.0, 0.0, 1.0, -alpha, 0.0]])
            return np.asarray(sosfilt(sos, x, axis=axis), dtype=x.dtype)

        fast_env = _onepole(rect, fast_ms)
        slow_env = _onepole(rect, slow_ms)

        # Attack envelope: positive only where fast > slow (i.e. fast envelope
        # is leaping ahead of the slow one). Normalized by slow envelope so
        # the metric is scale-independent — a quiet transient gets the same
        # *relative* boost as a loud one.
        eps = np.asarray(1e-9, dtype=audio.dtype)
        diff = fast_env - slow_env
        # Soft-clamp to [0, 1]: ratio of (fast-slow)/slow, then squash.
        ratio = np.maximum(diff, 0) / np.maximum(slow_env, eps)
        # tanh squash so very loud transients don't get unbounded boost.
        attack_strength = np.tanh(ratio.astype(audio.dtype))

        boost_linear = 10.0 ** (attack_boost_db / 20.0) - 1.0  # Δ above unity
        gain_envelope = 1.0 + boost_linear * attack_strength

        # Apply gain envelope to the band, then add the *delta* (modified band
        # minus original band) to the dry signal. Parallel pattern: dry signal
        # is never touched, only augmented with extra transient energy.
        shaped_band = band * gain_envelope.astype(audio.dtype)
        delta = (shaped_band - band).astype(audio.dtype)

        return (audio + delta).astype(audio.dtype)
