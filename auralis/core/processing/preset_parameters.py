# -*- coding: utf-8 -*-

"""
Adaptive Mastering Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Content-aware adaptive processing based on audio fingerprint analysis.
All mastering is adaptive - no fixed presets.

Processing parameters are generated dynamically based on:
- Audio fingerprint (25D: tempo, LUFS, harmonic ratio, spectral features, etc.)
- Content characteristics (genre hints, dynamic range, frequency balance)
- Source quality (compression level, noise floor, transient density)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Any, Optional
import json
from pathlib import Path


class PresetParameters:
    """
    Content-aware adaptive mastering parameters.

    All processing is adaptive - parameters are generated dynamically
    based on audio fingerprint analysis and content characteristics.
    """

    # Adaptive - The only mode, content-aware processing
    ADAPTIVE = {
        "name": "Adaptive",
        "description": "Content-aware processing based on audio fingerprint analysis",
        "requires_analysis": True,
    }

    # All presets mapped (only adaptive now)
    ALL_PRESETS = {
        "adaptive": ADAPTIVE,
    }

    @staticmethod
    def get_preset(preset_name: str = "adaptive") -> Dict[str, Any]:
        """
        Get adaptive processing parameters.

        Args:
            preset_name: Must be "adaptive" (only mode available)

        Returns:
            Dict indicating adaptive processing is required

        Raises:
            ValueError: If preset is not "adaptive"
        """
        preset_name_lower = preset_name.lower()

        if preset_name_lower not in PresetParameters.ALL_PRESETS:
            raise ValueError(
                f"Unknown preset: {preset_name}. "
                f"Only 'adaptive' is available (all processing is content-aware)"
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
