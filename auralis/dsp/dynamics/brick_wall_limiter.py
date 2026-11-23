"""
Brick-Wall Limiter
~~~~~~~~~~~~~~~~~~

True peak limiting with look-ahead for transparent peak control

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

A brick-wall limiter catches peaks above a threshold while preserving
overall loudness. Unlike peak normalization (which scales the entire signal),
a true limiter only reduces gain when peaks occur.
"""

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import maximum_filter1d

from ..utils.loudness_targets import LIMITER_LOOKAHEAD_MS, LIMITER_RELEASE_MS
from .limiter_ramp import ramp_gain_reduction
from auralis.dsp.constants import DEFAULT_SAMPLE_RATE
from auralis.dsp.utils.conversion import db_to_amplitude


@dataclass
class BrickWallLimiterSettings:
    """Configuration for brick-wall limiter"""
    # A generic default, deliberately not the output stage's OUTPUT_PEAK_CEILING_DB (#6635).
    threshold_db: float = -0.5      # Ceiling level (typically -0.1 to -1.0 dBFS)
    lookahead_ms: float = LIMITER_LOOKAHEAD_MS  # Look-ahead for peak detection (1-5ms typical)
    release_ms: float = LIMITER_RELEASE_MS  # Release time for the gain-reduction envelope
    sample_rate: int = DEFAULT_SAMPLE_RATE


class BrickWallLimiter:
    """
    True brick-wall limiter with look-ahead

    This limiter uses a look-ahead buffer to detect peaks before they occur,
    allowing it to apply gain reduction smoothly without audible artifacts.

    Key features:
    - Look-ahead peak detection (eliminates overshoot)
    - Gain reduction ramps linearly over the look-ahead and reaches its target
      on the peak sample, so the attack is not a one-sample step (#5699)
    - Preserves overall loudness (only reduces peaks)
    - Transparent limiting (minimal audible artifacts)

    Algorithm:
    1. Buffer audio with look-ahead delay
    2. Detect peaks in look-ahead window
    3. Calculate required gain reduction
    4. Ramp that reduction in over the look-ahead (trailing moving average)
    5. Apply the exponential release to the ramped curve
    6. Multiply audio by the gain curve
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

        self.threshold_linear = db_to_amplitude(settings.threshold_db)

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

        # --- Vectorized lookahead peak detection: an O(n) sliding-window maximum (#2293) ---
        # Per-sample max |audio| across channels, zero-padded so the filter sees
        # zeros beyond the end of the block. Built a channel at a time into the
        # padded buffer, so no full-size |audio| exists (#6717); max is exact,
        # so the values equal max(|pad(audio)|). #3658: audio.dtype throughout.
        per_sample_max = np.zeros(num_samples + self.lookahead_samples, dtype=audio.dtype)
        np.abs(audio[:, 0], out=per_sample_max[:num_samples])
        for ch in range(1, num_channels):
            np.maximum(per_sample_max[:num_samples], np.abs(audio[:, ch]), out=per_sample_max[:num_samples])

        # maximum_filter1d origin convention (#5562): a POSITIVE origin shifts
        # the window toward EARLIER samples (a post-peak hold), a NEGATIVE one
        # toward FUTURE samples. origin = -(lookahead // 2) makes the output at
        # i the max over [i, i + lookahead), i.e. a true look-ahead.
        lookahead = self.lookahead_samples
        peak_envelope = maximum_filter1d(
            per_sample_max,
            size=lookahead,
            mode='constant',
            cval=0.0,
            origin=-(lookahead // 2),
        )[:num_samples]  # trim padding tail

        # Vectorized target-gain computation: threshold / peak where above
        # threshold, else 1.0.  Clamp denominator to avoid division by zero.
        # Quotient and unity both written into the clamped envelope's buffer (#6717).
        target_gains = np.maximum(peak_envelope, 1e-10)
        np.divide(self.threshold_linear, target_gains, out=target_gains)
        target_gains[~(peak_envelope > self.threshold_linear)] = 1.0  # np.where's exact complement, NaN included
        del peak_envelope

        # Ramp the reduction in over the look-ahead (#5699), then build the
        # exponential-release gain envelope. The ramp overwrites per_sample_max.
        target_gains = ramp_gain_reduction(
            target_gains,
            per_sample_max[:num_samples],
            self.lookahead_samples,
            self.threshold_linear,
        )
        del per_sample_max  # dead from here; freed before the envelope and output (#6717)
        gain_curve = self._release_envelope(target_gains, audio.dtype)
        del target_gains

        # Apply gain curve to audio
        output: np.ndarray = audio * gain_curve.reshape(-1, 1)

        # Return in same format as input
        if is_mono:
            output = output.reshape(-1)

        return output

    def _release_envelope(
        self, target_gains: np.ndarray, dtype: np.dtype
    ) -> np.ndarray:
        """
        Build the follow-down / exponential-release gain curve (fixes #3751).

        ``target_gains`` is already ramped by ``_ramp_attack`` (#5699), so
        "following down" is not a step. The recurrence is sequential and nonlinear, so it has no exact
        closed-form vectorization:
            attack  (tg <  prev_gain): gain follows tg down
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
                # 1 - (1 - g) * rc**k through one float64 buffer, the same values (#6717).
                run_len = end - start
                release = np.arange(1, run_len + 1, dtype=np.float64)
                np.power(rc, release, out=release)
                release *= 1.0 - prev_gain
                np.subtract(1.0, release, out=gain_curve[start:end], casting='same_kind')
                # Advance prev_gain analytically in full precision (matches the
                # iterated scalar release to float roundoff).
                prev_gain = 1.0 - (1.0 - prev_gain) * float(rc ** run_len)
            else:
                # Scalar attack/release on the limiting samples — the branch
                # depends on the running gain, so it cannot be vectorized.
                for i in range(start, end):
                    tg = target_gains[i]
                    if tg < prev_gain:
                        prev_gain = tg  # attack: follow the ramped target
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
    sample_rate: int,
    threshold_db: float = -0.5,
    lookahead_ms: float = 2.0,
    release_ms: float = 50.0,
) -> BrickWallLimiter:
    """
    Factory function to create brick-wall limiter

    Args:
        sample_rate: Audio sample rate. Required (#4622) — a missing/wrong
            value silently mis-tunes look-ahead/release timing for the
            actual audio, with no error and no cue at the call site.
        threshold_db: Ceiling level in dBFS (typically -0.1 to -1.0)
        lookahead_ms: Look-ahead time in milliseconds (1-5ms typical)
        release_ms: Release time in milliseconds (20-100ms typical)

    Returns:
        Configured BrickWallLimiter instance

    Example:
        >>> limiter = create_brick_wall_limiter(44100, threshold_db=-0.3, lookahead_ms=2.0)
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
