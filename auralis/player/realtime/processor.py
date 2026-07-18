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
                    self.level_matcher.set_enabled(enabled)
                elif effect_name == 'auto_mastering' and self.auto_master:
                    self.auto_master.set_enabled(enabled)

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

    def process_chunk(self, audio: np.ndarray, sample_rate: int | None = None) -> np.ndarray:
        """
        Process a single audio chunk with all enabled effects

        Args:
            audio: Input audio chunk (stereo or mono)
            sample_rate: Actual sample rate of the current track (uses config default if None)

        Returns:
            Processed audio chunk
        """
        if audio is None or len(audio) == 0:
            # #3744: return a fresh copy on the empty branch so the
            # caller can't mutate the array we hand back into anything
            # else that retains a reference. Mirrors the copy-before-
            # modify discipline used everywhere else in the engine
            # (HybridProcessor._process_impl:240, BrickWallLimiter.process:91).
            return audio if audio is None else audio.copy()

        start_time = time.perf_counter()

        # #3784: snapshot `effects_enabled` under the lock, then release it
        # for the actual DSP work. AutoMasterProcessor and RealtimeLevelMatcher
        # each hold their own `_lock` while processing, so the outer lock
        # only needs to fence the effects-map read against `set_effect_enabled` /
        # `set_fingerprint` mutators. Keeping it held across the full chain
        # (level matcher + auto master + safety limiter) blocked
        # `set_fingerprint` for the entire ~23 ms chunk duration even though
        # it touches a different inner component's lock.
        with self.lock:
            level_matching_enabled = self.effects_enabled.get('level_matching', False)
            auto_mastering_enabled = self.effects_enabled.get('auto_mastering', False)

        processed = audio.copy()

        # Apply level matching first
        if level_matching_enabled and self.level_matcher:
            processed = self.level_matcher.process(processed)

        # Apply auto-mastering
        if auto_mastering_enabled and self.auto_master:
            processed = self.auto_master.process(processed)

        # Final safety limiting — linear gain reduction to target_peak.
        # tanh was previously applied to ALL samples in the chunk, adding
        # harmonic distortion even to sub-threshold content (fixes #2201).
        # Linear scaling preserves signal shape: only the level changes.
        #
        # #3744: cast the scaling factor to the input dtype so float32
        # chunks don't silently promote to float64 (np.max returns a
        # numpy scalar that's float64-typed regardless of input). Same
        # dtype-drift class as #3658 / #3659 / #2450.
        # #3754: target peak hoisted to PlayerConfig.realtime_safety_peak
        # so the ceiling lives next to other player knobs and can be
        # tuned to align with HybridProcessor's brick-wall threshold
        # (-0.3 dBFS ≈ 0.9661 linear) when both limiters share the
        # signal chain. Default 0.95 preserves prior behavior.
        target_peak = self.config.realtime_safety_peak
        max_val = np.max(np.abs(processed))
        if max_val > target_peak:
            processed = processed * processed.dtype.type(
                target_peak / max_val
            )

        # Record performance inside the lock so any concurrent reader of
        # performance_monitor stats (e.g. get_processing_info) always sees a
        # consistent state (fixes #2213).
        with self.lock:
            processing_time = time.perf_counter() - start_time
            chunk_duration = len(audio) / (sample_rate or self.config.sample_rate)
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
                self.level_matcher.reset()

            if self.auto_master:
                self.auto_master.set_profile("balanced")
                self.auto_master.set_enabled(False)

            # Reset effect states
            for effect in self.effects_enabled:
                self.effects_enabled[effect] = False

            info("All effects reset to initial state")
