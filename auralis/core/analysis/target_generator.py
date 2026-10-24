"""
Adaptive Target Generator
~~~~~~~~~~~~~~~~~~~~~~~~~~

Generate adaptive processing targets based on content analysis

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from ...dsp.utils.loudness_targets import DEFAULT_TARGET_LUFS
from ...utils.logging import debug
from ..config import GenreProfile, UnifiedConfig
from ..utils.fingerprint_unpacker import FingerprintUnpacker


from .target_fingerprint_adjustments import apply_fingerprint_enhancements
from .target_preset_overrides import apply_preset_overrides


class AdaptiveTargetGenerator:
    """Generate adaptive processing targets based on content analysis"""

    def __init__(self, config: UnifiedConfig, processor: Any | None = None) -> None:
        """
        Initialize adaptive target generator

        Args:
            config: Unified configuration object
            processor: Optional reference to main processor for preference access
        """
        self.config = config
        self.processor = processor  # Reference to the main processor for preference access

    def generate_targets(self, content_profile: dict[str, Any]) -> dict[str, Any]:
        """
        Generate adaptive processing targets

        Args:
            content_profile: Content analysis results

        Returns:
            Dictionary containing processing targets
        """
        debug("Generating adaptive processing targets")

        # Get base genre profile
        genre = content_profile["genre_info"]["primary"]
        genre_profile = self.config.get_genre_profile(genre)

        # Adapt targets based on content characteristics
        targets = self._adapt_targets_to_content(genre_profile, content_profile)

        # NEW: Apply fingerprint-driven enhancements if available
        if "fingerprint" in content_profile and content_profile["fingerprint"] is not None:
            targets = self._apply_fingerprint_enhancements(targets, content_profile["fingerprint"])

        # Apply preset overrides (blend with adaptive targets)
        preset_profile = self.config.get_preset_profile()
        if preset_profile:
            targets = self._apply_preset_overrides(targets, preset_profile, content_profile)

        debug(f"Generated targets for {genre} with preset '{self.config.mastering_profile}': "
              f"LUFS={targets['target_lufs']:.1f}, compression={targets['compression_ratio']:.1f}")

        return targets

    def _adapt_targets_to_content(self, genre_profile: GenreProfile,
                                 content_profile: dict[str, Any]) -> dict[str, Any]:
        """Adapt generic genre targets to specific content characteristics"""

        # Start with genre profile
        targets = {
            "target_lufs": genre_profile.target_lufs,
            "bass_boost_db": genre_profile.bass_boost_db,
            "midrange_clarity_db": genre_profile.midrange_clarity_db,
            "treble_enhancement_db": genre_profile.treble_enhancement_db,
            "compression_ratio": genre_profile.compression_ratio,
            "stereo_width": genre_profile.stereo_width,
            "mastering_intensity": genre_profile.mastering_intensity
        }

        # Adapt based on energy level
        energy_level = content_profile["energy_level"]
        if energy_level == "low":
            targets["target_lufs"] += 2.0  # Boost quiet content
            targets["compression_ratio"] *= 1.2
        elif energy_level == "high":
            targets["target_lufs"] -= 1.0  # Be more conservative with loud content
            targets["compression_ratio"] *= 0.8

        # Adapt based on dynamic range
        dynamic_range = content_profile["dynamic_range"]
        if dynamic_range > 25:  # High dynamic range
            targets["compression_ratio"] *= 0.7  # Less compression
            targets["mastering_intensity"] *= 0.8
        elif dynamic_range < 10:  # Low dynamic range (already compressed)
            targets["compression_ratio"] *= 0.5  # Much less compression
            targets["target_lufs"] -= 2.0  # Don't push it louder

        # Adapt based on spectral characteristics
        centroid = content_profile["spectral_centroid"]
        if centroid > 3500:  # Very bright content
            targets["treble_enhancement_db"] -= 1.0
        elif centroid < 1000:  # Very dark content
            targets["treble_enhancement_db"] += 1.0
            targets["midrange_clarity_db"] += 0.5

        # Adapt based on stereo information
        if content_profile["stereo_info"]["is_stereo"]:
            stereo_width = content_profile["stereo_info"]["width"]
            if stereo_width < 0.3:  # Narrow stereo
                targets["stereo_width"] = min(targets["stereo_width"] * 1.2, 1.0)
            elif stereo_width > 0.8:  # Very wide stereo
                targets["stereo_width"] = max(targets["stereo_width"] * 0.8, 0.3)

        # Apply adaptation strength from config
        adaptation_strength = self.config.adaptive.adaptation_strength
        for key in targets:
            if key != "target_lufs":  # Don't scale LUFS target
                # Get the corresponding genre profile value
                if key == "bass_boost_db":
                    genre_value = genre_profile.bass_boost_db
                elif key == "midrange_clarity_db":
                    genre_value = genre_profile.midrange_clarity_db
                elif key == "treble_enhancement_db":
                    genre_value = genre_profile.treble_enhancement_db
                elif key == "compression_ratio":
                    genre_value = genre_profile.compression_ratio
                elif key == "stereo_width":
                    genre_value = genre_profile.stereo_width
                else:
                    genre_value = targets[key]  # Use adapted value if no match

                # Blend between genre default and adapted value
                targets[key] = (genre_value * (1 - adaptation_strength) +
                              targets[key] * adaptation_strength)

        return targets

    def _apply_preset_overrides(self, targets: dict[str, Any],
                                 preset_profile: Any,
                                 content_profile: dict[str, Any]) -> dict[str, Any]:
        return apply_preset_overrides(self, targets, preset_profile, content_profile)

    def _apply_fingerprint_enhancements(self, targets: dict[str, Any],
                                         fingerprint: dict[str, float]) -> dict[str, Any]:
        return apply_fingerprint_enhancements(self, targets, fingerprint)
