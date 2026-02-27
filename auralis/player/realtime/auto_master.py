"""
Auto Master Processor
~~~~~~~~~~~~~~~~~~~~~

Automatic mastering with genre-aware processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

import numpy as np

from ...dsp.dynamics import AdaptiveCompressor
from ...dsp.dynamics.lowmid_transient_enhancer import LowMidTransientEnhancer
from ...dsp.dynamics.settings import CompressorSettings
from ...dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from ...utils.logging import debug, info, warning
from ..config import PlayerConfig


class AutoMasterProcessor:
    """
    Automatic mastering with fingerprint-aware adaptive processing.

    Supports two processing modes:
    1. Profile-based (fallback): Static gains per profile
    2. Fingerprint-adaptive (preferred): Content-aware gains from 25D analysis
    """

    def __init__(self, config: PlayerConfig):
        self.config = config
        self.enabled = False
        self.profile = "balanced"  # balanced, warm, bright, punchy

        # Fingerprint and adaptive parameters
        self.fingerprint: dict | None = None
        self.adaptive_params: dict | None = None

        # Fallback profile-based EQ parameters
        self.profiles = {
            "balanced": {"low_gain": 1.0, "mid_gain": 1.0, "high_gain": 1.0},
            "warm": {"low_gain": 1.1, "mid_gain": 0.95, "high_gain": 0.9},
            "bright": {"low_gain": 0.9, "mid_gain": 1.0, "high_gain": 1.15},
            "punchy": {"low_gain": 1.05, "mid_gain": 1.1, "high_gain": 1.05},
        }

        # Initialize proper stateful compressor to prevent gain pumping
        # Settings prioritize transient preservation to avoid kick/bass harmonic overlap
        # Use very gentle compression to avoid compressing kick drums into bass range
        comp_settings = CompressorSettings(
            threshold_db=-24.0,  # Higher threshold = only compress very loud peaks
            ratio=1.3,           # Very gentle ratio (1.3:1) to preserve transient punch
            attack_ms=20.0,      # Slower attack (20ms) lets transients breathe through
            release_ms=200.0,    # Longer release for smooth recovery
            knee_db=10.0,        # Very wide soft knee for ultra-smooth compression curve
            makeup_gain_db=0.0,  # No makeup gain (applied separately)
            enable_lookahead=False  # No lookahead for real-time
        )
        self.compressor = AdaptiveCompressor(comp_settings, config.sample_rate)

        # Initialize optional transient enhancer for low-mid punch restoration
        # Used for quiet, dynamic material (< -13 LUFS with crest > 14 dB)
        self.transient_enhancer = LowMidTransientEnhancer(sample_rate=config.sample_rate)
        self.use_transient_enhancement = True  # Can be toggled via set_use_transient_enhancement()

        debug(f"AutoMasterProcessor initialized with profile: {self.profile}")

    def set_profile(self, profile: str) -> None:
        """Set mastering profile"""
        if profile in self.profiles:
            self.profile = profile
            info(f"Auto-master profile set to: {profile}")
        else:
            warning(f"Unknown profile: {profile}, using balanced")
            self.profile = "balanced"

    def set_use_transient_enhancement(self, enabled: bool) -> None:
        """Enable/disable low-mid transient enhancement"""
        self.use_transient_enhancement = enabled
        info(f"Transient enhancement {'enabled' if enabled else 'disabled'}")

    def set_fingerprint(self, fingerprint: dict) -> None:
        """
        Set 25D fingerprint for adaptive processing.

        Args:
            fingerprint: 25D fingerprint dictionary from FingerprintService
        """
        self.fingerprint = fingerprint
        self.adaptive_params = self._generate_adaptive_parameters(fingerprint)
        info(f"Auto-master fingerprint set: LUFS {fingerprint.get('lufs', 0):.1f}, "
             f"crest {fingerprint.get('crest_db', 0):.1f} dB")

    def _generate_adaptive_parameters(self, fingerprint: dict) -> dict:
        """
        Generate content-aware processing parameters from fingerprint.

        Same logic as auto_master.py's generate_adaptive_parameters()
        """
        # Extract key fingerprint metrics
        lufs = fingerprint.get('lufs', -14.0)
        crest_db = fingerprint.get('crest_db', 12.0)
        bass_pct = fingerprint.get('bass_pct', 0.15)
        transient_density = fingerprint.get('transient_density', 0.5)

        # Calculate adaptive makeup gain using centralized logic
        makeup_gain_db, reasoning = AdaptiveLoudnessControl.calculate_adaptive_gain(
            source_lufs=lufs,
            intensity=1.0,
            crest_factor_db=crest_db,
            bass_pct=bass_pct,
            transient_density=transient_density
        )

        # Calculate adaptive compression ratio based on dynamic range
        if crest_db > 15:  # High dynamic range
            compression_ratio = 1.5  # Gentle compression
        elif crest_db > 12:  # Moderate dynamic range
            compression_ratio = 2.0
        else:  # Low dynamic range (already compressed)
            compression_ratio = 2.5

        # Calculate adaptive target peak
        target_peak, _ = AdaptiveLoudnessControl.calculate_adaptive_peak_target(lufs)

        return {
            'makeup_gain_db': makeup_gain_db,
            'compression_ratio': compression_ratio,
            'target_peak': target_peak,
            'reasoning': reasoning,
        }

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply automatic mastering with fingerprint-aware adaptive processing"""
        if not self.enabled:
            return audio

        processed = audio.copy()

        # Apply stateful compression with proper envelope tracking
        # Use hybrid detection (70% RMS + 30% peak) for balanced transient preservation
        # Peak-only was too responsive; pure RMS was too slow. Hybrid balances both.
        processed, comp_stats = self.compressor.process(processed, detection_mode="hybrid")

        # Determine which gain to apply
        if self.adaptive_params is not None:
            # Use fingerprint-adaptive gain
            makeup_gain_db = self.adaptive_params['makeup_gain_db']
            debug(f"Applying adaptive gain: {makeup_gain_db:.1f} dB")
        else:
            # Fallback to profile-based gain
            settings = self.profiles[self.profile]
            profile_gain = (settings["low_gain"] + settings["mid_gain"] + settings["high_gain"]) / 3

            # Convert to dB for consistency
            makeup_gain_db = 20 * np.log10(profile_gain) if profile_gain > 0 else 0
            debug(f"Using profile-based gain ({self.profile}): {makeup_gain_db:.1f} dB")

        # Apply gain with clipping protection measured on post-compression audio,
        # not the raw input — using the pre-compression peak would over-penalise
        # material that the compressor has already brought under control (#2310).
        # Cap gain to available headroom so the expected output peak never exceeds
        # 0.98 (-0.18 dBFS). The old proportional-attenuation approach (floored at
        # 0.8×) could not prevent clipping when peaks were already near 0 dBFS.
        processed_peak = np.max(np.abs(processed))
        if processed_peak > 0 and makeup_gain_db > 0:
            max_safe_gain_db = 20 * np.log10(0.98 / processed_peak)
            if makeup_gain_db > max_safe_gain_db:
                debug(f"Capped gain {makeup_gain_db:.1f} → {max(max_safe_gain_db, 0.0):.1f} dB "
                      f"(headroom protection, peak {20*np.log10(processed_peak):.1f} dBFS)")
                makeup_gain_db = max(max_safe_gain_db, 0.0)

        # Apply makeup gain in linear scale
        if makeup_gain_db != 0:
            gain_linear = 10 ** (makeup_gain_db / 20.0)
            processed *= gain_linear

        # Optional: Apply low-mid transient enhancement for quiet, dynamic material
        # This restores punch to bass, piano, vocals after compression
        if self.use_transient_enhancement and self.fingerprint is not None:
            lufs = self.fingerprint.get('lufs', 0)
            crest_db = self.fingerprint.get('crest_db', 0)

            # Enhance for quiet + dynamic material (1990s style)
            if lufs < -13.0 and crest_db > 14.0:
                debug(f"Applying low-mid transient enhancement (LUFS {lufs:.1f}, crest {crest_db:.1f} dB)")
                try:
                    # Use moderate intensity for real-time (not aggressive like batch)
                    transient_intensity = 0.35  # Subtle, not overwhelming
                    attack_samples = int(self.config.sample_rate * 0.05)  # 50ms window
                    processed = self.transient_enhancer.enhance_transients(
                        processed,
                        intensity=transient_intensity,
                        attack_samples=attack_samples
                    )
                    debug(f"Transient enhancement applied (intensity: {transient_intensity:.2f})")
                except Exception as e:
                    warning(f"Transient enhancement failed: {e}")

        # Apply adaptive peak ceiling from fingerprint parameters.
        # target_peak is computed by _generate_adaptive_parameters() but was never
        # consumed here — quieter sources got a higher ceiling (0.90) while loud
        # sources got a tighter one (0.85), acting as a final safety net that
        # accounts for transient enhancement potentially adding back peak energy.
        if self.adaptive_params is not None:
            target_peak = self.adaptive_params['target_peak']
            current_peak = np.max(np.abs(processed))
            if current_peak > target_peak and current_peak > 0:
                processed = processed * (target_peak / current_peak)
                debug(f"Adaptive peak ceiling: {20*np.log10(current_peak):.1f} → "
                      f"{20*np.log10(target_peak):.1f} dBFS")

        return processed

    def get_stats(self) -> dict[str, Any]:
        """Get auto-master statistics"""
        return {
            'enabled': self.enabled,
            'profile': self.profile,
            'available_profiles': list(self.profiles.keys()),
            'has_fingerprint': self.fingerprint is not None,
            'adaptive_params': self.adaptive_params,
            'transient_enhancement_enabled': self.use_transient_enhancement,
        }
