"""
Target preset overrides
~~~~~~~~~~~~~~~~~~~~~~~

Split from ``AdaptiveTargetGenerator`` (#6272); each function takes the
generator as its first argument and the class method stays a thin delegator.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


from typing import Any

from ...dsp.utils.loudness_targets import DEFAULT_TARGET_LUFS

from ...utils.logging import debug


def apply_preset_overrides(generator, targets: dict[str, Any],
                            preset_profile: Any, content_profile: dict[str, Any]) -> dict[str, Any]:
    """
    Apply preset-specific overrides to adaptive targets.

    Blends preset characteristics with adaptive targets using the preset's
    blend factors to preserve content-aware intelligence.

    Args:
        targets: Adaptive targets from content analysis
        preset_profile: PresetProfile with preset characteristics
        content_profile: Content analysis results

    Returns:
        Modified targets with preset characteristics applied
    """
    debug(f"Applying preset overrides: {preset_profile.name}")

    # Create a copy to avoid modifying original
    modified_targets = targets.copy()

    # Apply EQ adjustments (blended with adaptive targets)
    eq_blend = preset_profile.eq_blend

    # Low shelf (bass)
    adaptive_bass = modified_targets.get("bass_boost_db", 0.0)
    preset_bass = preset_profile.low_shelf_gain
    modified_targets["bass_boost_db"] = (
        adaptive_bass * (1 - eq_blend) + preset_bass * eq_blend
    )

    # Mid-range adjustments
    adaptive_mid_clarity = modified_targets.get("midrange_clarity_db", 0.0)
    preset_mid = preset_profile.mid_gain
    modified_targets["midrange_clarity_db"] = (
        adaptive_mid_clarity * (1 - eq_blend) + preset_mid * eq_blend
    )

    # High shelf (treble)
    adaptive_treble = modified_targets.get("treble_enhancement_db", 0.0)
    preset_treble = preset_profile.high_shelf_gain
    modified_targets["treble_enhancement_db"] = (
        adaptive_treble * (1 - eq_blend) + preset_treble * eq_blend
    )

    # Apply dynamics adjustments (blended with adaptive targets)
    dynamics_blend = preset_profile.dynamics_blend

    # Compression ratio
    adaptive_ratio = modified_targets.get("compression_ratio", 2.5)
    preset_ratio = preset_profile.compression_ratio
    modified_targets["compression_ratio"] = (
        adaptive_ratio * (1 - dynamics_blend) + preset_ratio * dynamics_blend
    )

    # Mastering intensity
    adaptive_intensity = modified_targets.get("mastering_intensity", 0.8)
    modified_targets["mastering_intensity"] = (
        adaptive_intensity * (1 - dynamics_blend) + dynamics_blend
    )

    # Target loudness (LUFS) - blend towards preset target
    # But respect content characteristics (don't over-compress material)
    adaptive_lufs = modified_targets.get("target_lufs", DEFAULT_TARGET_LUFS)
    preset_lufs = preset_profile.target_lufs

    # Get estimated input loudness from content analysis
    estimated_lufs = content_profile.get("estimated_lufs", -20.0)
    dynamic_range = content_profile.get("dynamic_range", 15.0)

    # Content-aware loudness adjustment based on input characteristics
    if dynamic_range < 8:
        # Very compressed (loudness wars era) - be very conservative
        lufs_blend = dynamics_blend * 0.3
        debug(f"Very compressed material (DR<8): using conservative blend {lufs_blend:.2f}")
    elif dynamic_range < 10:
        # Moderately compressed - be conservative
        lufs_blend = dynamics_blend * 0.5
        debug(f"Compressed material (DR<10): using moderate blend {lufs_blend:.2f}")
    elif estimated_lufs > -12:
        # Already loud (modern/loudness wars) - be conservative even if DR is good
        lufs_blend = dynamics_blend * 0.4
        debug(f"Already loud material (>{estimated_lufs:.1f} LUFS): using conservative blend {lufs_blend:.2f}")
    else:
        # Normal dynamic material - use standard blend
        lufs_blend = dynamics_blend * 0.8

    modified_targets["target_lufs"] = (
        adaptive_lufs * (1 - lufs_blend) + preset_lufs * lufs_blend
    )

    # Add preset-specific EQ band adjustments
    # These provide additional character beyond the basic shelves
    modified_targets["preset_low_mid_gain"] = preset_profile.low_mid_gain * eq_blend
    modified_targets["preset_high_mid_gain"] = preset_profile.high_mid_gain * eq_blend

    # Store preset metadata for downstream processors
    modified_targets["preset_name"] = preset_profile.name
    modified_targets["preset_eq_blend"] = eq_blend
    modified_targets["preset_dynamics_blend"] = dynamics_blend

    debug(f"Preset adjustments - LUFS: {adaptive_lufs:.1f} → {modified_targets['target_lufs']:.1f}, "
          f"Bass: {adaptive_bass:.1f} → {modified_targets['bass_boost_db']:.1f}dB, "
          f"Comp: {adaptive_ratio:.1f} → {modified_targets['compression_ratio']:.1f}:1")

    return modified_targets
