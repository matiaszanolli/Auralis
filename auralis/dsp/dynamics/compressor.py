"""
Adaptive Compressor
~~~~~~~~~~~~~~~~~~~

Content-aware compressor with multiple detection modes

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, cast

import numpy as np

from ...utils.logging import debug
from .settings import CompressorSettings

# Use vectorized envelope follower for 40-70x speedup
EnvelopeFollower: Any  # Will be assigned below
try:
    from .vectorized_envelope import VectorizedEnvelopeFollower as EnvelopeFollower
except ImportError:
    # Fallback to original if vectorized version not available
    from .envelope import EnvelopeFollower
    debug("Vectorized envelope not available, using standard version")


class AdaptiveCompressor:
    """Content-aware compressor with multiple detection modes"""

    def __init__(self, settings: CompressorSettings, sample_rate: int) -> None:
        """
        Initialize adaptive compressor

        Args:
            settings: Compressor configuration
            sample_rate: Audio sample rate
        """
        self.settings = settings
        self.sample_rate = sample_rate

        # Initialize envelope followers
        self.peak_follower = EnvelopeFollower(sample_rate, 0.1, 1.0)  # Peak detection
        self.rms_follower = EnvelopeFollower(sample_rate, 10.0, 100.0)  # RMS detection
        self.gain_follower = EnvelopeFollower(sample_rate, settings.attack_ms, settings.release_ms)

        # Lookahead buffer (will be initialized on first use to match audio dimensions)
        self.lookahead_buffer: np.ndarray | None = None
        if settings.enable_lookahead:
            self.lookahead_samples = int(settings.lookahead_ms * sample_rate / 1000)
        else:
            self.lookahead_samples = 0

        # State variables
        self.gain_reduction = 0.0
        self.previous_gain = 1.0

        debug(f"Adaptive compressor initialized: {settings.ratio:.1f}:1, {settings.threshold_db:.1f}dB")

    def _calculate_gain_reduction_vectorized(self, levels_db: np.ndarray) -> np.ndarray:
        """Calculate gain reduction for an array of input levels (pure NumPy, no Python loop).

        Replaces the previous np.vectorize wrapper for ~10-50x speedup (fixes #2596).
        """
        threshold = self.settings.threshold_db
        ratio = self.settings.ratio
        knee = self.settings.knee_db
        half_knee = knee / 2

        gain_reduction = np.zeros_like(levels_db)

        # Above knee: linear compression
        above_knee = levels_db >= threshold + half_knee
        over_threshold_above = levels_db[above_knee] - threshold
        gain_reduction[above_knee] = -over_threshold_above * (1 - 1 / ratio)

        # In knee: soft compression (quadratic interpolation)
        in_knee = (levels_db > threshold - half_knee) & ~above_knee
        over_threshold_knee = levels_db[in_knee] - threshold + half_knee
        knee_ratio = over_threshold_knee / knee
        soft_ratio = 1 + knee_ratio * (ratio - 1) / ratio
        gain_reduction[in_knee] = -over_threshold_knee * (1 - 1 / soft_ratio)

        # Below knee: gain_reduction stays 0.0 (already initialized)
        return gain_reduction

    def _detect_input_level(self, audio: np.ndarray, detection_mode: str = "rms") -> float:
        """Detect input level using specified mode"""
        if detection_mode == "peak":
            peak_level = np.max(np.abs(audio))
            return float(self.peak_follower.process(peak_level))
        elif detection_mode == "rms":
            rms_level = np.sqrt(np.mean(audio ** 2))
            return float(self.rms_follower.process(rms_level))
        else:  # hybrid
            peak_level = np.max(np.abs(audio))
            rms_level = np.sqrt(np.mean(audio ** 2))
            # Weighted combination
            combined = 0.7 * rms_level + 0.3 * peak_level
            return float(combined)

    def process(self, audio: np.ndarray, detection_mode: str = "rms") -> tuple[np.ndarray, dict[str, float]]:
        """
        Process audio through compressor with per-sample gain envelope.

        Uses the envelope follower to compute sample-by-sample gain reduction
        instead of applying a single gain to the entire chunk, preventing
        audible pumping artifacts (#2214).

        Args:
            audio: Input audio
            detection_mode: 'peak', 'rms', or 'hybrid'

        Returns:
            Tuple of (processed_audio, compression_info)
        """
        if len(audio) == 0:
            return audio, {}

        # Handle lookahead — check the settings flag instead of the buffer,
        # since the buffer is lazily initialized inside _apply_lookahead() (fixes #2592).
        if self.settings.enable_lookahead and self.lookahead_samples > 0:
            delayed_audio = self._apply_lookahead(audio)
        else:
            delayed_audio = audio

        # Compute per-sample input levels for the gain envelope (#2214).
        # Mono: use absolute value; stereo: max across channels.
        if delayed_audio.ndim == 1:
            sample_levels = np.abs(delayed_audio)
        else:
            sample_levels = np.max(np.abs(delayed_audio), axis=1)

        # Convert to dB
        sample_levels_db = 20 * np.log10(sample_levels + 1e-10)

        # Pure NumPy vectorized gain reduction per sample (fixes #2596)
        target_gain_reduction = self._calculate_gain_reduction_vectorized(sample_levels_db)

        # Smooth gain reduction with the envelope follower (per-sample)
        smoothed_gain_reduction = self.gain_follower.process_buffer(
            target_gain_reduction.astype(np.float32)
        )

        # Track average reduction for reporting
        avg_reduction = float(np.mean(smoothed_gain_reduction))
        self.gain_reduction = avg_reduction

        # Convert to linear gain
        gain_envelope = np.power(10.0, smoothed_gain_reduction / 20.0)

        # Apply makeup gain
        makeup_gain = 10 ** (self.settings.makeup_gain_db / 20)
        gain_envelope = gain_envelope * makeup_gain

        # Apply per-sample gain to audio
        if delayed_audio.ndim == 2:
            processed_audio = delayed_audio * gain_envelope[:, np.newaxis]
        else:
            processed_audio = delayed_audio * gain_envelope

        self.previous_gain = float(gain_envelope[-1])

        # Average input level for reporting
        avg_input_db = float(np.mean(sample_levels_db))

        compression_info = {
            'input_level_db': avg_input_db,
            'gain_reduction_db': avg_reduction,
            'output_gain': float(gain_envelope[-1]),
            'threshold_db': self.settings.threshold_db,
            'ratio': self.settings.ratio
        }

        return processed_audio, compression_info

    def _apply_lookahead(self, audio: np.ndarray) -> np.ndarray:
        """Apply lookahead delay for better transient handling"""
        if self.lookahead_samples == 0:
            return audio

        # Initialize buffer on first use with correct shape
        if self.lookahead_buffer is None:
            if audio.ndim == 1:
                self.lookahead_buffer = np.zeros(self.lookahead_samples)
            else:
                self.lookahead_buffer = np.zeros((self.lookahead_samples, audio.shape[1]))

        # Buffer is guaranteed to be non-None after initialization
        buffer_size = self.lookahead_buffer.shape[0]
        audio_len = len(audio)

        if audio_len >= buffer_size:
            # Replace buffer with end of current audio
            delayed_audio = np.concatenate([self.lookahead_buffer, audio[:-buffer_size]], axis=0)
            self.lookahead_buffer = audio[-buffer_size:].copy()
        else:
            # Partial buffer update
            delayed_audio = np.concatenate([
                self.lookahead_buffer[:audio_len],
                audio
            ], axis=0)
            self.lookahead_buffer = np.roll(self.lookahead_buffer, -audio_len, axis=0)
            self.lookahead_buffer[-audio_len:, ...] = audio

        return cast(np.ndarray, delayed_audio[:audio_len])

    def get_current_state(self) -> dict[str, float]:
        """Get current compressor state"""
        return {
            'gain_reduction_db': self.gain_reduction,
            'current_gain': self.previous_gain,
            'threshold_db': self.settings.threshold_db,
            'ratio': self.settings.ratio,
            'attack_ms': self.settings.attack_ms,
            'release_ms': self.settings.release_ms
        }

    def reset(self) -> None:
        """Reset compressor state"""
        self.peak_follower.reset()
        self.rms_follower.reset()
        self.gain_follower.reset()
        self.gain_reduction = 0.0
        self.previous_gain = 1.0
        if self.lookahead_buffer is not None:
            self.lookahead_buffer.fill(0)


def create_adaptive_compressor(settings: CompressorSettings,
                               sample_rate: int) -> AdaptiveCompressor:
    """
    Factory function to create adaptive compressor

    Args:
        settings: Compressor configuration
        sample_rate: Audio sample rate

    Returns:
        Configured AdaptiveCompressor instance
    """
    return AdaptiveCompressor(settings, sample_rate)
