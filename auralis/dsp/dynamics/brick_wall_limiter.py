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
        self.lookahead_samples = int(settings.lookahead_ms * self.sample_rate / 1000)
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
            return audio

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
        abs_padded = np.abs(
            np.vstack([audio, np.zeros((self.lookahead_samples, num_channels))])
        )
        # Collapse channels: take the per-sample maximum across all channels.
        per_sample_max = abs_padded.max(axis=1)  # shape: (num_samples + lookahead,)

        # maximum_filter1d with a negative origin shifts the window forward so
        # it looks *ahead* rather than centred on the current sample.
        # origin = -(size // 2) places the right edge of the window at the
        # current sample, i.e. the window spans [i, i + lookahead_samples).
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
        safe_envelope = np.maximum(peak_envelope, 1e-10)
        target_gains = np.where(
            peak_envelope > self.threshold_linear,
            self.threshold_linear / safe_envelope,
            1.0,
        )

        # Release envelope is inherently recurrent (each sample depends on the
        # previous gain), so a loop is unavoidable here.  However it now has
        # NO inner NumPy call — it's pure scalar arithmetic, which is ~10×
        # faster than the previous O(n × lookahead) loop.
        gain_curve = np.empty(num_samples)
        # Seed from self.current_gain so consecutive chunk calls produce a
        # continuous gain envelope (fixes #2390: audible click at boundaries).
        prev_gain = self.current_gain
        rc = self.release_coef
        for i in range(num_samples):
            tg = target_gains[i]
            if tg < prev_gain:
                # Attack: instant
                prev_gain = tg
            else:
                # Release: exponential decay back toward 1.0
                prev_gain = prev_gain * rc + tg * (1.0 - rc)
            gain_curve[i] = prev_gain

        # Persist ending gain for the next call (cross-chunk continuity).
        self.current_gain = float(gain_curve[-1])

        # Apply gain curve to audio
        output = audio * gain_curve.reshape(-1, 1)

        # Return in same format as input
        if is_mono:
            output = output.reshape(-1)

        return output

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
