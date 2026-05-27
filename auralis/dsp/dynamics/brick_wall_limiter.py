"""
Brick-Wall Limiter
~~~~~~~~~~~~~~~~~~

True peak limiting with look-ahead for transparent peak control

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

A brick-wall limiter catches peaks above a threshold while preserving
overall loudness. Unlike peak normalization (which scales the entire signal),
a true limiter only reduces gain when peaks occur.
"""

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import maximum_filter1d


@dataclass
class BrickWallLimiterSettings:
    """Configuration for brick-wall limiter"""
    threshold_db: float = -0.5      # Ceiling level (typically -0.1 to -1.0 dBFS)
    lookahead_ms: float = 2.0        # Look-ahead time for peak detection (1-5ms typical)
    release_ms: float = 50.0         # Release time for gain reduction envelope
    sample_rate: int = 44100


class BrickWallLimiter:
    """
    True brick-wall limiter with look-ahead

    This limiter uses a look-ahead buffer to detect peaks before they occur,
    allowing it to apply gain reduction smoothly without audible artifacts.

    Key features:
    - Look-ahead peak detection (eliminates overshoot)
    - Smooth gain reduction envelope (no clicks/pops)
    - Preserves overall loudness (only reduces peaks)
    - Transparent limiting (minimal audible artifacts)

    Algorithm:
    1. Buffer audio with look-ahead delay
    2. Detect peaks in look-ahead window
    3. Calculate required gain reduction
    4. Apply smooth envelope to gain curve
    5. Multiply delayed audio by gain curve
    """

    def __init__(self, settings: BrickWallLimiterSettings):
        """
        Initialize brick-wall limiter

        Args:
            settings: Limiter configuration
        """
        self.settings = settings
        self.sample_rate = settings.sample_rate

        # Convert parameters to samples
        # #3750: clamp lookahead_samples to 1 minimum. `lookahead_ms=0`
        # (and any sub-sample-period value) computes to 0, which makes
        # `scipy.ndimage.maximum_filter1d(..., size=0, ...)` raise
        # `ValueError("incorrect filter size")`. The default
        # `lookahead_ms=2.0` masks this for normal use; a user/preset
        # disabling lookahead crashes the limiter.
        self.lookahead_samples = max(
            1, int(settings.lookahead_ms * self.sample_rate / 1000)
        )
        self.release_samples = int(settings.release_ms * self.sample_rate / 1000)

        # Threshold in linear scale
        self.threshold_linear = 10 ** (settings.threshold_db / 20)

        # Look-ahead buffer (ring buffer for efficiency)
        self.buffer_size = self.lookahead_samples * 2
        self.buffer = None
        self.buffer_pos = 0

        # Gain reduction state
        self.current_gain = 1.0

        # Release coefficient (exponential decay)
        # Formula: gain approaches 1.0 with this time constant
        self.release_coef = np.exp(-1.0 / self.release_samples) if self.release_samples > 0 else 0.0

    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply brick-wall limiting to audio

        Args:
            audio: Input audio (samples,) or (samples, channels)

        Returns:
            Limited audio with same shape as input
        """
        if len(audio) == 0:
            return audio.copy()

        # Handle mono/stereo
        is_mono = audio.ndim == 1
        if is_mono:
            audio = audio.reshape(-1, 1)

        num_samples, num_channels = audio.shape

        # --- Vectorized lookahead peak detection (fixes #2293) ---
        #
        # Original approach: O(n × lookahead) — a Python loop with an inner
        # np.max() call per sample, which is 100-500 ms/second of audio.
        #
        # New approach: O(n) sliding-window maximum via scipy.ndimage.
        #
        # Pad the abs signal so the filter sees zeros beyond the end of the
        # block (matching the original zero-padding behaviour).
        # #3658: pass dtype=audio.dtype so float32 input stays float32 — without
        # this np.zeros defaults to float64 and the vstack/multiply chain
        # silently promotes the entire pipeline output.
        abs_padded = np.abs(
            np.vstack(
                [audio, np.zeros((self.lookahead_samples, num_channels), dtype=audio.dtype)]
            )
        )
        # Collapse channels: take the per-sample maximum across all channels.
        per_sample_max = abs_padded.max(axis=1)  # shape: (num_samples + lookahead,)

        # maximum_filter1d origin convention: positive origin shifts the
        # window toward *larger* indices (future samples).  Use the largest
        # legal positive origin — (size - 1) // 2 — so the window spans
        # approximately [i, i + lookahead), giving true lookahead peak
        # detection. The previous negative origin looked *backward*,
        # defeating the purpose of the lookahead delay (fixes #3308).
        # scipy requires -(size // 2) <= origin <= (size - 1) // 2; for
        # even sizes `lookahead // 2` exceeds the upper bound and raises
        # ValueError('invalid origin').
        lookahead = self.lookahead_samples
        peak_envelope = maximum_filter1d(
            per_sample_max,
            size=lookahead,
            mode='constant',
            cval=0.0,
            origin=(lookahead - 1) // 2,
        )[:num_samples]  # trim padding tail

        # Vectorized target-gain computation: threshold / peak where above
        # threshold, else 1.0.  Clamp denominator to avoid division by zero.
        safe_envelope = np.maximum(peak_envelope, 1e-10)
        target_gains = np.where(
            peak_envelope > self.threshold_linear,
            self.threshold_linear / safe_envelope,
            1.0,
        )

        # Build the instant-attack / exponential-release gain envelope.
        gain_curve = self._release_envelope(target_gains, audio.dtype)

        # Apply gain curve to audio
        output = audio * gain_curve.reshape(-1, 1)

        # Return in same format as input
        if is_mono:
            output = output.reshape(-1)

        return output

    def _release_envelope(
        self, target_gains: np.ndarray, dtype: np.dtype
    ) -> np.ndarray:
        """
        Build the instant-attack / exponential-release gain curve (fixes #3751).

        The recurrence is sequential and nonlinear, so it has no exact
        closed-form vectorization:
            attack  (tg <  prev_gain): gain jumps instantly to tg
            release (tg >= prev_gain): gain = rc*prev_gain + (1-rc)*tg

        However, ``target_gains`` is *exactly* 1.0 wherever no limiting is
        needed and < 1.0 only at peaks. Over a maximal run of unity targets the
        recurrence collapses to a pure geometric release toward 1.0:

            gain[k] = 1 - (1 - gain_start) * rc**k

        which we fill in one vectorized shot. The scalar attack/release loop
        then runs only on the (typically sparse) limiting samples, turning the
        former ~1.3M-iteration per-sample loop into O(num_peaks) Python work.
        Exact to float precision.

        Args:
            target_gains: Per-sample target gain in (0, 1]; 1.0 == no limiting.
            dtype: Output dtype — matches the audio so the downstream
                ``audio * gain_curve`` multiply does not promote float32 to
                float64 (#3658).

        Returns:
            Gain curve of shape ``(len(target_gains),)`` in ``dtype``.

        Side effect:
            Updates ``self.current_gain`` with the final gain so consecutive
            chunk calls produce a continuous envelope (#2390: no boundary click).
        """
        num_samples = target_gains.shape[0]
        gain_curve = np.empty(num_samples, dtype=dtype)
        # Seed from self.current_gain for cross-chunk continuity (#2390).
        prev_gain = self.current_gain
        rc = self.release_coef

        # Split the block into maximal runs of "unity" (no limiting) vs
        # "limiting" samples; the state flips at these boundary indices.
        is_unity = target_gains >= 1.0
        flips = np.flatnonzero(np.diff(is_unity)) + 1
        seg_starts = np.concatenate(([0], flips))
        seg_ends = np.concatenate((flips, [num_samples]))  # exclusive bounds

        for start, end in zip(seg_starts, seg_ends):
            if is_unity[start]:
                # Vectorized geometric release toward 1.0 across the whole run.
                run_len = end - start
                k = np.arange(1, run_len + 1)
                gain_curve[start:end] = 1.0 - (1.0 - prev_gain) * (rc ** k)
                # Advance prev_gain analytically in full precision (matches the
                # iterated scalar release to float roundoff).
                prev_gain = 1.0 - (1.0 - prev_gain) * float(rc ** run_len)
            else:
                # Scalar attack/release on the limiting samples — the branch
                # depends on the running gain, so it cannot be vectorized.
                for i in range(start, end):
                    tg = target_gains[i]
                    if tg < prev_gain:
                        prev_gain = tg  # attack: instant
                    else:
                        prev_gain = prev_gain * rc + tg * (1.0 - rc)  # release
                    gain_curve[i] = prev_gain

        # Persist ending gain for the next call (cross-chunk continuity).
        self.current_gain = float(gain_curve[-1])
        return gain_curve

    def reset(self) -> None:
        """Reset limiter state (clear buffers)"""
        self.buffer = None
        self.current_gain = 1.0
        self.buffer_pos = 0


def create_brick_wall_limiter(
    threshold_db: float = -0.5,
    lookahead_ms: float = 2.0,
    release_ms: float = 50.0,
    sample_rate: int = 44100
) -> BrickWallLimiter:
    """
    Factory function to create brick-wall limiter

    Args:
        threshold_db: Ceiling level in dBFS (typically -0.1 to -1.0)
        lookahead_ms: Look-ahead time in milliseconds (1-5ms typical)
        release_ms: Release time in milliseconds (20-100ms typical)
        sample_rate: Audio sample rate

    Returns:
        Configured BrickWallLimiter instance

    Example:
        >>> limiter = create_brick_wall_limiter(threshold_db=-0.3, lookahead_ms=2.0)
        >>> limited_audio = limiter.process(audio)
    """
    settings = BrickWallLimiterSettings(
        threshold_db=threshold_db,
        lookahead_ms=lookahead_ms,
        release_ms=release_ms,
        sample_rate=sample_rate
    )
    return BrickWallLimiter(settings)


# Export public API
__all__ = [
    'BrickWallLimiter',
    'BrickWallLimiterSettings',
    'create_brick_wall_limiter'
]
