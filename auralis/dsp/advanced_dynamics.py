# -*- coding: utf-8 -*-

"""
Advanced Dynamics Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Intelligent compression, limiting, and dynamic range optimization

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Advanced dynamics processing with content-aware adaptation
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import threading
import time

from .unified import smooth_parameter_transition, rms
from ..utils.logging import debug


class DynamicsMode(Enum):
    """Dynamics processing modes"""
    TRANSPARENT = "transparent"      # Minimal processing, preserve dynamics
    MUSICAL = "musical"             # Musical compression, enhance groove
    BROADCAST = "broadcast"         # Consistent loudness for broadcast
    MASTERING = "mastering"         # Professional mastering chain
    ADAPTIVE = "adaptive"           # Content-aware automatic processing


@dataclass
class CompressorSettings:
    """Compressor configuration"""
    threshold_db: float = -18.0
    ratio: float = 4.0
    attack_ms: float = 10.0
    release_ms: float = 100.0
    knee_db: float = 2.0
    makeup_gain_db: float = 0.0
    enable_lookahead: bool = True
    lookahead_ms: float = 5.0


@dataclass
class LimiterSettings:
    """Limiter configuration"""
    threshold_db: float = -1.0
    release_ms: float = 50.0
    lookahead_ms: float = 5.0
    isr_enabled: bool = True  # Inter-sample peak detection
    oversampling: int = 4


@dataclass
class DynamicsSettings:
    """Complete dynamics processing settings"""
    mode: DynamicsMode = DynamicsMode.ADAPTIVE
    sample_rate: int = 44100

    # Processing chain configuration
    enable_gate: bool = True
    gate_threshold_db: float = -60.0
    gate_ratio: float = 10.0

    enable_compressor: bool = True
    compressor: CompressorSettings = None

    enable_limiter: bool = True
    limiter: LimiterSettings = None

    # Adaptive settings
    adaptation_speed: float = 0.1
    target_lufs: float = -14.0
    target_lra: float = 7.0  # Loudness Range

    def __post_init__(self):
        if self.compressor is None:
            self.compressor = CompressorSettings()
        if self.limiter is None:
            self.limiter = LimiterSettings()


class EnvelopeFollower:
    """High-quality envelope follower for dynamics processing"""

    def __init__(self, sample_rate: int, attack_ms: float, release_ms: float):
        self.sample_rate = sample_rate
        self.envelope = 0.0

        # Convert time constants to coefficients
        self.attack_coeff = np.exp(-1.0 / (attack_ms * 0.001 * sample_rate))
        self.release_coeff = np.exp(-1.0 / (release_ms * 0.001 * sample_rate))

    def process(self, input_level: float) -> float:
        """Process input level and return envelope"""
        if input_level > self.envelope:
            # Attack (faster)
            self.envelope = input_level + (self.envelope - input_level) * self.attack_coeff
        else:
            # Release (slower)
            self.envelope = input_level + (self.envelope - input_level) * self.release_coeff

        return self.envelope

    def process_buffer(self, input_levels: np.ndarray) -> np.ndarray:
        """Process entire buffer of input levels"""
        output = np.zeros_like(input_levels)

        for i, level in enumerate(input_levels):
            output[i] = self.process(level)

        return output

    def reset(self):
        """Reset envelope state"""
        self.envelope = 0.0


class AdaptiveCompressor:
    """Content-aware compressor with multiple detection modes"""

    def __init__(self, settings: CompressorSettings, sample_rate: int):
        self.settings = settings
        self.sample_rate = sample_rate

        # Initialize envelope followers
        self.peak_follower = EnvelopeFollower(sample_rate, 0.1, 1.0)  # Peak detection
        self.rms_follower = EnvelopeFollower(sample_rate, 10.0, 100.0)  # RMS detection
        self.gain_follower = EnvelopeFollower(sample_rate, settings.attack_ms, settings.release_ms)

        # Lookahead buffer (will be initialized on first use to match audio dimensions)
        if settings.enable_lookahead:
            self.lookahead_samples = int(settings.lookahead_ms * sample_rate / 1000)
            self.lookahead_buffer = None  # Will be initialized with correct shape
            self.lookahead_index = 0
        else:
            self.lookahead_buffer = None
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
            return self.peak_follower.process(peak_level)
        elif detection_mode == "rms":
            rms_level = np.sqrt(np.mean(audio ** 2))
            return self.rms_follower.process(rms_level)
        else:  # hybrid
            peak_level = np.max(np.abs(audio))
            rms_level = np.sqrt(np.mean(audio ** 2))
            # Weighted combination
            combined = 0.7 * rms_level + 0.3 * peak_level
            return combined

    def process(self, audio: np.ndarray, detection_mode: str = "rms") -> Tuple[np.ndarray, Dict[str, float]]:
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

        buffer_size = len(self.lookahead_buffer)

        if len(audio) >= buffer_size:
            # Replace buffer with end of current audio
            delayed_audio = np.concatenate([self.lookahead_buffer, audio[:-buffer_size]], axis=0)
            self.lookahead_buffer = audio[-buffer_size:].copy()
        else:
            # Partial buffer update
            delayed_audio = np.concatenate([
                self.lookahead_buffer[:len(audio)],
                audio
            ], axis=0)
            self.lookahead_buffer = np.roll(self.lookahead_buffer, -len(audio), axis=0)
            self.lookahead_buffer[-len(audio):] = audio

        return delayed_audio[:len(audio)]

    def get_current_state(self) -> Dict[str, float]:
        """Get current compressor state"""
        return {
            'gain_reduction_db': self.gain_reduction,
            'current_gain': self.previous_gain,
            'threshold_db': self.settings.threshold_db,
            'ratio': self.settings.ratio,
            'attack_ms': self.settings.attack_ms,
            'release_ms': self.settings.release_ms
        }

    def reset(self):
        """Reset compressor state"""
        self.peak_follower.reset()
        self.rms_follower.reset()
        self.gain_follower.reset()
        self.gain_reduction = 0.0
        self.previous_gain = 1.0
        if self.lookahead_buffer is not None:
            self.lookahead_buffer.fill(0)
        else:
            # Reset buffer to None so it gets re-initialized with correct shape
            self.lookahead_buffer = None


class AdaptiveLimiter:
    """Advanced lookahead limiter with ISR and oversampling"""

    def __init__(self, settings: LimiterSettings, sample_rate: int):
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

            # Apply filtering to each channel
            kernel_size = factor * 2 + 1
            kernel = np.ones(kernel_size) / kernel_size
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


class DynamicsProcessor:
    """
    Complete adaptive dynamics processing chain

    Combines gating, compression, and limiting with content-aware adaptation
    """

    def __init__(self, settings: DynamicsSettings):
        self.settings = settings
        self.sample_rate = settings.sample_rate

        # Initialize processing components
        if settings.enable_compressor:
            self.compressor = AdaptiveCompressor(settings.compressor, settings.sample_rate)
        else:
            self.compressor = None

        if settings.enable_limiter:
            self.limiter = AdaptiveLimiter(settings.limiter, settings.sample_rate)
        else:
            self.limiter = None

        # Gate (simple implementation)
        self.gate_threshold_linear = 10 ** (settings.gate_threshold_db / 20)
        self.gate_gain = 1.0

        # Adaptive state
        self.content_history = []
        self.adaptation_state = {
            'target_threshold': settings.compressor.threshold_db,
            'target_ratio': settings.compressor.ratio,
            'current_lufs': -14.0,
            'current_lra': 7.0
        }

        debug(f"Dynamics processor initialized in {settings.mode.value} mode")

    def process(self, audio: np.ndarray,
                content_info: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Process audio through complete dynamics chain

        Args:
            audio: Input audio
            content_info: Optional content analysis for adaptation

        Returns:
            Tuple of (processed_audio, dynamics_info)
        """
        if len(audio) == 0:
            return audio, {}

        processed_audio = audio.copy()
        processing_info = {}

        # Adapt parameters based on content
        if content_info and self.settings.mode == DynamicsMode.ADAPTIVE:
            self._adapt_to_content(content_info)

        # Apply gating
        if self.settings.enable_gate:
            processed_audio, gate_info = self._apply_gate(processed_audio)
            processing_info['gate'] = gate_info

        # Apply compression
        if self.compressor is not None:
            detection_mode = self._get_detection_mode(content_info)
            processed_audio, comp_info = self.compressor.process(processed_audio, detection_mode)
            processing_info['compressor'] = comp_info

        # Apply limiting
        if self.limiter is not None:
            processed_audio, limit_info = self.limiter.process(processed_audio)
            processing_info['limiter'] = limit_info

        # Update adaptation state
        self._update_adaptation_state(processed_audio, content_info)

        return processed_audio, processing_info

    def _apply_gate(self, audio: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
        """Apply noise gate"""
        level = np.sqrt(np.mean(audio ** 2))

        if level < self.gate_threshold_linear:
            # Below threshold - reduce gain
            target_gain = 1.0 / self.settings.gate_ratio
        else:
            # Above threshold - unity gain
            target_gain = 1.0

        # Smooth gain changes
        self.gate_gain = smooth_parameter_transition(self.gate_gain, target_gain, 0.1)

        gated_audio = audio * self.gate_gain

        gate_info = {
            'input_level_db': 20 * np.log10(level + 1e-10),
            'gate_gain': self.gate_gain,
            'threshold_db': self.settings.gate_threshold_db,
            'active': level < self.gate_threshold_linear
        }

        return gated_audio, gate_info

    def _get_detection_mode(self, content_info: Optional[Dict[str, Any]]) -> str:
        """Determine optimal detection mode based on content"""
        if not content_info:
            return "rms"  # Default

        genre = content_info.get('genre_info', {}).get('primary', 'pop')

        if genre in ['classical', 'jazz', 'acoustic']:
            return "rms"  # Better for musical content
        elif genre in ['electronic', 'hip_hop', 'metal']:
            return "peak"  # Better for transient-heavy content
        else:
            return "hybrid"  # Balanced approach

    def _adapt_to_content(self, content_info: Dict[str, Any]):
        """Adapt dynamics settings based on content analysis"""
        genre_info = content_info.get('genre_info', {})
        primary_genre = genre_info.get('primary', 'pop')

        dynamic_range = content_info.get('dynamic_range', 15.0)
        energy_level = content_info.get('energy_level', 'medium')

        # Adapt compression threshold based on genre and content
        if primary_genre == 'classical':
            # Lighter compression for classical
            target_threshold = -12.0
            target_ratio = 2.0
        elif primary_genre == 'electronic':
            # More aggressive for electronic
            target_threshold = -20.0
            target_ratio = 6.0
        elif primary_genre in ['rock', 'metal']:
            # Moderate compression for punch
            target_threshold = -16.0
            target_ratio = 4.0
        elif primary_genre == 'broadcast':
            # Consistent for broadcast
            target_threshold = -18.0
            target_ratio = 8.0
        else:
            # Default for pop/other
            target_threshold = -18.0
            target_ratio = 4.0

        # Adjust based on dynamic range
        if dynamic_range > 25:  # High DR - be gentler
            target_threshold -= 3.0
            target_ratio *= 0.8
        elif dynamic_range < 10:  # Low DR - be lighter
            target_threshold += 2.0
            target_ratio *= 0.7

        # Adjust based on energy level
        if energy_level == 'low':
            target_threshold += 3.0  # Higher threshold for quiet content
        elif energy_level == 'high':
            target_threshold -= 2.0  # Lower threshold for loud content

        # Smooth parameter transitions
        if self.compressor:
            current_threshold = self.compressor.settings.threshold_db
            current_ratio = self.compressor.settings.ratio

            new_threshold = smooth_parameter_transition(
                current_threshold, target_threshold, self.settings.adaptation_speed
            )
            new_ratio = smooth_parameter_transition(
                current_ratio, target_ratio, self.settings.adaptation_speed
            )

            self.compressor.settings.threshold_db = new_threshold
            self.compressor.settings.ratio = new_ratio

    def _update_adaptation_state(self, processed_audio: np.ndarray,
                                content_info: Optional[Dict[str, Any]]):
        """Update adaptation state with processed audio"""
        # Calculate current loudness metrics
        current_lufs = content_info.get('estimated_lufs', -14.0) if content_info else -14.0

        # Store in adaptation state
        self.adaptation_state['current_lufs'] = current_lufs

        # Store content info for trend analysis
        if content_info:
            self.content_history.append(content_info)
            if len(self.content_history) > 10:  # Keep last 10 frames
                self.content_history.pop(0)

    def get_processing_info(self) -> Dict[str, Any]:
        """Get complete dynamics processing information"""
        info = {
            'mode': self.settings.mode.value,
            'adaptation_state': self.adaptation_state.copy()
        }

        if self.compressor:
            info['compressor'] = self.compressor.get_current_state()

        if self.limiter:
            info['limiter'] = self.limiter.get_current_state()

        info['gate'] = {
            'threshold_db': self.settings.gate_threshold_db,
            'current_gain': self.gate_gain
        }

        return info

    def set_mode(self, mode: DynamicsMode):
        """Change dynamics processing mode"""
        self.settings.mode = mode
        debug(f"Dynamics mode changed to: {mode.value}")

    def reset(self):
        """Reset all dynamics processing state"""
        if self.compressor:
            self.compressor.reset()

        if self.limiter:
            self.limiter.reset()

        self.gate_gain = 1.0
        self.content_history.clear()

        debug("Dynamics processor reset")


def create_dynamics_processor(
    mode: DynamicsMode = DynamicsMode.ADAPTIVE,
    sample_rate: int = 44100,
    target_lufs: float = -14.0
) -> DynamicsProcessor:
    """
    Factory function to create dynamics processor

    Args:
        mode: Processing mode
        sample_rate: Audio sample rate
        target_lufs: Target loudness level

    Returns:
        Configured DynamicsProcessor
    """
    settings = DynamicsSettings(
        mode=mode,
        sample_rate=sample_rate,
        target_lufs=target_lufs
    )

    return DynamicsProcessor(settings)