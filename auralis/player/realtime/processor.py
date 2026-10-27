"""
Real-time Processor
~~~~~~~~~~~~~~~~~~

Main real-time audio processor orchestrator

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import time
from threading import Lock
from typing import Any

import numpy as np

from ...utils.audio_validation import validate_audio_finite
from ...utils.logging import info
from ..config import PlayerConfig
from .auto_master import AutoMasterProcessor
from .level_matcher import RealtimeLevelMatcher
from .peak_ceiling import StreamingPeakCeiling
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

        # Final safety ceiling (#5721): a per-sample envelope carried across
        # chunks, not the old per-chunk `ceiling / max(|chunk|)` scalar that
        # stepped at every chunk boundary.
        self.safety_ceiling = StreamingPeakCeiling(config.sample_rate)

        # Performance monitoring
        self.performance_monitor = PerformanceMonitor(max_cpu_usage=0.75)

        # Processing state.
        #
        # #4633: there is deliberately no `is_processing` flag here. One existed,
        # assigned False in __init__ and never touched again — process_chunk()
        # never toggled it and nothing read it, so any consumer that reasonably
        # trusted the name (a busy indicator, a health check, a re-entrancy
        # guard) would have silently received a permanent False. If live
        # processing status is ever genuinely needed, wire it properly rather
        # than reinstating the default: set it under `self.lock` at the top of
        # process_chunk() and clear it in a `finally:` so it cannot stick after
        # an exception, and surface it through get_processing_info().
        self.effects_enabled = {
            'level_matching': config.enable_level_matching,
            'auto_mastering': config.enable_auto_mastering,
        }

        info("RealtimeProcessor initialized:")
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

    def set_fingerprint(self, fingerprint: dict[str, Any] | None) -> None:
        """
        Set or clear the 25D fingerprint used for adaptive processing.

        Args:
            fingerprint: 25D fingerprint dictionary from FingerprintService
        """
        with self.lock:
            if self.auto_master is None:
                return
            if fingerprint is None:
                self.auto_master.clear_fingerprint()
                info("Fingerprint cleared; using profile-based mastering")
            else:
                self.auto_master.set_fingerprint(fingerprint)
                info("Fingerprint set for adaptive mastering")

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

        # Apply auto-mastering. set_sample_rate() is a no-op unless the
        # chunk's rate differs from the DSP chain's current rate (#5729),
        # so a 48/96 kHz track gets correctly-scaled attack/release and
        # transient windows after load or a gapless swap.
        if auto_mastering_enabled and self.auto_master:
            if sample_rate is not None:
                self.auto_master.set_sample_rate(sample_rate)
            processed = self.auto_master.process(processed)

        # Final safety limiting to target_peak. tanh was previously applied to
        # ALL samples in the chunk, adding harmonic distortion even to
        # sub-threshold content (fixes #2201); only the level changes here.
        #
        # #5721: the gain is a per-sample envelope that StreamingPeakCeiling
        # carries across chunks. The old `target_peak / max(|chunk|)` scalar
        # was constant inside a chunk and independent between chunks, so it
        # stepped (-2.8 dB in the probe) at both edges of any over-ceiling chunk.
        # #3744: the helper preserves the input dtype (no float32 -> float64).
        # #3754: target peak lives in PlayerConfig.realtime_safety_peak so it
        # can be tuned to align with HybridProcessor's brick-wall threshold
        # (-0.3 dBFS ~ 0.9661 linear). Default 0.95 preserves prior behavior.
        if sample_rate is not None:
            self.safety_ceiling.set_sample_rate(sample_rate)
        processed = self.safety_ceiling.apply(processed, self.config.realtime_safety_peak)

        # #5313: unlike every other pipeline in the engine (HybridProcessor,
        # ContinuousMode, AdaptiveMode, SimpleMasteringPipeline), this chain
        # had no finite-value guard anywhere — and the peak clamp just above
        # is silently defeated by NaN (`max_val > target_peak` is False when
        # max_val is NaN, so a non-finite chunk skips it entirely and would
        # otherwise reach the output device unclamped and unlogged). This
        # final check repairs (or at minimum logs) any non-finite sample
        # regardless of whether the clamp above caught it, matching
        # ContinuousMode's `validate_audio_finite(..., repair=True)` pattern.
        processed = validate_audio_finite(
            processed, context="realtime chunk output", repair=True
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

            self.safety_ceiling.reset()

            if self.auto_master:
                self.auto_master.set_enabled(False)

            # Reset effect states
            for effect in self.effects_enabled:
                self.effects_enabled[effect] = False

            info("All effects reset to initial state")
