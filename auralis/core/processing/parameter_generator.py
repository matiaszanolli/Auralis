# -*- coding: utf-8 -*-

"""
Continuous Parameter Generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generates DSP processing parameters from processing space coordinates.
Implements intelligent parameter selection based on audio characteristics.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Optional, Dict, Any
from .continuous_space import (
    ProcessingCoordinates,
    ProcessingParameters,
    PreferenceVector
)


class ContinuousParameterGenerator:
    """
    Generates DSP parameters from processing space coordinates.

    This class implements the core intelligence of the continuous space system:
    it takes a position in 3D processing space and generates optimal DSP
    parameters for that position, optionally biased by user preferences.
    """

    def generate_parameters(
        self,
        coords: ProcessingCoordinates,
        user_preference: Optional[PreferenceVector] = None
    ) -> ProcessingParameters:
        """
        Generate all processing parameters from space coordinates.

        Args:
            coords: Position in 3D processing space
            user_preference: Optional user preference vector to bias parameters

        Returns:
            ProcessingParameters with all DSP settings
        """
        # Apply user preference bias if provided
        if user_preference:
            coords = self._apply_preference_bias(coords, user_preference)

        # Generate parameters for each processing stage
        return ProcessingParameters(
            # Loudness targets
            target_lufs=self._calculate_target_lufs(coords, user_preference),
            peak_target_db=self._calculate_peak_target(coords, user_preference),

            # EQ curve
            eq_curve=self._generate_eq_curve(coords, user_preference),
            eq_blend=self._calculate_eq_blend(coords),

            # Dynamics
            compression_params=self._generate_compression(coords, user_preference),
            expansion_params=self._generate_expansion(coords, user_preference),
            dynamics_blend=self._calculate_dynamics_blend(coords, user_preference),

            # Limiting
            limiter_params=self._generate_limiter(coords),

            # Stereo processing
            stereo_width_target=self._calculate_stereo_width(coords, user_preference),
        )

    def _apply_preference_bias(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector
    ) -> ProcessingCoordinates:
        """
        Apply user preference bias to coordinates.

        Preferences shift the coordinates in the processing space,
        affecting all downstream parameter calculations.

        Args:
            coords: Original coordinates
            preference: User preference vector

        Returns:
            Biased coordinates
        """
        # Apply bias with damping to prevent extreme values
        BIAS_STRENGTH = 0.3  # How much preferences affect coordinates (0-1)

        biased_spectral = coords.spectral_balance + (preference.spectral_bias * BIAS_STRENGTH)
        biased_dynamic = coords.dynamic_range + (preference.dynamic_bias * BIAS_STRENGTH)
        biased_energy = coords.energy_level + (preference.loudness_bias * BIAS_STRENGTH)

        return ProcessingCoordinates(
            spectral_balance=np.clip(biased_spectral, 0.0, 1.0),
            dynamic_range=np.clip(biased_dynamic, 0.0, 1.0),
            energy_level=np.clip(biased_energy, 0.0, 1.0),
            fingerprint=coords.fingerprint
        )

    def _calculate_target_lufs(
        self,
        coords: ProcessingCoordinates,
        preference: Optional[PreferenceVector]
    ) -> float:
        """
        Calculate target LUFS based on input energy and dynamic range.

        Strategy:
        - Quiet material (low energy): Raise to -16 to -14 LUFS
        - Loud material (high energy): Preserve or slightly reduce to -12 to -10 LUFS
        - Dynamic material: More conservative targets to preserve dynamics
        - Compressed material: Can push louder

        Args:
            coords: Processing space coordinates
            preference: Optional user preference

        Returns:
            Target LUFS value
        """
        energy = coords.energy_level
        dynamics = coords.dynamic_range

        # Base target: interpolate between quiet and loud extremes
        # Quiet tracks (energy=0) → -16 LUFS
        # Loud tracks (energy=1) → -10 LUFS
        base_lufs = -16.0 + (energy * 6.0)

        # Adjust for dynamics: preserve more headroom for dynamic material
        # Dynamic tracks (dynamics=1) → -2 dB quieter
        # Compressed tracks (dynamics=0) → No adjustment
        dynamics_adjustment = dynamics * -2.0

        # Apply user loudness preference if provided
        preference_adjustment = 0.0
        if preference:
            # Loudness bias affects target (-1 = -2dB, +1 = +2dB)
            preference_adjustment = preference.loudness_bias * 2.0

        target_lufs = base_lufs + dynamics_adjustment + preference_adjustment

        # Clamp to reasonable range
        return np.clip(target_lufs, -20.0, -8.0)

    def _calculate_peak_target(
        self,
        coords: ProcessingCoordinates,
        preference: Optional[PreferenceVector]
    ) -> float:
        """
        Calculate peak normalization target.

        Strategy:
        - Dynamic material: More headroom (-1.0 to -0.7 dB)
        - Compressed material: Less headroom (-0.5 to -0.2 dB)

        Args:
            coords: Processing space coordinates
            preference: Optional user preference

        Returns:
            Peak target in dBFS (negative value)
        """
        dynamics = coords.dynamic_range

        # More dynamics = more headroom
        # Dynamic (1.0) → -1.0 dB
        # Compressed (0.0) → -0.3 dB
        base_peak = -1.0 + (1.0 - dynamics) * 0.7

        # Apply loudness preference (affects headroom slightly)
        preference_adjustment = 0.0
        if preference:
            # Louder preference = less headroom
            preference_adjustment = preference.loudness_bias * 0.2

        peak_target = base_peak + preference_adjustment

        # Clamp to safe range
        return np.clip(peak_target, -1.5, -0.2)

    def _generate_eq_curve(
        self,
        coords: ProcessingCoordinates,
        preference: Optional[PreferenceVector]
    ) -> Dict[str, float]:
        """
        Generate frequency-specific EQ adjustments.

        Strategy:
        - Analyze what's missing (bass deficit, air deficit)
        - Boost deficits to bring balance
        - Respect user bass/treble preferences
        - Use actual frequency percentages from fingerprint

        Args:
            coords: Processing space coordinates
            preference: Optional user preference

        Returns:
            Dictionary with EQ curve parameters
        """
        fp = coords.fingerprint

        # Analyze deficits (what's missing compared to ideal)
        IDEAL_BASS = 28.0    # Ideal ~28% bass content
        IDEAL_AIR = 12.0     # Ideal ~12% air content
        IDEAL_MID = 35.0     # Ideal ~35% mid content

        # Calculate deficit ratios (how far from ideal)
        bass_deficit = max(0, IDEAL_BASS - fp['bass_pct']) / IDEAL_BASS     # 0-1
        air_deficit = max(0, IDEAL_AIR - fp['air_pct']) / IDEAL_AIR         # 0-1
        mid_deficit = max(0, IDEAL_MID - fp['mid_pct']) / IDEAL_MID         # 0-1

        # Base EQ gains (boost what's missing)
        # Use polynomial scaling for more aggressive boosts at higher deficits
        low_shelf_gain = (bass_deficit ** 0.7) * 4.0    # Up to +4 dB bass boost (more aggressive)
        high_shelf_gain = (air_deficit ** 0.7) * 3.0    # Up to +3 dB air boost
        high_mid_gain = (air_deficit ** 0.7) * 2.5      # Up to +2.5 dB presence
        low_mid_gain = 0.5                              # Always slight body enhancement
        mid_gain = (mid_deficit ** 0.8) * 1.5           # Up to +1.5 dB mid boost

        # Apply user preference adjustments
        if preference:
            # Bass preference (0 to 1) adds extra bass boost
            low_shelf_gain += preference.bass_boost * 2.0

            # Treble preference (0 to 1) adds extra treble boost
            high_shelf_gain += preference.treble_boost * 2.0
            high_mid_gain += preference.treble_boost * 1.5

            # Spectral bias shifts overall tonality
            if preference.spectral_bias > 0:  # Brighter
                high_shelf_gain += preference.spectral_bias * 1.5
                low_shelf_gain -= preference.spectral_bias * 1.0
            else:  # Darker
                low_shelf_gain += abs(preference.spectral_bias) * 1.5
                high_shelf_gain -= abs(preference.spectral_bias) * 1.0

        return {
            # Gains (dB)
            'low_shelf_gain': np.clip(low_shelf_gain, 0.0, 5.0),
            'low_mid_gain': np.clip(low_mid_gain, 0.0, 3.0),
            'mid_gain': np.clip(mid_gain, 0.0, 2.0),
            'high_mid_gain': np.clip(high_mid_gain, 0.0, 4.0),
            'high_shelf_gain': np.clip(high_shelf_gain, 0.0, 4.0),

            # Frequencies (Hz)
            'low_shelf_freq': 200,
            'low_mid_freq': 500,
            'mid_freq': 1500,
            'high_mid_freq': 4000,
            'high_shelf_freq': 8000,
        }

    def _calculate_eq_blend(self, coords: ProcessingCoordinates) -> float:
        """
        Calculate how much EQ to apply.

        Strategy:
        - Unbalanced material: More EQ (blend closer to 1.0)
        - Already balanced: Less EQ (blend closer to 0.5)

        Args:
            coords: Processing space coordinates

        Returns:
            EQ blend factor (0.0 to 1.0)
        """
        fp = coords.fingerprint

        # Measure spectral imbalance
        IDEAL_BASS = 30.0
        IDEAL_AIR = 12.0
        IDEAL_MID = 35.0

        bass_imbalance = abs(fp['bass_pct'] - IDEAL_BASS) / IDEAL_BASS
        air_imbalance = abs(fp['air_pct'] - IDEAL_AIR) / IDEAL_AIR
        mid_imbalance = abs(fp['mid_pct'] - IDEAL_MID) / IDEAL_MID

        # Average imbalance
        imbalance = (bass_imbalance + air_imbalance + mid_imbalance) / 3.0

        # More imbalance = more EQ (0.5 to 1.0 range)
        eq_blend = 0.5 + (np.clip(imbalance, 0, 1) * 0.5)

        return eq_blend

    def _generate_compression(
        self,
        coords: ProcessingCoordinates,
        preference: Optional[PreferenceVector]
    ) -> Dict[str, float]:
        """
        Generate compression parameters.

        Strategy:
        - Dynamic material (high dynamic_range): Very light or no compression
        - Moderately dynamic: Light compression to control peaks
        - Already compressed: No compression (expansion handled separately)

        Args:
            coords: Processing space coordinates
            preference: Optional user preference

        Returns:
            Compression parameters dictionary
        """
        dynamics = coords.dynamic_range

        # Adjust dynamics based on user preference
        effective_dynamics = dynamics
        if preference:
            # Dynamic bias affects how much we compress
            # Positive bias (preserve dynamics) → treat as more dynamic
            # Negative bias (allow compression) → treat as less dynamic
            effective_dynamics += preference.dynamic_bias * 0.3
            effective_dynamics = np.clip(effective_dynamics, 0.0, 1.0)

        # Very dynamic (>0.7): Minimal compression
        if effective_dynamics > 0.7:
            return {
                'ratio': 1.5,
                'threshold': -26.0,
                'attack': 25.0,
                'release': 250.0,
                'amount': 0.3,  # Apply very lightly
            }
        # Moderately dynamic (0.4-0.7): Light compression
        elif effective_dynamics > 0.4:
            return {
                'ratio': 1.8,
                'threshold': -22.0,
                'attack': 20.0,
                'release': 200.0,
                'amount': 0.5,
            }
        # Already compressed (<0.4): No compression
        else:
            return {
                'ratio': 1.0,
                'threshold': 0.0,
                'attack': 0.0,
                'release': 0.0,
                'amount': 0.0,  # Skip compression
            }

    def _generate_expansion(
        self,
        coords: ProcessingCoordinates,
        preference: Optional[PreferenceVector]
    ) -> Dict[str, float]:
        """
        Generate expansion parameters (de-mastering).

        Strategy:
        - Brick-walled material (low dynamics): Expand to restore dynamics
        - Already dynamic: No expansion

        Args:
            coords: Processing space coordinates
            preference: Optional user preference

        Returns:
            Expansion parameters dictionary
        """
        dynamics = coords.dynamic_range

        # Adjust dynamics based on user preference
        effective_dynamics = dynamics
        if preference:
            # Dynamic bias affects expansion threshold
            effective_dynamics += preference.dynamic_bias * 0.3
            effective_dynamics = np.clip(effective_dynamics, 0.0, 1.0)

        # Brick-walled (<0.3): Strong expansion
        if effective_dynamics < 0.3:
            return {
                'target_crest_increase': 4.0,  # +4 dB crest increase
                'amount': 1.0,
            }
        # Moderately compressed (0.3-0.5): Light expansion
        elif effective_dynamics < 0.5:
            return {
                'target_crest_increase': 2.0,  # +2 dB crest increase
                'amount': 0.6,
            }
        # Already dynamic (>0.5): No expansion
        else:
            return {
                'target_crest_increase': 0.0,
                'amount': 0.0,
            }

    def _calculate_dynamics_blend(
        self,
        coords: ProcessingCoordinates,
        preference: Optional[PreferenceVector]
    ) -> float:
        """
        Calculate dynamics processing blend.

        Args:
            coords: Processing space coordinates
            preference: Optional user preference

        Returns:
            Dynamics blend factor (0.0 to 1.0)
        """
        # Base blend from dynamic range
        # Less dynamic = more processing
        base_blend = 0.3 + ((1.0 - coords.dynamic_range) * 0.4)

        # User preference can increase/decrease
        if preference and preference.dynamic_bias != 0:
            # Positive bias (preserve dynamics) → less processing
            # Negative bias (allow compression) → more processing
            base_blend -= preference.dynamic_bias * 0.2

        return np.clip(base_blend, 0.2, 0.9)

    def _generate_limiter(self, coords: ProcessingCoordinates) -> Dict[str, float]:
        """
        Generate limiter parameters.

        Strategy:
        - Dynamic material: Gentler limiting (-3 to -2 dB threshold)
        - Compressed material: Tighter limiting (-1.5 to -1 dB threshold)

        Args:
            coords: Processing space coordinates

        Returns:
            Limiter parameters dictionary
        """
        dynamics = coords.dynamic_range

        # More dynamics = gentler limiting (more headroom)
        threshold = -3.0 + ((1.0 - dynamics) * 1.5)  # -3 to -1.5 dB
        release = 120.0 - (dynamics * 40.0)          # 120ms to 80ms

        return {
            'threshold': threshold,
            'release': release,
        }

    def _calculate_stereo_width(
        self,
        coords: ProcessingCoordinates,
        preference: Optional[PreferenceVector]
    ) -> float:
        """
        Calculate target stereo width.

        Strategy:
        - Narrow material (<0.5): Expand width to 0.7-0.8
        - Already wide (>0.85): Reduce slightly to avoid phase issues
        - Good width (0.5-0.85): Preserve or enhance slightly

        Args:
            coords: Processing space coordinates
            preference: Optional user preference

        Returns:
            Target stereo width (0.0 to 1.0)
        """
        fp = coords.fingerprint
        current_width = fp.get('stereo_width', 0.7)

        # Determine target based on current width
        if current_width < 0.5:
            # Narrow: expand to 0.7-0.8
            target_width = 0.7 + (coords.spectral_balance * 0.1)
        elif current_width > 0.85:
            # Too wide: reduce to safer level
            target_width = 0.75
        else:
            # Good width: preserve with slight enhancement
            target_width = current_width + 0.05

        # Apply user stereo preference
        if preference:
            # Stereo bias shifts target (-1 = narrower, +1 = wider)
            target_width += preference.stereo_bias * 0.2

        return np.clip(target_width, 0.5, 0.9)
