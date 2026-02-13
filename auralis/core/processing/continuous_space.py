"""
Continuous Processing Space
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Maps audio fingerprints to continuous parameter space for adaptive processing.
Replaces discrete presets with intelligent parameter generation.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class ProcessingCoordinates:
    """
    Position in 3D processing space.

    The processing space has three primary axes derived from the 25D fingerprint:
    - Spectral Balance: Dark (bass-heavy) to Bright (treble-heavy)
    - Dynamic Range: Compressed (brick-walled) to Dynamic (high crest factor)
    - Energy Level: Quiet (low LUFS) to Loud (high LUFS)
    """
    spectral_balance: float  # 0.0 (dark/bass-heavy) to 1.0 (bright/treble-heavy)
    dynamic_range: float     # 0.0 (compressed/brick-walled) to 1.0 (dynamic/high crest)
    energy_level: float      # 0.0 (quiet/low LUFS) to 1.0 (loud/high LUFS)
    fingerprint: dict[str, float]  # Full 25D fingerprint for secondary parameters

    def __str__(self) -> str:
        return (f"ProcessingCoordinates("
                f"spectral={self.spectral_balance:.2f}, "
                f"dynamic={self.dynamic_range:.2f}, "
                f"energy={self.energy_level:.2f})")


@dataclass
class ProcessingParameters:
    """
    Complete set of DSP processing parameters.

    Generated from processing space coordinates and user preferences.
    """
    # Loudness normalization
    target_lufs: float          # Target integrated loudness (LUFS)
    peak_target_db: float       # Peak normalization target (dBFS)

    # EQ parameters
    eq_curve: dict[str, float]  # Frequency-specific gains and frequencies
    eq_blend: float             # EQ application strength (0.0 to 1.0)

    # Dynamics processing
    compression_params: dict[str, float]  # Compression settings
    expansion_params: dict[str, float]    # Expansion settings (de-mastering)
    dynamics_blend: float                 # Dynamics processing strength (0.0 to 1.0)

    # Limiting
    limiter_params: dict[str, float]      # Limiter settings

    # Stereo processing
    stereo_width_target: float            # Target stereo width (0.0 to 1.0)

    def __str__(self) -> str:
        return (f"ProcessingParameters("
                f"LUFS={self.target_lufs:.1f}, "
                f"peak={self.peak_target_db:.2f}dB, "
                f"eq_blend={self.eq_blend:.2f}, "
                f"dynamics_blend={self.dynamics_blend:.2f})")


@dataclass
class PreferenceVector:
    """
    User preference as a bias in processing space.

    Instead of rigid presets, preferences act as gentle biases that
    shift the processing behavior in desired directions.
    """
    # Spectral preference: -1.0 (darker) to +1.0 (brighter)
    spectral_bias: float = 0.0

    # Dynamic preference: -1.0 (more compression) to +1.0 (more dynamics)
    dynamic_bias: float = 0.0

    # Loudness preference: -1.0 (quieter) to +1.0 (louder)
    loudness_bias: float = 0.0

    # Bass boost: 0.0 (none) to 1.0 (strong)
    bass_boost: float = 0.0

    # Treble boost: 0.0 (none) to 1.0 (strong)
    treble_boost: float = 0.0

    # Stereo width preference: -1.0 (narrower) to +1.0 (wider)
    stereo_bias: float = 0.0

    @classmethod
    def from_preset_name(cls, preset: str) -> PreferenceVector:
        """
        Convert legacy preset names to preference vectors.

        This provides backward compatibility with the old preset system
        while allowing gradual migration to the continuous space.

        Args:
            preset: Preset name (adaptive, gentle, warm, bright, punchy, live)

        Returns:
            PreferenceVector representing the preset's characteristics
        """
        presets = {
            'adaptive': cls(),  # Neutral - pure content-driven processing

            'gentle': cls(
                dynamic_bias=0.3,      # Preserve dynamics more
                loudness_bias=-0.2,    # Quieter output
            ),

            'warm': cls(
                spectral_bias=-0.3,    # Darker/warmer tonality
                bass_boost=0.5,        # More bass
                treble_boost=-0.2,     # Less treble (smoother highs)
            ),

            'bright': cls(
                spectral_bias=0.5,     # Brighter tonality
                treble_boost=0.7,      # More treble
                bass_boost=-0.3,       # Less bass
            ),

            'punchy': cls(
                bass_boost=0.6,        # More bass punch
                dynamic_bias=-0.2,     # Allow more compression
                loudness_bias=0.3,     # Louder output
            ),

            'live': cls(
                dynamic_bias=0.4,      # Preserve live dynamics
                stereo_bias=0.2,       # Wider stereo field
                bass_boost=-0.2,       # Reduce bass (less mud)
            ),
        }

        return presets.get(preset.lower(), cls())

    def __str__(self) -> str:
        return (f"PreferenceVector("
                f"spectral={self.spectral_bias:+.1f}, "
                f"dynamic={self.dynamic_bias:+.1f}, "
                f"loudness={self.loudness_bias:+.1f})")


class ProcessingSpaceMapper:
    """
    Maps 25D audio fingerprints to 3D processing space coordinates.

    The mapper transforms the high-dimensional fingerprint into a compact
    3-dimensional representation that captures the essential characteristics
    for processing decisions:
    - Spectral Balance (dark to bright)
    - Dynamic Range (compressed to dynamic)
    - Energy Level (quiet to loud)
    """

    def map_fingerprint_to_space(self, fingerprint: dict[str, float]) -> ProcessingCoordinates:
        """
        Convert 25D fingerprint to 3D processing space position.

        Args:
            fingerprint: 25D audio fingerprint dictionary

        Returns:
            ProcessingCoordinates with position in 3D space
        """
        # X-Axis: Spectral Balance (0 = dark/bass-heavy, 1 = bright/treble-heavy)
        # Weighted combination of frequency distribution
        spectral_balance = self._calculate_spectral_balance(fingerprint)

        # Y-Axis: Dynamic Range (0 = compressed/brick-walled, 1 = dynamic/high crest)
        # Based on crest factor and variation
        dynamic_range = self._calculate_dynamic_range(fingerprint)

        # Z-Axis: Energy Level (0 = quiet, 1 = loud)
        # Based on LUFS loudness
        energy_level = self._calculate_energy_level(fingerprint)

        return ProcessingCoordinates(
            spectral_balance=np.clip(spectral_balance, 0.0, 1.0),
            dynamic_range=np.clip(dynamic_range, 0.0, 1.0),
            energy_level=np.clip(energy_level, 0.0, 1.0),
            fingerprint=fingerprint
        )

    def _calculate_spectral_balance(self, fp: dict[str, float]) -> float:
        """
        Calculate spectral balance from bass/mid/treble distribution.

        Strategy:
        - More bass, less treble → Lower score (darker)
        - Less bass, more treble → Higher score (brighter)
        - Uses actual frequency percentages, not just spectral centroid

        Args:
            fp: Fingerprint dictionary

        Returns:
            Spectral balance score (0.0 to 1.0)
        """
        # Normalize bass percentage (typical range 15-40%)
        # 40% bass → 0.0 (very dark), 15% bass → 1.0 (very bright)
        bass_normalized = 1.0 - np.clip((fp['bass_pct'] - 15.0) / 25.0, 0.0, 1.0)

        # Normalize air percentage (typical range 5-20%)
        # 5% air → 0.0, 20% air → 1.0
        air_normalized = np.clip((fp['air_pct'] - 5.0) / 15.0, 0.0, 1.0)

        # Normalize spectral centroid (typical range 1000-6000 Hz)
        centroid_normalized = np.clip((fp['spectral_centroid'] - 1000.0) / 5000.0, 0.0, 1.0)

        # Normalize presence (typical range 8-25%)
        presence_normalized = np.clip((fp['presence_pct'] - 8.0) / 17.0, 0.0, 1.0)

        # Weighted combination emphasizing actual frequency distribution
        spectral_balance = (
            0.35 * bass_normalized +        # Primary: bass content
            0.35 * air_normalized +         # Primary: air content
            0.15 * centroid_normalized +    # Secondary: centroid
            0.15 * presence_normalized      # Secondary: presence
        )

        return float(spectral_balance)

    def _calculate_dynamic_range(self, fp: dict[str, float]) -> float:
        """
        Calculate dynamic range position from crest factor and variation.

        Strategy:
        - Low crest (8-10 dB) → Brick-walled, score near 0
        - High crest (16-20 dB) → Dynamic, score near 1
        - Consider variation and consistency

        Args:
            fp: Fingerprint dictionary

        Returns:
            Dynamic range score (0.0 to 1.0)
        """
        # Map crest factor to 0-1 range (8-20 dB typical range)
        crest_normalized = np.clip((fp['crest_db'] - 8.0) / 12.0, 0.0, 1.0)

        # Consider dynamic range variation (how much DR changes)
        # High variation might indicate intentional dynamics
        variation_factor = fp.get('dynamic_range_variation', 0.0)

        # Loudness variation (quiet/loud sections)
        loudness_var = np.clip(fp.get('loudness_variation_std', 0.0) / 5.0, 0.0, 1.0)

        # Weighted combination
        dynamic_range = (
            0.5 * crest_normalized +      # Primary: crest factor
            0.3 * variation_factor +      # Secondary: variation
            0.2 * loudness_var            # Tertiary: loudness variation
        )

        return float(dynamic_range)

    def _calculate_energy_level(self, fp: dict[str, float]) -> float:
        """
        Calculate energy level from LUFS loudness.

        Strategy:
        - Very quiet (-30 LUFS) → Score near 0
        - Very loud (-10 LUFS) → Score near 1
        - Typical range: -30 to -10 LUFS

        Args:
            fp: Fingerprint dictionary

        Returns:
            Energy level score (0.0 to 1.0)
        """
        # Map LUFS to 0-1 range (-30 to -10 LUFS typical range)
        # Quieter material has lower energy score
        energy_level = np.clip((fp['lufs'] + 30.0) / 20.0, 0.0, 1.0)

        return float(energy_level)
