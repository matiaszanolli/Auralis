"""
Mastering Preset Profiles
~~~~~~~~~~~~~~~~~~~~~~~~~

Defines mastering preset configurations for different sonic characters.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass


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
    peak_target_db: float = -0.35  # Peak normalization target in dBFS (default -0.35 dB)


def create_preset_profiles() -> dict[str, PresetProfile]:
    """
    Create all mastering preset profiles.

    A single preset, 'adaptive', ships today. The 'gentle'/'warm'/'bright'/
    'punchy'/'live' profiles that used to live here were removed rather than
    kept as dead entries: config.mastering_profile can only ever be set to
    'adaptive' now (schemas.VALID_PRESETS/EnhancementPresetLiteral narrowed
    the same way, and processor_factory.py's ProcessorFactory.get_or_create
    is the only place that writes mastering_profile, always from that same
    API-gated value), so the other five were exactly as unreachable as 'live'
    already was (#4861) -- just via this profile table instead of
    PreferenceVector.from_preset_name's bias table. get_preset_profile()
    already returns None (not a fallback profile) for any name not in this
    dict, and both of its call sites (adaptive_mode.py, target_generator.py)
    already handle a None profile gracefully, so removing the five entries
    changes no live behavior.

    Returns:
        Dictionary mapping preset names to PresetProfile objects
    """
    return {
        "adaptive": PresetProfile(
            name="Adaptive",
            description="Intelligent content-aware mastering that adapts to your audio",

            # Enhanced EQ - more bass presence, slight high-end lift
            low_shelf_gain=2.5,      # Bass boost
            low_mid_gain=0.5,        # Body
            mid_gain=0.0,            # Neutral mids
            high_mid_gain=0.5,       # Presence
            high_shelf_gain=0.8,     # Air

            # Very light compression for maximum transparency
            compression_ratio=1.5,
            compression_threshold=-26.0,
            compression_attack=25.0,
            compression_release=250.0,

            # Conservative limiting - balanced headroom
            limiter_threshold=-2.5,
            limiter_release=100.0,

            # Moderate processing strength for noticeable enhancement
            eq_blend=0.75,           # Apply more of the EQ curve
            dynamics_blend=0.4,      # Light compression

            # Moderate loudness target - noticeable but not overdone
            target_lufs=-14.0,

            # Balanced headroom (louder output than before)
            peak_target_db=-0.50,
        ),
    }


def get_preset_profile(preset_name: str) -> PresetProfile | None:
    """
    Get a preset profile by name.

    Args:
        preset_name: Name of the preset (case-insensitive)

    Returns:
        PresetProfile if found, None otherwise
    """
    profiles = create_preset_profiles()
    return profiles.get(preset_name.lower())


def get_available_presets() -> list[str]:
    """
    Get list of available preset names.

    Returns:
        List of preset names
    """
    return list(create_preset_profiles().keys())
