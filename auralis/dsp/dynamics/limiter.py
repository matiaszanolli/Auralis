"""
Adaptive Limiter
~~~~~~~~~~~~~~~~

Advanced lookahead limiter with ISR and oversampling

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

import numpy as np
from scipy.ndimage import maximum_filter1d

from ...utils.logging import debug
from .lookahead_buffer import LookaheadBuffer
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
        self._lookahead = LookaheadBuffer(self.lookahead_samples)

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
            processed_os, limit_info = self._process_core(audio_os, oversampling=self.settings.oversampling)
            processed_audio = self._downsample(processed_os)
        else:
            processed_audio, limit_info = self._process_core(audio)

        return processed_audio, limit_info

    def _process_core(self, audio: np.ndarray, oversampling: int = 1) -> tuple[np.ndarray, dict[str, float]]:
        """Core limiting processing with per-sample gain envelope.

        #4913: the gain curve is computed from a forward-looking peak-envelope
        window over `audio` and applied directly to that same (undelayed)
        `audio` — matching `BrickWallLimiter`'s non-causal batch convention
        (the whole buffer is already available; there is no streaming reason
        to pay lookahead as *output* latency). The previous code instead
        multiplied the gain curve into `_apply_lookahead_delay(audio)`,
        double-applying the lookahead: the gain computed from window
        [k, k+L) ended up multiplying `audio[k-L]`, not `audio[k]` — the
        limiter both missed the peaks it was supposed to catch and ducked
        unrelated material L samples early. `_apply_lookahead_delay`/
        `_lookahead` are kept as directly-tested helpers (see
        tests/regression/test_lookahead_buffer_dedup_4309.py) but are no
        longer part of this signal path.
        """
        threshold_linear = 10 ** (self.settings.threshold_db / 20)
        num_samples = len(audio)

        # Compute per-sample peak envelope using lookahead window. `oversampling`
        # scales lookahead_samples (computed at the base rate in __init__) to
        # the actual rate of `audio`, which may be the oversampled signal —
        # without this the effective lookahead was lookahead_ms / oversampling.
        peak_envelope = self._compute_peak_envelope(audio, oversampling)

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

        # Apply per-sample gain curve to the same (undelayed) audio the
        # envelope was computed from.
        if audio.ndim == 2:
            limited_audio = audio * gain_curve.reshape(-1, 1)
        else:
            limited_audio = audio * gain_curve

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

    def _compute_peak_envelope(self, audio: np.ndarray, oversampling: int = 1) -> np.ndarray:
        """Compute per-sample peak envelope with lookahead window.

        #4913: `oversampling` scales `self.lookahead_samples` (computed at the
        base sample rate in `__init__`) to the rate `audio` is actually at —
        `_process_core` may be called with the oversampled signal, and without
        this scaling the effective lookahead window was `lookahead_ms /
        oversampling` instead of the configured `lookahead_ms`.
        """
        num_samples = len(audio)
        lookahead = max(self.lookahead_samples * oversampling, 1)

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
        # #3688: dtype-match the zeros so this path doesn't latently promote
        # float32 to float64. Currently masked by VectorizedEnvelopeFollower
        # hard-coding float32 output downstream, but the local promotion is
        # still wasteful and fragile under envelope-follower substitution.
        padded = np.concatenate([abs_audio, np.zeros(lookahead, dtype=abs_audio.dtype)])
        # scipy requires -(size // 2) <= origin <= (size - 1) // 2. For even
        # `lookahead`, `+lookahead // 2` exceeds the upper bound and raises
        # ValueError('invalid origin') — use the largest legal positive
        # origin so the window still spans [i, i + lookahead).
        peak_envelope = maximum_filter1d(
            padded,
            size=lookahead,
            mode='constant',
            cval=0.0,
            origin=(lookahead - 1) // 2,
        )[:num_samples]

        return peak_envelope

    def _apply_lookahead_delay(self, audio: np.ndarray) -> np.ndarray:
        """Apply lookahead delay"""
        return self._lookahead.apply(audio)

    @property
    def lookahead_buffer(self) -> np.ndarray | None:
        """Current ring-buffer contents, or None before first use."""
        return self._lookahead.buffer

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
        """Oversample by an integer factor using a polyphase anti-imaging filter.

        #4907: the previous zero-stuff + fixed-width moving-average kernel
        algebraically reduces, at the decimation phase `_downsample` samples,
        to a 3-tap FIR with the wrong passband shape: +2.5 dB at DC and
        -7.0 dB at Nyquist — altering level and frequency response even when
        the limiter's gain curve is identically 1.0. `scipy.signal.resample_poly`
        designs a proper unity-passband-gain anti-imaging filter instead, and
        handles mono/multi-channel arrays uniformly via `axis=0`.
        """
        factor = self.settings.oversampling
        input_dtype = audio.dtype

        from scipy.signal import resample_poly
        oversampled: np.ndarray = resample_poly(audio, factor, 1, axis=0)

        return oversampled.astype(input_dtype, copy=False)

    def _downsample(self, audio_os: np.ndarray) -> np.ndarray:
        """Downsample back to the original rate using a polyphase anti-aliasing
        filter — the inverse of `_oversample` (#4907)."""
        factor = self.settings.oversampling
        input_dtype = audio_os.dtype

        from scipy.signal import resample_poly
        downsampled: np.ndarray = resample_poly(audio_os, 1, factor, axis=0)

        return downsampled.astype(input_dtype, copy=False)

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
        self._lookahead.reset()


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
