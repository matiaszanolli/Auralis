"""
Real-time Processor
~~~~~~~~~~~~~~~~~~

Main real-time audio processor orchestrator

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import time
from threading import Lock
from typing import Any

import numpy as np

from ...utils.logging import info
from ..config import PlayerConfig
from .auto_master import AutoMasterProcessor
from .gain_smoother import AdaptiveGainSmoother
from .level_matcher import RealtimeLevelMatcher
from .performance_monitor import PerformanceMonitor


class RealtimeProcessor:
    """
    Main real-time audio processor for Auralis
    Coordinates all DSP effects and manages processing state
    """

    def __init__(self, config: PlayerConfig):
        self.config = config
        self.lock = Lock()  # Thread safety for parameter changes

        # Initialize DSP components
        self.level_matcher = RealtimeLevelMatcher(config) if config.enable_level_matching else None
        self.auto_master = AutoMasterProcessor(config) if config.enable_auto_mastering else None

        # Performance monitoring
        self.performance_monitor = PerformanceMonitor(max_cpu_usage=0.75)

        # Processing state
        self.is_processing = False
        self.effects_enabled = {
            'level_matching': config.enable_level_matching,
            'auto_mastering': config.enable_auto_mastering,
        }

        info(f"RealtimeProcessor initialized:")
        info(f"   Sample rate: {config.sample_rate} Hz")
        info(f"   Buffer size: {config.buffer_size} samples ({config.buffer_size / config.sample_rate * 1000:.1f}ms)")
        info(f"   Level matching: {'✅ Enabled' if config.enable_level_matching else '❌ Disabled'}")
        info(f"   Auto-mastering: {'✅ Enabled' if config.enable_auto_mastering else '❌ Disabled'}")

    def set_reference_audio(self, reference: np.ndarray) -> bool:
        """Set reference audio for processing"""
        with self.lock:
            success = False

            if self.level_matcher:
                success = self.level_matcher.set_reference_audio(reference)

            if success:
                info("Reference audio loaded for real-time processing")

            return success

    def set_effect_enabled(self, effect_name: str, enabled: bool) -> None:
        """Enable/disable specific effects"""
        with self.lock:
            if effect_name in self.effects_enabled:
                self.effects_enabled[effect_name] = enabled

                # Update component state
                if effect_name == 'level_matching' and self.level_matcher:
                    self.level_matcher.enabled = enabled
                elif effect_name == 'auto_mastering' and self.auto_master:
                    self.auto_master.enabled = enabled

                info(f"Effect {effect_name}: {'enabled' if enabled else 'disabled'}")

    def set_auto_master_profile(self, profile: str) -> None:
        """Set auto-mastering profile"""
        with self.lock:
            if self.auto_master:
                self.auto_master.set_profile(profile)

    def set_fingerprint(self, fingerprint: dict | None) -> None:
        """
        Set 25D fingerprint for adaptive processing.

        Args:
            fingerprint: 25D fingerprint dictionary from FingerprintService
        """
        with self.lock:
            if self.auto_master and fingerprint:
                self.auto_master.set_fingerprint(fingerprint)
                info(f"Fingerprint set for adaptive mastering")

    def process_chunk(self, audio: np.ndarray) -> np.ndarray:
        """
        Process a single audio chunk with all enabled effects

        Args:
            audio: Input audio chunk (stereo or mono)

        Returns:
            Processed audio chunk
        """
        if audio is None or len(audio) == 0:
            return audio

        start_time = time.perf_counter()

        with self.lock:
            processed = audio.copy()

            # Apply level matching first
            if self.effects_enabled.get('level_matching', False) and self.level_matcher:
                processed = self.level_matcher.process(processed)

            # Apply auto-mastering
            if self.effects_enabled.get('auto_mastering', False) and self.auto_master:
                processed = self.auto_master.process(processed)

            # Final safety limiting - intelligent soft clip to prevent harsh distortion
            # Use tanh() for smooth saturation instead of hard clipping
            max_val = np.max(np.abs(processed))
            if max_val > 0.95:  # Only limit if really needed (was 0.9, now 0.95)
                # Calculate how much we need to reduce
                target_peak = 0.98  # Leave 2% headroom (was 0.95)

                # Only apply saturation if we're going to clip
                if max_val > 1.0:
                    # Scale down first to avoid over-saturation
                    safety_gain = target_peak / max_val
                    processed = processed * safety_gain

                    # Then apply very gentle tanh() for anti-aliasing
                    # Use a gentler curve (multiply by 0.95 before tanh)
                    processed = np.tanh(processed * 0.95) / 0.95
                else:
                    # Just gentle saturation, no gain reduction needed
                    # Map [0.95, 1.0] -> [0.95, 0.98] smoothly
                    processed = np.tanh(processed / target_peak) * target_peak

        # Record performance
        processing_time = time.perf_counter() - start_time
        chunk_duration = len(audio) / self.config.sample_rate
        self.performance_monitor.record_processing_time(processing_time, chunk_duration)

        return processed

    def get_processing_info(self) -> dict[str, Any]:
        """Get comprehensive processing information"""
        with self.lock:
            info = {
                'performance': self.performance_monitor.get_stats(),
                'effects': {
                    'level_matching': self.level_matcher.get_stats() if self.level_matcher else {'enabled': False},
                    'auto_mastering': self.auto_master.get_stats() if self.auto_master else {'enabled': False},
                },
                'enabled_effects': self.effects_enabled.copy(),
                'config': {
                    'sample_rate': self.config.sample_rate,
                    'buffer_size': self.config.buffer_size,
                    'buffer_duration_ms': self.config.buffer_size / self.config.sample_rate * 1000,
                }
            }

        return info

    def reset_all_effects(self) -> None:
        """Reset all effects to initial state"""
        with self.lock:
            if self.level_matcher:
                self.level_matcher.reference_rms = None
                self.level_matcher.enabled = False
                self.level_matcher.gain_smoother = AdaptiveGainSmoother()

            if self.auto_master:
                self.auto_master.profile = "balanced"
                self.auto_master.enabled = False

            # Reset effect states
            for effect in self.effects_enabled:
                self.effects_enabled[effect] = False

            info("All effects reset to initial state")
