"""
Adaptive Limiter
~~~~~~~~~~~~~~~~

Advanced lookahead limiter with ISR and oversampling

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, cast

import numpy as np
from scipy.ndimage import maximum_filter1d

from ...utils.logging import debug
from .settings import LimiterSettings

# Use vectorized envelope follower for 40-70x speedup
EnvelopeFollower: Any  # Will be assigned below
try:
    from .vectorized_envelope import VectorizedEnvelopeFollower as EnvelopeFollower
except ImportError:
    # Fallback to original if vectorized version not available
    from .envelope import EnvelopeFollower
    debug("Vectorized envelope not available, using standard version")


class AdaptiveLimiter:
    """Advanced lookahead limiter with ISR and oversampling"""

    def __init__(self, settings: LimiterSettings, sample_rate: int) -> None:
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
        self.lookahead_buffer: np.ndarray | None = None

        # Gain smoothing — for gain curves the signal drops when limiting
        # (opposite of audio peaks), so swap attack/release: the "release"
        # coeff drives fast gain reduction, "attack" coeff drives slow recovery.
        self.gain_smoother = EnvelopeFollower(sample_rate, settings.release_ms, 0.1)

        # State
        self.current_gain = 1.0
        self.peak_hold = 0.0

        debug(f"Adaptive limiter initialized: {settings.threshold_db:.1f}dB threshold")

    def process(self, audio: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
        """
        Process audio through limiter

        Args:
            audio: Input audio

        Returns:
            Tuple of (processed_audio, limiting_info)
        """
        if len(audio) == 0:
            return audio.copy(), {}

        # Oversample if enabled
        if self.settings.oversampling > 1:
            audio_os = self._oversample(audio)
            processed_os, limit_info = self._process_core(audio_os)
            processed_audio = self._downsample(processed_os)
        else:
            processed_audio, limit_info = self._process_core(audio)

        return processed_audio, limit_info

    def _process_core(self, audio: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
        """Core limiting processing with per-sample gain envelope"""
        threshold_linear = 10 ** (self.settings.threshold_db / 20)
        num_samples = len(audio)

        # Apply lookahead delay
        delayed_audio = self._apply_lookahead_delay(audio)

        # Compute per-sample peak envelope using lookahead window
        peak_envelope = self._compute_peak_envelope(audio)

        # Per-sample target gains: reduce only where peaks exceed threshold
        safe_envelope = np.maximum(peak_envelope, 1e-10)
        target_gains = np.where(
            peak_envelope > threshold_linear,
            threshold_linear / safe_envelope,
            1.0,
        )

        # Smooth gains with attack/release envelope
        gain_curve = self.gain_smoother.process_buffer(target_gains)
        self.current_gain = float(gain_curve[-1]) if num_samples > 0 else self.current_gain

        # Apply per-sample gain curve
        if audio.ndim == 2:
            limited_audio = delayed_audio * gain_curve.reshape(-1, 1)
        else:
            limited_audio = delayed_audio * gain_curve

        # Update peak hold
        peak_level = float(np.max(peak_envelope))
        output_peak = float(np.max(np.abs(limited_audio)))
        self.peak_hold = max(self.peak_hold * 0.999, output_peak)

        min_gain = float(np.min(gain_curve)) if num_samples > 0 else 1.0
        limit_info = {
            'input_peak_db': 20 * np.log10(peak_level + 1e-10),
            'output_peak_db': 20 * np.log10(output_peak + 1e-10),
            'gain_reduction_db': 20 * np.log10(min_gain + 1e-10),
            'threshold_db': self.settings.threshold_db,
            'peak_hold_db': 20 * np.log10(self.peak_hold + 1e-10)
        }

        return limited_audio, limit_info

    def _compute_peak_envelope(self, audio: np.ndarray) -> np.ndarray:
        """Compute per-sample peak envelope with lookahead window"""
        num_samples = len(audio)
        lookahead = max(self.lookahead_samples, 1)

        # Get per-sample absolute values, collapsing channels
        if audio.ndim == 2:
            abs_audio = np.max(np.abs(audio), axis=1)
        else:
            abs_audio = np.abs(audio)

        # Include ISR interpolated peaks if enabled
        if self.settings.isr_enabled and num_samples >= 2:
            interpolated = np.abs((audio[:-1] + audio[1:]) / 2)
            if audio.ndim == 2:
                interp_max = np.max(interpolated, axis=1)
            else:
                interp_max = interpolated
            # Take maximum of sample and interpolated peaks
            abs_audio[:-1] = np.maximum(abs_audio[:-1], interp_max)

        # Pad for lookahead and compute sliding-window maximum.
        # maximum_filter1d origin convention: positive origin shifts the
        # window toward *larger* indices (future samples).  With
        # origin=+(lookahead // 2) the window spans approximately
        # [i, i + lookahead), giving true lookahead peak detection.
        # The previous negative origin looked *backward*, defeating the
        # purpose of the lookahead delay (mirrors BrickWallLimiter fix #3308).
        padded = np.concatenate([abs_audio, np.zeros(lookahead)])
        peak_envelope = maximum_filter1d(
            padded,
            size=lookahead,
            mode='constant',
            cval=0.0,
            origin=+(lookahead // 2),
        )[:num_samples]

        return peak_envelope

    def _apply_lookahead_delay(self, audio: np.ndarray) -> np.ndarray:
        """Apply lookahead delay"""
        # Initialize buffer — mirror-pad to avoid zero-sample artifact (#3291)
        if self.lookahead_buffer is None:
            if audio.ndim == 1:
                pad = audio[:self.lookahead_samples]
                self.lookahead_buffer = np.pad(pad, (self.lookahead_samples - len(pad), 0), mode='reflect')
            else:
                pad = audio[:self.lookahead_samples]
                deficit = self.lookahead_samples - len(pad)
                self.lookahead_buffer = np.pad(pad, ((deficit, 0), (0, 0)), mode='reflect')

        # Buffer is guaranteed to be non-None after initialization
        buffer_size = self.lookahead_buffer.shape[0]
        audio_len = len(audio)

        if audio_len >= buffer_size:
            delayed_audio = np.concatenate([self.lookahead_buffer, audio[:-buffer_size]], axis=0)
            self.lookahead_buffer = audio[-buffer_size:].copy()
        else:
            delayed_audio = np.concatenate([
                self.lookahead_buffer[:audio_len],
                audio
            ], axis=0)
            self.lookahead_buffer = np.roll(self.lookahead_buffer, -audio_len, axis=0)
            self.lookahead_buffer[-audio_len:, ...] = audio

        return cast(np.ndarray, delayed_audio[:audio_len])

    def _detect_isr_peaks(self, audio: np.ndarray) -> float:
        """Detect inter-sample peaks using simple interpolation"""
        if len(audio) < 2:
            return float(np.max(np.abs(audio)))

        # Simple linear interpolation between samples
        interpolated = (audio[:-1] + audio[1:]) / 2

        # Find maximum including interpolated points
        sample_peaks = float(np.max(np.abs(audio)))
        interp_peaks = float(np.max(np.abs(interpolated)))

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

    def get_current_state(self) -> dict[str, float]:
        """Get current limiter state"""
        return {
            'current_gain': self.current_gain,
            'peak_hold_db': 20 * np.log10(self.peak_hold + 1e-10),
            'threshold_db': self.settings.threshold_db,
            'lookahead_ms': self.settings.lookahead_ms
        }

    def reset(self) -> None:
        """Reset limiter state"""
        self.gain_smoother.reset()
        self.current_gain = 1.0
        self.peak_hold = 0.0
        if self.lookahead_buffer is not None:
            self.lookahead_buffer.fill(0)


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
