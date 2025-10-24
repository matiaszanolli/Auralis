# -*- coding: utf-8 -*-

"""
Mastering Preset Profiles
~~~~~~~~~~~~~~~~~~~~~~~~~

Defines mastering preset configurations for different sonic characters.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class PresetProfile:
    """
    Configuration profile for a mastering preset.

    Each preset defines processing characteristics for achieving
    a specific sonic character.
    """
    name: str
    description: str

    # EQ characteristics
    low_shelf_gain: float  # dB boost/cut for bass (< 200 Hz)
    low_mid_gain: float    # dB boost/cut for low-mids (200-800 Hz)
    mid_gain: float        # dB boost/cut for mids (800-3000 Hz)
    high_mid_gain: float   # dB boost/cut for high-mids (3000-8000 Hz)
    high_shelf_gain: float # dB boost/cut for highs (> 8000 Hz)

    # Dynamics characteristics
    compression_ratio: float      # Compression ratio (1.5:1 to 4:1)
    compression_threshold: float  # Threshold in dB
    compression_attack: float     # Attack time in ms
    compression_release: float    # Release time in ms

    # Limiting characteristics
    limiter_threshold: float  # Limiter threshold in dB
    limiter_release: float    # Limiter release time in ms

    # Processing intensity
    eq_blend: float          # 0.0-1.0 - How much EQ to apply
    dynamics_blend: float    # 0.0-1.0 - How much compression to apply

    # Target levels
    target_lufs: float       # Target loudness in LUFS (-14 for streaming, -8 for club)


def create_preset_profiles() -> Dict[str, PresetProfile]:
    """
    Create all mastering preset profiles.

    Returns:
        Dictionary mapping preset names to PresetProfile objects
    """
    return {
        "adaptive": PresetProfile(
            name="Adaptive",
            description="Intelligent content-aware mastering that adapts to your audio",

            # Balanced EQ - let adaptive algorithm decide
            low_shelf_gain=0.0,
            low_mid_gain=0.0,
            mid_gain=0.0,
            high_mid_gain=0.0,
            high_shelf_gain=0.0,

            # Very light compression for maximum transparency
            compression_ratio=1.5,
            compression_threshold=-26.0,
            compression_attack=25.0,
            compression_release=250.0,

            # Very conservative limiting with plenty of headroom
            limiter_threshold=-4.0,
            limiter_release=120.0,

            # Much reduced processing strength - subtle enhancement only
            eq_blend=0.4,
            dynamics_blend=0.25,

            # Conservative loudness target - preserve dynamics
            target_lufs=-18.0,
        ),





























        "gentle": PresetProfile(
            name="Gentle",
            description="Subtle, transparent processing with minimal coloration",

            # Very light EQ adjustments
            low_shelf_gain=0.3,
            low_mid_gain=0.0,
            mid_gain=0.0,
            high_mid_gain=0.2,
            high_shelf_gain=0.5,

            # Light compression
            compression_ratio=1.8,
            compression_threshold=-20.0,
            compression_attack=15.0,
            compression_release=150.0,

            # Conservative limiting
            limiter_threshold=-2.0,
            limiter_release=75.0,

            # Reduced processing intensity
            eq_blend=0.6,
            dynamics_blend=0.5,

            # Lower target loudness
            target_lufs=-16.0,
        ),

        "warm": PresetProfile(
            name="Warm",
            description="Rich analog warmth with enhanced low-mids and smooth highs",

            # Warm EQ curve - boost bass and low-mids, gentle high-end
            low_shelf_gain=1.5,
            low_mid_gain=1.2,
            mid_gain=0.3,
            high_mid_gain=-0.3,
            high_shelf_gain=0.8,

            # Smooth compression
            compression_ratio=2.2,
            compression_threshold=-19.0,
            compression_attack=20.0,
            compression_release=200.0,

            # Smooth limiting
            limiter_threshold=-1.5,
            limiter_release=100.0,

            # Full EQ, moderate dynamics
            eq_blend=1.0,
            dynamics_blend=0.75,

            # Moderate loudness
            target_lufs=-13.0,
        ),

        "bright": PresetProfile(
            name="Bright",
            description="Modern clarity with enhanced presence and air",

            # Bright EQ curve - emphasis on high-mids and highs
            low_shelf_gain=0.0,
            low_mid_gain=-0.5,
            mid_gain=0.5,
            high_mid_gain=2.0,
            high_shelf_gain=2.5,

            # Tight, controlled compression
            compression_ratio=2.8,
            compression_threshold=-17.0,
            compression_attack=5.0,
            compression_release=80.0,

            # Tight limiting
            limiter_threshold=-0.8,
            limiter_release=40.0,

            # Strong EQ, full dynamics
            eq_blend=1.0,
            dynamics_blend=0.9,

            # Higher target loudness
            target_lufs=-12.0,
        ),

        "punchy": PresetProfile(
            name="Punchy",
            description="Heavy music mastering - powerful dynamics for metal and industrial",

            # Punchy EQ curve - bass punch (80-250 Hz), presence (2-4 kHz)
            # Based on heavy metal Matchering analysis
            low_shelf_gain=1.8,      # Bass punch without mud
            low_mid_gain=0.5,        # Body
            mid_gain=0.0,            # Neutral mids
            high_mid_gain=1.5,       # Presence and attack
            high_shelf_gain=0.8,     # Air without harshness

            # Moderate compression for controlled punch
            # Target: RMS +3 to +4 dB increase, Crest -0.5 to -1.0 dB
            compression_ratio=2.5,
            compression_threshold=-18.0,
            compression_attack=5.0,
            compression_release=100.0,

            # Moderate limiting - allow dynamics
            # Target final crest: 13-14 dB
            limiter_threshold=-2.0,
            limiter_release=80.0,

            # Balanced processing intensity
            eq_blend=0.75,
            dynamics_blend=0.65,

            # Target RMS: -14 dB (heavy music Matchering average)
            target_lufs=-14.0,
        ),

        "live": PresetProfile(
            name="Live",
            description="Live recording enhancement - energy and clarity with audience control",

            # Live EQ curve - reduce mud, enhance clarity
            low_shelf_gain=0.8,      # Controlled low end
            low_mid_gain=-0.8,       # Reduce 200-500 Hz mud
            mid_gain=0.5,            # Clarity
            high_mid_gain=2.0,       # Presence and detail
            high_shelf_gain=1.5,     # Air and space

            # LIGHT compression - live material already has good dynamics
            # Matchering shows +2 to +3 dB RMS with -2 dB crest (gentle compression)
            compression_ratio=1.8,
            compression_threshold=-22.0,
            compression_attack=15.0,
            compression_release=180.0,

            # Very gentle limiting - preserve transients
            # Target final crest: 11-13 dB
            limiter_threshold=-3.5,
            limiter_release=120.0,

            # Reduced processing intensity to preserve live energy
            eq_blend=0.7,
            dynamics_blend=0.4,

            # Target RMS: -13.5 dB
            target_lufs=-13.5,
        ),
    }


def get_preset_profile(preset_name: str) -> Optional[PresetProfile]:
    """
    Get a preset profile by name.

    Args:
        preset_name: Name of the preset (case-insensitive)

    Returns:
        PresetProfile if found, None otherwise
    """
    profiles = create_preset_profiles()
    return profiles.get(preset_name.lower())


def get_available_presets() -> list:
    """
    Get list of available preset names.

    Returns:
        List of preset names
    """
    return list(create_preset_profiles().keys())
