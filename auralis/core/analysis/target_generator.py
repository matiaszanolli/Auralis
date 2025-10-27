# -*- coding: utf-8 -*-

"""
Adaptive Target Generator
~~~~~~~~~~~~~~~~~~~~~~~~~~

Generate adaptive processing targets based on content analysis

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Any, Optional

from ..unified_config import UnifiedConfig, GenreProfile
from ...utils.logging import debug


class AdaptiveTargetGenerator:
    """Generate adaptive processing targets based on content analysis"""

    def __init__(self, config: UnifiedConfig, processor=None):
        """
        Initialize adaptive target generator

        Args:
            config: Unified configuration object
            processor: Optional reference to main processor for preference access
        """
        self.config = config
        self.processor = processor  # Reference to the main processor for preference access

    def generate_targets(self, content_profile: Dict[str, Any]) -> Dict[str, Any]:
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
            targets = self._apply_fingerprint_enhancements(targets, content_profile["fingerprint"], content_profile)

        # Apply preset overrides (blend with adaptive targets)
        preset_profile = self.config.get_preset_profile()
        if preset_profile:
            targets = self._apply_preset_overrides(targets, preset_profile, content_profile)

        # Apply user preference learning if available
        if self.processor and hasattr(self.processor, 'current_user_id') and self.processor.current_user_id:
            targets = self.processor.preference_engine.get_adaptive_parameters(
                self.processor.current_user_id,
                content_profile,
                targets
            )

        debug(f"Generated targets for {genre} with preset '{self.config.mastering_profile}': "
              f"LUFS={targets['target_lufs']:.1f}, compression={targets['compression_ratio']:.1f}")

        return targets

    def _adapt_targets_to_content(self, genre_profile: GenreProfile,
                                 content_profile: Dict[str, Any]) -> Dict[str, Any]:
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

    def _apply_preset_overrides(self, targets: Dict[str, Any],
                                preset_profile, content_profile: Dict[str, Any]) -> Dict[str, Any]:
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
        adaptive_lufs = modified_targets.get("target_lufs", -14.0)
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

    def _apply_fingerprint_enhancements(self, targets: Dict[str, Any],
                                       fingerprint: Dict[str, float],
                                       content_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply intelligent enhancements based on 25D audio fingerprint.

        This uses the complete acoustic fingerprint to make precise, content-aware
        adjustments beyond simple rule-based heuristics.

        Args:
            targets: Base processing targets
            fingerprint: 25D audio fingerprint
            content_profile: Full content analysis

        Returns:
            Enhanced targets with fingerprint-driven adjustments
        """
        debug("Applying 25D fingerprint-driven enhancements")

        enhanced = targets.copy()

        # 1. FREQUENCY-AWARE EQ ADJUSTMENTS (7D frequency distribution)
        # Use actual frequency distribution instead of guessing from spectral centroid
        bass_pct = fingerprint.get("bass_pct", 15.0)
        mid_pct = fingerprint.get("mid_pct", 30.0)
        presence_pct = fingerprint.get("presence_pct", 10.0)
        air_pct = fingerprint.get("air_pct", 5.0)

        # Bass adjustment: compensate for deficiency/excess
        if bass_pct < 10.0:  # Bass-light
            enhanced["bass_boost_db"] = targets.get("bass_boost_db", 0.0) + 1.5
        elif bass_pct > 25.0:  # Bass-heavy
            enhanced["bass_boost_db"] = targets.get("bass_boost_db", 0.0) - 1.0

        # Mid-range adjustment
        if mid_pct < 20.0:  # Mid-scooped
            enhanced["midrange_clarity_db"] = targets.get("midrange_clarity_db", 0.0) + 1.2
        elif mid_pct > 40.0:  # Mid-heavy
            enhanced["midrange_clarity_db"] = targets.get("midrange_clarity_db", 0.0) - 0.8

        # Presence/Air adjustment
        high_freq_total = presence_pct + air_pct
        if high_freq_total < 10.0:  # Dark mix
            enhanced["treble_enhancement_db"] = targets.get("treble_enhancement_db", 0.0) + 1.8
        elif high_freq_total > 25.0:  # Bright mix
            enhanced["treble_enhancement_db"] = targets.get("treble_enhancement_db", 0.0) - 1.2

        # 2. DYNAMICS-AWARE COMPRESSION (3D dynamics characteristics)
        lufs = fingerprint.get("lufs", -20.0)
        crest_db = fingerprint.get("crest_db", 15.0)
        bass_mid_ratio = fingerprint.get("bass_mid_ratio", 0.0)

        # Adjust compression based on current dynamics
        if crest_db > 16.0:  # High dynamic range (classical, live recordings)
            enhanced["compression_ratio"] = max(1.5, targets.get("compression_ratio", 2.5) * 0.6)
            debug(f"High crest ({crest_db:.1f}dB) - reducing compression to preserve dynamics")
        elif crest_db < 8.0:  # Already brick-walled (loudness wars)
            enhanced["compression_ratio"] = max(1.2, targets.get("compression_ratio", 2.5) * 0.3)
            debug(f"Low crest ({crest_db:.1f}dB) - minimal compression, already squashed")

        # Adjust target LUFS based on current loudness
        if lufs > -10.0:  # Already very loud
            enhanced["target_lufs"] = max(-14.0, targets.get("target_lufs", -14.0) - 2.0)
            debug(f"Already loud ({lufs:.1f}LUFS) - conservative target")
        elif lufs < -25.0:  # Very quiet
            enhanced["target_lufs"] = min(-12.0, targets.get("target_lufs", -14.0) + 2.0)
            debug(f"Quiet input ({lufs:.1f}LUFS) - boost target")

        # 3. TEMPORAL-AWARE PROCESSING (4D temporal characteristics)
        tempo_bpm = fingerprint.get("tempo_bpm", 120.0)
        rhythm_stability = fingerprint.get("rhythm_stability", 0.5)
        transient_density = fingerprint.get("transient_density", 0.5)

        # Adjust processing based on transient content
        if transient_density > 0.7:  # Drum-heavy, percussive
            # Preserve transients, reduce attack time
            enhanced["mastering_intensity"] = targets.get("mastering_intensity", 0.8) * 0.85
            debug(f"High transient density ({transient_density:.2f}) - preserving punch")
        elif transient_density < 0.3:  # Smooth, pad-heavy
            # Can be more aggressive
            enhanced["mastering_intensity"] = targets.get("mastering_intensity", 0.8) * 1.1

        # 4. HARMONIC-AWARE PROCESSING (3D harmonic characteristics)
        harmonic_ratio = fingerprint.get("harmonic_ratio", 0.5)
        pitch_stability = fingerprint.get("pitch_stability", 0.7)

        # Reduce processing intensity for highly harmonic content (vocals, strings)
        if harmonic_ratio > 0.7 and pitch_stability > 0.8:
            enhanced["mastering_intensity"] = targets.get("mastering_intensity", 0.8) * 0.9
            debug(f"Highly harmonic content (ratio={harmonic_ratio:.2f}) - gentle processing")

        # 5. STEREO-AWARE ADJUSTMENTS (2D stereo characteristics)
        stereo_width = fingerprint.get("stereo_width", 0.5)
        phase_correlation = fingerprint.get("phase_correlation", 1.0)

        # Adjust stereo width target based on current width
        if stereo_width < 0.3:  # Narrow/mono
            enhanced["stereo_width"] = min(0.9, targets.get("stereo_width", 0.7) + 0.2)
            debug(f"Narrow stereo ({stereo_width:.2f}) - expanding width")
        elif stereo_width > 0.85:  # Already very wide
            enhanced["stereo_width"] = max(0.5, targets.get("stereo_width", 0.7) - 0.1)
            debug(f"Already wide stereo ({stereo_width:.2f}) - slight reduction")

        # Check phase correlation - warn if problematic
        if phase_correlation < 0.5:
            debug(f"WARNING: Low phase correlation ({phase_correlation:.2f}) - potential mono compatibility issues")
            enhanced["stereo_width"] = min(enhanced.get("stereo_width", 0.7), 0.6)  # Reduce width

        # 6. VARIATION-AWARE ADJUSTMENTS (3D variation characteristics)
        loudness_variation = fingerprint.get("loudness_variation_std", 0.5)
        dynamic_range_variation = fingerprint.get("dynamic_range_variation", 0.5)

        # If material has intentional loudness variation (dynamics), preserve it
        if loudness_variation > 0.7:
            enhanced["compression_ratio"] = max(1.5, enhanced.get("compression_ratio", 2.5) * 0.8)
            debug(f"High loudness variation ({loudness_variation:.2f}) - preserving intentional dynamics")

        # Store fingerprint metadata for downstream processors
        enhanced["fingerprint_driven"] = True
        enhanced["fingerprint_version"] = "25D_v1"

        debug(f"Fingerprint enhancements applied: Bass {enhanced.get('bass_boost_db', 0):.1f}dB, "
              f"Comp {enhanced.get('compression_ratio', 0):.1f}:1, "
              f"Stereo width {enhanced.get('stereo_width', 0):.2f}")

        return enhanced


def create_adaptive_target_generator(config: UnifiedConfig,
                                     processor=None) -> AdaptiveTargetGenerator:
    """
    Factory function to create adaptive target generator

    Args:
        config: Unified configuration object
        processor: Optional reference to main processor

    Returns:
        Configured AdaptiveTargetGenerator instance
    """
    return AdaptiveTargetGenerator(config, processor)
