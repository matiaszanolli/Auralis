# -*- coding: utf-8 -*-

"""
Adaptive Limiter
~~~~~~~~~~~~~~~~

Advanced lookahead limiter with ISR and oversampling

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Tuple

from .settings import LimiterSettings
from ...utils.logging import debug

# Use vectorized envelope follower for 40-70x speedup
try:
    from .vectorized_envelope import VectorizedEnvelopeFollower as EnvelopeFollower
except ImportError:
    # Fallback to original if vectorized version not available
    from .envelope import EnvelopeFollower
    debug("Vectorized envelope not available, using standard version")


class AdaptiveLimiter:
    """Advanced lookahead limiter with ISR and oversampling"""

    def __init__(self, settings: LimiterSettings, sample_rate: int):
        """
        Initialize adaptive limiter

        Args:
            settings: Limiter configuration
            sample_rate: Audio sample rate
        """
        self.settings = settings
        self.sample_rate = sample_rate

        # Lookahead buffer (will be initialized on first use)
        self.lookahead_samples = int(settings.lookahead_ms * sample_rate / 1000)
        self.lookahead_buffer = None

        # Gain smoothing
        self.gain_smoother = EnvelopeFollower(sample_rate, 0.1, settings.release_ms)

        # State
        self.current_gain = 1.0
        self.peak_hold = 0.0

        debug(f"Adaptive limiter initialized: {settings.threshold_db:.1f}dB threshold")

    def process(self, audio: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Process audio through limiter

        Args:
            audio: Input audio

        Returns:
            Tuple of (processed_audio, limiting_info)
        """
        if len(audio) == 0:
            return audio, {}

        # Oversample if enabled
        if self.settings.oversampling > 1:
            audio_os = self._oversample(audio)
            processed_os, limit_info = self._process_core(audio_os)
            processed_audio = self._downsample(processed_os)
        else:
            processed_audio, limit_info = self._process_core(audio)

        return processed_audio, limit_info

    def _process_core(self, audio: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
        """Core limiting processing"""
        threshold_linear = 10 ** (self.settings.threshold_db / 20)

        # Apply lookahead delay
        delayed_audio = self._apply_lookahead_delay(audio)

        # Detect peaks (including ISR if enabled)
        if self.settings.isr_enabled:
            peak_level = self._detect_isr_peaks(audio)
        else:
            peak_level = np.max(np.abs(audio))

        # Calculate required gain reduction
        if peak_level > threshold_linear:
            required_gain = threshold_linear / peak_level
        else:
            required_gain = 1.0

        # Apply gain smoothing
        smoothed_gain = self.gain_smoother.process(required_gain)
        self.current_gain = smoothed_gain

        # Apply limiting
        limited_audio = delayed_audio * smoothed_gain

        # Update peak hold
        output_peak = np.max(np.abs(limited_audio))
        self.peak_hold = max(self.peak_hold * 0.999, output_peak)  # Slow decay

        limit_info = {
            'input_peak_db': 20 * np.log10(peak_level + 1e-10),
            'output_peak_db': 20 * np.log10(output_peak + 1e-10),
            'gain_reduction_db': 20 * np.log10(smoothed_gain + 1e-10),
            'threshold_db': self.settings.threshold_db,
            'peak_hold_db': 20 * np.log10(self.peak_hold + 1e-10)
        }

        return limited_audio, limit_info

    def _apply_lookahead_delay(self, audio: np.ndarray) -> np.ndarray:
        """Apply lookahead delay"""
        # Initialize buffer on first use with correct shape
        if self.lookahead_buffer is None:
            if audio.ndim == 1:
                self.lookahead_buffer = np.zeros(self.lookahead_samples)
            else:
                self.lookahead_buffer = np.zeros((self.lookahead_samples, audio.shape[1]))

        buffer_size = len(self.lookahead_buffer)

        if len(audio) >= buffer_size:
            delayed_audio = np.concatenate([self.lookahead_buffer, audio[:-buffer_size]], axis=0)
            self.lookahead_buffer = audio[-buffer_size:].copy()
        else:
            delayed_audio = np.concatenate([self.lookahead_buffer[:len(audio)], audio], axis=0)
            self.lookahead_buffer = np.roll(self.lookahead_buffer, -len(audio), axis=0)
            self.lookahead_buffer[-len(audio):] = audio

        return delayed_audio[:len(audio)]

    def _detect_isr_peaks(self, audio: np.ndarray) -> float:
        """Detect inter-sample peaks using simple interpolation"""
        if len(audio) < 2:
            return np.max(np.abs(audio))

        # Simple linear interpolation between samples
        interpolated = (audio[:-1] + audio[1:]) / 2

        # Find maximum including interpolated points
        sample_peaks = np.max(np.abs(audio))
        interp_peaks = np.max(np.abs(interpolated))

        return max(sample_peaks, interp_peaks)

    def _oversample(self, audio: np.ndarray) -> np.ndarray:
        """Simple oversampling using zero-padding and filtering"""
        factor = self.settings.oversampling

        if audio.ndim == 1:
            # Mono audio
            oversampled = np.zeros(len(audio) * factor)
            oversampled[::factor] = audio

            # Simple anti-aliasing filter (moving average)
            kernel_size = factor * 2 + 1
            kernel = np.ones(kernel_size) / kernel_size
            filtered = np.convolve(oversampled, kernel, mode='same') * factor
        else:
            # Stereo/multi-channel audio
            oversampled = np.zeros((len(audio) * factor, audio.shape[1]))
            oversampled[::factor] = audio

            # Apply filtering to each channel using vectorized operation
            kernel_size = factor * 2 + 1
            kernel = np.ones(kernel_size) / kernel_size

            # Vectorized approach: convolve all channels at once via scipy
            try:
                from scipy import signal
                # Use scipy's efficient multi-channel convolve
                filtered = np.zeros_like(oversampled)
                for ch in range(audio.shape[1]):
                    filtered[:, ch] = signal.convolve(oversampled[:, ch], kernel, mode='same') * factor
            except ImportError:
                # Fallback to numpy if scipy unavailable
                filtered = np.zeros_like(oversampled)
                for ch in range(audio.shape[1]):
                    filtered[:, ch] = np.convolve(oversampled[:, ch], kernel, mode='same') * factor

        return filtered

    def _downsample(self, audio_os: np.ndarray) -> np.ndarray:
        """Downsample back to original rate"""
        factor = self.settings.oversampling
        return audio_os[::factor]

    def get_current_state(self) -> Dict[str, float]:
        """Get current limiter state"""
        return {
            'current_gain': self.current_gain,
            'peak_hold_db': 20 * np.log10(self.peak_hold + 1e-10),
            'threshold_db': self.settings.threshold_db,
            'lookahead_ms': self.settings.lookahead_ms
        }

    def reset(self):
        """Reset limiter state"""
        self.gain_smoother.reset()
        self.current_gain = 1.0
        self.peak_hold = 0.0
        if self.lookahead_buffer is not None:
            self.lookahead_buffer.fill(0)
        else:
            # Reset buffer to None so it gets re-initialized with correct shape
            self.lookahead_buffer = None


def create_adaptive_limiter(settings: LimiterSettings,
                            sample_rate: int) -> AdaptiveLimiter:
    """
    Factory function to create adaptive limiter

    Args:
        settings: Limiter configuration
        sample_rate: Audio sample rate

    Returns:
        Configured AdaptiveLimiter instance
    """
    return AdaptiveLimiter(settings, sample_rate)
