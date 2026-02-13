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

    def _calculate_gain_reduction(self, level_db: float) -> float:
        """Calculate gain reduction based on input level"""
        threshold = self.settings.threshold_db
        ratio = self.settings.ratio
        knee = self.settings.knee_db

        if level_db <= threshold - knee/2:
            # Below knee
            return 0.0
        elif level_db >= threshold + knee/2:
            # Above knee (linear compression)
            over_threshold = level_db - threshold
            return -over_threshold * (1 - 1/ratio)
        else:
            # In knee (soft compression)
            over_threshold = level_db - threshold + knee/2
            knee_ratio = over_threshold / knee
            soft_ratio = 1 + knee_ratio * (ratio - 1) / ratio
            return -over_threshold * (1 - 1/soft_ratio)

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
        Process audio through compressor

        Args:
            audio: Input audio
            detection_mode: 'peak', 'rms', or 'hybrid'

        Returns:
            Tuple of (processed_audio, compression_info)
        """
        if len(audio) == 0:
            return audio, {}

        # Handle lookahead
        if self.lookahead_buffer is not None:
            # Use lookahead for better transient handling
            delayed_audio = self._apply_lookahead(audio)
        else:
            delayed_audio = audio

        # Detect input level
        input_level = self._detect_input_level(delayed_audio, detection_mode)
        input_level_db = 20 * np.log10(input_level + 1e-10)

        # Calculate required gain reduction
        target_gain_reduction = self._calculate_gain_reduction(input_level_db)

        # Apply gain smoothing
        smoothed_gain_reduction = self.gain_follower.process(target_gain_reduction)
        self.gain_reduction = smoothed_gain_reduction

        # Convert to linear gain
        gain_linear = 10 ** (smoothed_gain_reduction / 20)

        # Apply makeup gain
        makeup_gain = 10 ** (self.settings.makeup_gain_db / 20)
        final_gain = gain_linear * makeup_gain

        # Apply gain to audio
        processed_audio = delayed_audio * final_gain
        self.previous_gain = final_gain

        # Compression info
        compression_info = {
            'input_level_db': float(input_level_db),
            'gain_reduction_db': float(smoothed_gain_reduction),
            'output_gain': float(final_gain),
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
