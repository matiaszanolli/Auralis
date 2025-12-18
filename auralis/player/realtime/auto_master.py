# -*- coding: utf-8 -*-

"""
Auto Master Processor
~~~~~~~~~~~~~~~~~~~~~

Automatic mastering with genre-aware processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any, Optional
from ..config import PlayerConfig
from ...utils.logging import debug, info, warning
from ...dsp.dynamics import AdaptiveCompressor
from ...dsp.dynamics.settings import CompressorSettings
from ...dsp.utils.adaptive_loudness import AdaptiveLoudnessControl


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
        self.fingerprint: Optional[Dict] = None
        self.adaptive_params: Optional[Dict] = None

        # Fallback profile-based EQ parameters
        self.profiles = {
            "balanced": {"low_gain": 1.0, "mid_gain": 1.0, "high_gain": 1.0},
            "warm": {"low_gain": 1.1, "mid_gain": 0.95, "high_gain": 0.9},
            "bright": {"low_gain": 0.9, "mid_gain": 1.0, "high_gain": 1.15},
            "punchy": {"low_gain": 1.05, "mid_gain": 1.1, "high_gain": 1.05},
        }

        # Initialize proper stateful compressor to prevent gain pumping
        comp_settings = CompressorSettings(
            threshold_db=-18.0,  # Gentle threshold
            ratio=2.5,           # Moderate compression
            attack_ms=5.0,       # Fast attack
            release_ms=100.0,    # Smooth release
            knee_db=6.0,         # Soft knee
            makeup_gain_db=0.0,  # No makeup gain
            enable_lookahead=False  # No lookahead for real-time
        )
        self.compressor = AdaptiveCompressor(comp_settings, config.sample_rate)

        debug(f"AutoMasterProcessor initialized with profile: {self.profile}")

    def set_profile(self, profile: str) -> None:
        """Set mastering profile"""
        if profile in self.profiles:
            self.profile = profile
            info(f"Auto-master profile set to: {profile}")
        else:
            warning(f"Unknown profile: {profile}, using balanced")
            self.profile = "balanced"

    def set_fingerprint(self, fingerprint: Dict) -> None:
        """
        Set 25D fingerprint for adaptive processing.

        Args:
            fingerprint: 25D fingerprint dictionary from FingerprintService
        """
        self.fingerprint = fingerprint
        self.adaptive_params = self._generate_adaptive_parameters(fingerprint)
        info(f"Auto-master fingerprint set: LUFS {fingerprint.get('lufs', 0):.1f}, "
             f"crest {fingerprint.get('crest_db', 0):.1f} dB")

    def _generate_adaptive_parameters(self, fingerprint: Dict) -> Dict:
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
        # This prevents gain pumping and maintains smooth dynamics
        processed, comp_stats = self.compressor.process(processed, detection_mode="rms")

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

        # Apply gain with clipping protection
        input_peak = np.max(np.abs(audio))
        if input_peak > 0.5:  # -6dBFS threshold
            # Reduce gain proportionally for loud material
            hot_reduction = 1.0 - (input_peak - 0.5) * 0.4
            makeup_gain_db *= max(hot_reduction, 0.8)
            debug(f"Reduced gain due to hot input: {makeup_gain_db:.1f} dB")

        # Apply makeup gain in linear scale
        if makeup_gain_db != 0:
            gain_linear = 10 ** (makeup_gain_db / 20.0)
            processed *= gain_linear

        return processed

    def get_stats(self) -> Dict[str, Any]:
        """Get auto-master statistics"""
        return {
            'enabled': self.enabled,
            'profile': self.profile,
            'available_profiles': list(self.profiles.keys()),
            'has_fingerprint': self.fingerprint is not None,
            'adaptive_params': self.adaptive_params,
        }
