# -*- coding: utf-8 -*-

"""
Advanced Dynamics Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Intelligent compression, limiting, and dynamic range optimization

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Advanced dynamics processing with content-aware adaptation
"""

from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..utils.logging import debug

# Import from refactored modules
from .dynamics import (
    AdaptiveCompressor,
    AdaptiveLimiter,
    CompressorSettings,
    DynamicsMode,
    DynamicsSettings,
    EnvelopeFollower,
    LimiterSettings,
)
from .unified import rms, smooth_parameter_transition

# Re-export for backward compatibility
__all__ = [
    'DynamicsMode', 'CompressorSettings', 'LimiterSettings', 'DynamicsSettings',
    'EnvelopeFollower', 'AdaptiveCompressor', 'AdaptiveLimiter',
    'DynamicsProcessor', 'create_dynamics_processor'
]


class DynamicsProcessor:
    """
    Complete adaptive dynamics processing chain

    Combines gating, compression, and limiting with content-aware adaptation
    """

    def __init__(self, settings: DynamicsSettings):
        """
        Initialize dynamics processor

        Args:
            settings: Dynamics processing configuration
        """
        self.settings = settings
        self.sample_rate = settings.sample_rate

        # Initialize processing components
        if settings.enable_compressor and settings.compressor is not None:
            self.compressor: Optional[AdaptiveCompressor] = AdaptiveCompressor(settings.compressor, settings.sample_rate)
        else:
            self.compressor = None

        if settings.enable_limiter and settings.limiter is not None:
            self.limiter: Optional[AdaptiveLimiter] = AdaptiveLimiter(settings.limiter, settings.sample_rate)
        else:
            self.limiter = None

        # Gate (simple implementation)
        self.gate_threshold_linear = 10 ** (settings.gate_threshold_db / 20)
        self.gate_gain = 1.0

        # Adaptive state
        self.content_history: list[Dict[str, Any]] = []
        threshold_db = settings.compressor.threshold_db if settings.compressor else -18.0
        ratio = settings.compressor.ratio if settings.compressor else 4.0
        self.adaptation_state = {
            'target_threshold': threshold_db,
            'target_ratio': ratio,
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

    def _adapt_to_content(self, content_info: Dict[str, Any]) -> None:
        """Adapt dynamics settings based on content analysis and processing targets"""
        # Check if we have processing targets from AdaptiveTargetGenerator
        processing_targets = content_info.get('processing_targets', {})

        # If targets provide compression_ratio, use it; otherwise use genre-based adaptation
        if 'compression_ratio' in processing_targets:
            # Use targets from preset-aware adaptive system
            target_ratio = processing_targets['compression_ratio']

            # Calculate threshold based on ratio (higher ratio = lower threshold)
            # Map ratio (1.5-4.0) to threshold (-12 to -20)
            target_threshold = -12.0 - (target_ratio - 1.5) * 3.2

            debug(f"Using preset targets: ratio={target_ratio:.1f}:1, threshold={target_threshold:.1f}dB")
        else:
            # Fall back to genre-based adaptation
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

            # Calculate automatic makeup gain
            # Standard formula: makeup_gain = |threshold| * (1 - 1/ratio)
            # This compensates for the gain reduction caused by compression
            auto_makeup_gain = abs(new_threshold) * (1 - 1/new_ratio)
            self.compressor.settings.makeup_gain_db = auto_makeup_gain

            debug(f"Auto makeup gain: {auto_makeup_gain:.2f}dB (threshold={new_threshold:.1f}dB, ratio={new_ratio:.1f}:1)")

    def _update_adaptation_state(self, processed_audio: np.ndarray,
                                content_info: Optional[Dict[str, Any]]) -> None:
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

    def set_mode(self, mode: DynamicsMode) -> None:
        """Change dynamics processing mode"""
        self.settings.mode = mode
        debug(f"Dynamics mode changed to: {mode.value}")

    def reset(self) -> None:
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
