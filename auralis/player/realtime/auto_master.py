# -*- coding: utf-8 -*-

"""
Auto Master Processor
~~~~~~~~~~~~~~~~~~~~~

Automatic mastering with genre-aware processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any
from ..config import PlayerConfig
from ...utils.logging import debug, info, warning
from ...dsp.dynamics import AdaptiveCompressor
from ...dsp.dynamics.settings import CompressorSettings


class AutoMasterProcessor:
    """Automatic mastering with genre-aware processing"""

    def __init__(self, config: PlayerConfig):
        self.config = config
        self.enabled = False
        self.profile = "balanced"  # balanced, warm, bright, punchy

        # Simple EQ parameters for different profiles
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

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply automatic mastering"""
        if not self.enabled:
            return audio

        # Get current profile settings
        settings = self.profiles[self.profile]

        processed = audio.copy()

        # Apply stateful compression with proper envelope tracking
        # This prevents gain pumping and maintains smooth dynamics
        processed, comp_stats = self.compressor.process(processed, detection_mode="rms")

        # Apply profile-based tonal shaping (simplified)
        # In a full implementation, this would be proper EQ bands
        profile_gain = (settings["low_gain"] + settings["mid_gain"] + settings["high_gain"]) / 3

        # Apply gain, but check for potential clipping on loud material
        # If input is already hot (> -6dBFS), reduce profile gain to prevent fuzz
        input_peak = np.max(np.abs(audio))
        if input_peak > 0.5:  # -6dBFS threshold
            # Reduce gain proportionally for loud material
            # Scale from 1.0 (at 0.5) to 0.8 (at 1.0)
            hot_reduction = 1.0 - (input_peak - 0.5) * 0.4
            profile_gain *= max(hot_reduction, 0.8)  # Don't reduce below 80%

        processed *= profile_gain

        return processed

    def get_stats(self) -> Dict[str, Any]:
        """Get auto-master statistics"""
        return {
            'enabled': self.enabled,
            'profile': self.profile,
            'available_profiles': list(self.profiles.keys()),
        }
