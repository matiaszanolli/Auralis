# -*- coding: utf-8 -*-

"""
Pre-generated Mastering Preset Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pre-computed EQ and dynamics parameters for standard mastering presets.
Eliminates expensive parameter generation for standard profiles.

Instead of analyzing content and generating parameters every time, we pre-generate
them once for common presets and load at startup.

Performance Impact:
- Without pre-gen: ~100-200ms for parameter generation per job
- With pre-gen: ~0-5ms (dict lookup + copy)
- 20-40x speedup for standard presets

Presets:
1. Adaptive - Automatic content-aware processing (requires analysis)
2. Gentle - Subtle enhancement, safe for all content
3. Warm - Emphasize mids and bass, reduce harshness
4. Bright - Emphasize presence and air, add sparkle
5. Punchy - Increase dynamics and impact, aggressive compression

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Any, Optional
import json
from pathlib import Path


class PresetParameters:
    """
    Pre-generated parameter sets for standard mastering presets.

    Each preset contains pre-computed EQ and dynamics parameters
    optimized for specific mixing/mastering goals.
    """

    # Gentle Preset - Safe, subtle enhancement
    GENTLE = {
        "name": "Gentle",
        "description": "Subtle enhancement, safe for all content",
        "eq_gains": {
            "sub_bass_20": -2.0,    # Slight sub-bass reduction
            "bass_60": 0.5,          # Minimal bass lift
            "low_mid_250": 1.0,      # Gentle low-mid lift
            "mid_500": 0.0,          # Neutral mid
            "upper_mid_2k": 0.5,     # Slight presence
            "presence_4k": 1.0,      # Mild presence lift
            "air_6k": 0.5,           # Subtle air
        },
        "dynamics": {
            "compressor_ratio": 2.0,
            "compressor_threshold_db": -20.0,
            "compressor_attack_ms": 10.0,
            "compressor_release_ms": 100.0,
            "makeup_gain_db": 2.0,
            "soft_clipper_threshold_db": -2.0,
        },
        "target_lufs": -10.0,
    }

    # Warm Preset - Emphasis mids and bass, reduce harshness
    WARM = {
        "name": "Warm",
        "description": "Emphasize mids and bass, reduce harshness",
        "eq_gains": {
            "sub_bass_20": 1.0,      # Lift sub-bass
            "bass_60": 2.0,          # Warm bass emphasis
            "low_mid_250": 2.5,      # Rich lows
            "mid_500": 1.5,          # Warm mids
            "upper_mid_2k": -0.5,    # Reduce harshness
            "presence_4k": -1.0,     # Smooth presence
            "air_6k": 0.5,           # Subtle air
        },
        "dynamics": {
            "compressor_ratio": 2.5,
            "compressor_threshold_db": -22.0,
            "compressor_attack_ms": 20.0,
            "compressor_release_ms": 120.0,
            "makeup_gain_db": 3.0,
            "soft_clipper_threshold_db": -1.5,
        },
        "target_lufs": -9.0,
    }

    # Bright Preset - Presence and air emphasis
    BRIGHT = {
        "name": "Bright",
        "description": "Emphasize presence and air, add sparkle",
        "eq_gains": {
            "sub_bass_20": -1.0,     # Reduce mud
            "bass_60": 0.5,          # Controlled bass
            "low_mid_250": 0.0,      # Neutral lows
            "mid_500": 0.5,          # Clean mids
            "upper_mid_2k": 1.5,     # Bright upper mids
            "presence_4k": 3.0,      # Strong presence
            "air_6k": 2.5,           # Airy brightness
        },
        "dynamics": {
            "compressor_ratio": 1.8,
            "compressor_threshold_db": -18.0,
            "compressor_attack_ms": 5.0,
            "compressor_release_ms": 80.0,
            "makeup_gain_db": 1.5,
            "soft_clipper_threshold_db": -2.5,
        },
        "target_lufs": -11.0,
    }

    # Punchy Preset - Dynamic impact and aggression
    PUNCHY = {
        "name": "Punchy",
        "description": "Increase dynamics and impact, aggressive compression",
        "eq_gains": {
            "sub_bass_20": 1.5,      # Punch in subs
            "bass_60": 2.5,          # Powerful bass
            "low_mid_250": 1.5,      # Impact in lows
            "mid_500": 1.0,          # Forward mids
            "upper_mid_2k": 2.0,     # Aggressive presence
            "presence_4k": 2.0,      # Punchy presence
            "air_6k": 1.0,           # Crisp highs
        },
        "dynamics": {
            "compressor_ratio": 4.0,  # Strong compression
            "compressor_threshold_db": -18.0,
            "compressor_attack_ms": 3.0,  # Fast attack for punch
            "compressor_release_ms": 60.0,
            "makeup_gain_db": 5.0,
            "soft_clipper_threshold_db": -1.0,
        },
        "target_lufs": -8.0,
    }

    # Adaptive Preset - Content-aware processing
    # NOTE: Adaptive preset requires content analysis and cannot be pre-generated
    ADAPTIVE = {
        "name": "Adaptive",
        "description": "Automatic content-aware processing (requires analysis)",
        "requires_analysis": True,
        "note": "This preset requires audio analysis and cannot be pre-generated",
    }

    # All presets mapped
    ALL_PRESETS = {
        "gentle": GENTLE,
        "warm": WARM,
        "bright": BRIGHT,
        "punchy": PUNCHY,
        "adaptive": ADAPTIVE,
    }

    @staticmethod
    def get_preset(preset_name: str) -> Dict[str, Any]:
        """
        Get pre-generated parameters for a preset.

        Args:
            preset_name: Name of preset (gentle, warm, bright, punchy, adaptive)

        Returns:
            Dict with pre-computed parameters, or None if not found

        Raises:
            ValueError: If preset not found
        """
        preset_name_lower = preset_name.lower()

        if preset_name_lower not in PresetParameters.ALL_PRESETS:
            raise ValueError(
                f"Unknown preset: {preset_name}. "
                f"Valid presets: {', '.join(PresetParameters.ALL_PRESETS.keys())}"
            )

        return PresetParameters.ALL_PRESETS[preset_name_lower].copy()

    @staticmethod
    def is_preset_pregenerated(preset_name: str) -> bool:
        """
        Check if preset parameters are pre-generated (or require analysis).

        Args:
            preset_name: Name of preset

        Returns:
            True if preset is pre-generated, False if requires analysis
        """
        preset = PresetParameters.get_preset(preset_name)
        return not preset.get("requires_analysis", False)

    @staticmethod
    def export_presets_to_json(output_path: Optional[str] = None) -> str:
        """
        Export all presets to JSON for external use/validation.

        Args:
            output_path: Path to save JSON (optional)

        Returns:
            JSON string representation of all presets
        """
        json_data = json.dumps(PresetParameters.ALL_PRESETS, indent=2)

        if output_path:
            Path(output_path).write_text(json_data)

        return json_data

    @staticmethod
    def list_presets() -> Dict[str, str]:
        """
        List all available presets with descriptions.

        Returns:
            Dict mapping preset names to descriptions
        """
        return {
            name: str(preset.get("description", ""))
            for name, preset in PresetParameters.ALL_PRESETS.items()
        }


def get_preset_parameters(preset_name: str) -> Dict[str, Any]:
    """
    Convenience function to get preset parameters.

    Args:
        preset_name: Name of preset

    Returns:
        Dict with pre-computed parameters

    Raises:
        ValueError: If preset not found
    """
    return PresetParameters.get_preset(preset_name)
