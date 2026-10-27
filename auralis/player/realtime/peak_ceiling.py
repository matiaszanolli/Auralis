"""
Streaming peak ceiling
~~~~~~~~~~~~~~~~~~~~~~

Zero-latency peak limiter whose gain envelope is carried across buffers (#5721)

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

The real-time chain used to hold its peak ceiling with ``ceiling / max(|buffer|)``
applied to the whole buffer. That gain is constant inside a buffer and
independent between buffers, so it stepped at every boundary where one buffer
exceeded the ceiling and its neighbour did not (zipper clicks).

``StreamingPeakCeiling`` replaces it with a per-sample envelope:

* **Attack** is the smoothest gain that still never exceeds the ceiling:
  ``g[n] = min over m >= n of (cap[m] + attack_slope * (m - n))`` where
  ``cap[m] = min(1, ceiling / |x[m]|)``. A peak ``k`` samples into the buffer
  is approached by a ramp of slope ``attack_slope`` instead of a step. Nothing
  is delayed, so a buffer that *opens* with an over-ceiling sample still has to
  step to its cap on that sample — the ceiling takes precedence over smoothness.
* **Release** is slope-limited and seeded from the previous buffer's final gain,
  so leaving a limited buffer recovers over ``release_ms`` instead of snapping
  back to unity.

Both passes are running minima, so the whole envelope is vectorised.
"""

import threading

import numpy as np

_TINY = 1e-12


class StreamingPeakCeiling:
    """Peak limiter with a gain envelope that persists across ``apply`` calls."""

    def __init__(self, sample_rate: int = 44100,
                 lookahead_ms: float = 2.0, release_ms: float = 50.0) -> None:
        self.lookahead_ms = lookahead_ms
        self.release_ms = release_ms
        self.current_gain = 1.0
        # Leaf lock: the envelope is read-modify-write state, and the safety
        # stage in RealtimeProcessor runs outside the processor's own lock.
        self._lock = threading.Lock()
        self.sample_rate = 0
        self.set_sample_rate(sample_rate)

    def set_sample_rate(self, sample_rate: int) -> None:
        """Re-derive the per-sample slopes so the ramp times hold at any rate."""
        if sample_rate == self.sample_rate:
            return
        self.sample_rate = sample_rate
        self._attack_slope = 1.0 / max(1.0, self.lookahead_ms * sample_rate / 1000.0)
        self._release_slope = 1.0 / max(1.0, self.release_ms * sample_rate / 1000.0)

    def reset(self) -> None:
        with self._lock:
            self.current_gain = 1.0

    def apply(self, audio: np.ndarray, ceiling: float) -> np.ndarray:
        """Return ``audio`` with every |sample| held at or below ``ceiling``.

        Non-finite samples do not drive the gain (they are left for the
        caller's finite-value guard), shape and dtype are preserved.
        """
        if audio.size == 0 or ceiling <= 0:
            return audio

        peaks = np.abs(audio) if audio.ndim == 1 else np.abs(audio).max(axis=1)
        peaks = np.where(np.isfinite(peaks), peaks, 0.0).astype(np.float64)
        cap = np.minimum(1.0, ceiling / np.maximum(peaks, _TINY))

        idx = np.arange(len(cap), dtype=np.float64)
        with self._lock:
            if self.current_gain >= 1.0 and float(peaks.max()) <= ceiling:
                return audio  # idle: exactly unity, no rounding drift
            # Attack: reverse running minimum of cap[m] + s*m, minus s*n.
            attack = self._attack_slope * idx
            ahead = np.minimum.accumulate((cap + attack)[::-1])[::-1] - attack
            # Release: forward running minimum seeded with the carried gain.
            release = self._release_slope * idx
            gain = np.minimum(
                self.current_gain + self._release_slope,
                np.minimum.accumulate(ahead - release),
            ) + release
            gain = np.minimum(gain, 1.0)
            self.current_gain = float(gain[-1])
        shaped = gain.astype(audio.dtype)
        limited: np.ndarray = audio * (shaped if audio.ndim == 1 else shaped[:, np.newaxis])
        return limited
