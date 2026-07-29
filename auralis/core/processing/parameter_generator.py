"""
Continuous Parameter Generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generates DSP processing parameters from processing space coordinates.
Implements intelligent parameter selection based on audio characteristics.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from .continuous_space import (
    PreferenceVector,
    ProcessingCoordinates,
    ProcessingParameters,
)


def _signed_band_gain(
    source_fraction: float,
    center_fraction: float,
    limit_db: float,
    transition_db: float = 6.0,
) -> float:
    """Return a smooth signed gain from a source/center energy ratio."""
    epsilon = 1e-8
    delta_db = 10.0 * np.log10(
        (center_fraction + epsilon) / (source_fraction + epsilon)
    )
    return float(limit_db * np.tanh(delta_db / transition_db))


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
        user_preference: PreferenceVector | None = None,
        target_spectrum: dict[str, float] | None = None,
    ) -> ProcessingParameters:
        """
        Generate all processing parameters from space coordinates.

        Args:
            coords: Position in 3D processing space
            user_preference: Optional user preference vector to bias parameters
            target_spectrum: Optional target band fractions from the soft k-NN
                reference cloud (see target_derivation.derive_target). When
                provided, the EQ curve is computed as a signed, capped delta
                from source toward target (symmetric: can boost OR cut).
                When None, falls back to the legacy deficit-based curve.

        Returns:
            ProcessingParameters with all DSP settings
        """
        # Apply user preference bias if provided
        if user_preference:
            coords = self._apply_preference_bias(coords, user_preference)

        eq_curve = (
            self._generate_eq_curve_from_target(coords, target_spectrum, user_preference)
            if target_spectrum is not None
            else self._generate_eq_curve(coords, user_preference)
        )

        # Generate parameters for each processing stage
        return ProcessingParameters(
            # Loudness targets
            target_lufs=self._calculate_target_lufs(coords, user_preference),
            peak_target_db=self._calculate_peak_target(coords, user_preference),

            # EQ curve
            eq_curve=eq_curve,
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
        preference: PreferenceVector | None
    ) -> float:
        """
        Calculate target LUFS based on input energy and dynamic range.

        The lift approaches a dynamics-aware maximum smoothly as the source
        moves below the reference loudness. No source category or coordinate
        boundary selects a different formula.

        Args:
            coords: Processing space coordinates
            preference: Optional user preference

        Returns:
            Target LUFS value
        """
        dynamics = coords.dynamic_range
        fp = coords.fingerprint

        input_lufs = fp.get('lufs', -14.0)
        reference_lufs = -12.0
        softness_db = 0.75
        loudness_gap = reference_lufs - input_lufs
        desired_lift = softness_db * np.logaddexp(
            0.0, loudness_gap / softness_db
        )
        maximum_lift = 8.25 - dynamics
        gain_db = maximum_lift * np.tanh(desired_lift / maximum_lift)
        target_lufs = input_lufs + gain_db

        # Apply user loudness preference if provided
        # This is applied AFTER automatic boost calculation
        if preference:
            # Loudness bias affects target (-1 = -2dB quieter, +1 = +2dB louder)
            preference_adjustment = preference.loudness_bias * 2.0
            target_lufs += preference_adjustment

        # Clamp to reasonable range
        # Minimum: -28 dB (very quiet material)
        # Maximum: -2 dB (prevent excessive clipping risk)
        return float(np.clip(target_lufs, -28.0, -2.0))

    def _calculate_peak_target(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
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
        return float(np.clip(peak_target, -1.5, -0.2))

    def _generate_eq_curve(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
    ) -> dict[str, float]:
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

        # Robust centers from the deterministic 512-track corpus sample. They
        # define the origin of a signed continuous correction, not an ideal
        # profile or a pass/fail range. ``tanh`` approaches the DSP envelope
        # smoothly instead of clipping bands into deficit/excess classes.
        low_shelf_gain = _signed_band_gain(fp['bass_pct'], 0.4561, 4.0)
        low_mid_gain = _signed_band_gain(
            fp.get('low_mid_pct', 0.1009), 0.1009, 2.0
        )
        mid_gain = _signed_band_gain(fp['mid_pct'], 0.1983, 2.0)
        high_mid_source = fp.get('upper_mid_pct', 0.0733) + fp['presence_pct']
        high_mid_gain = _signed_band_gain(high_mid_source, 0.1030, 3.0)
        high_shelf_gain = _signed_band_gain(fp['air_pct'], 0.0063, 3.0)

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
            'low_shelf_gain': float(5.0 * np.tanh(low_shelf_gain / 5.0)),
            'low_mid_gain': float(3.0 * np.tanh(low_mid_gain / 3.0)),
            'mid_gain': float(2.0 * np.tanh(mid_gain / 2.0)),
            'high_mid_gain': float(4.0 * np.tanh(high_mid_gain / 4.0)),
            'high_shelf_gain': float(4.0 * np.tanh(high_shelf_gain / 4.0)),

            # Frequencies (Hz)
            'low_shelf_freq': 200,
            'low_mid_freq': 500,
            'mid_freq': 1500,
            'high_mid_freq': 4000,
            'high_shelf_freq': 8000,
        }

    def _generate_eq_curve_from_target(
        self,
        coords: ProcessingCoordinates,
        target_spectrum: dict[str, float],
        preference: PreferenceVector | None,
    ) -> dict[str, float]:
        """Compute the 5-shelf curve via delta-from-target (Phase 4).

        Replaces the deficit-based math when the mastering pipeline has a
        reference cloud and was able to derive a target. Symmetric (can cut),
        capped per-band, smoothly saturated via tanh — see delta_eq.py.

        User preference still applies as additive bias on top of the delta
        curve, but with reduced strength since the cloud already encodes
        most of the "what should this sound like" intent.
        """
        from .delta_eq import compute_delta_eq, to_eq_curve

        delta_result = compute_delta_eq(coords.fingerprint, target_spectrum)
        curve = to_eq_curve(delta_result)

        # Apply user preference adjustments at half-strength (cloud carries
        # most of the intent; preference becomes a gentle nudge, not the
        # primary signal it was in the deficit-based path).
        if preference is not None:
            curve['low_shelf_gain']  += preference.bass_boost * 1.0
            curve['high_shelf_gain'] += preference.treble_boost * 1.0
            curve['high_mid_gain']   += preference.treble_boost * 0.75
            if preference.spectral_bias > 0:        # brighter
                curve['high_shelf_gain'] += preference.spectral_bias * 0.75
                curve['low_shelf_gain']  -= preference.spectral_bias * 0.5
            elif preference.spectral_bias < 0:      # darker
                curve['low_shelf_gain']  += abs(preference.spectral_bias) * 0.75
                curve['high_shelf_gain'] -= abs(preference.spectral_bias) * 0.5

        # Re-clamp to the existing ProcessingParameters envelope so
        # downstream EQProcessor sees values it expects.
        curve['low_shelf_gain']  = float(np.clip(curve['low_shelf_gain'],  -5.0, 5.0))
        curve['low_mid_gain']    = float(np.clip(curve['low_mid_gain'],    -3.0, 3.0))
        curve['mid_gain']        = float(np.clip(curve['mid_gain'],        -2.0, 2.0))
        curve['high_mid_gain']   = float(np.clip(curve['high_mid_gain'],   -4.0, 4.0))
        curve['high_shelf_gain'] = float(np.clip(curve['high_shelf_gain'], -4.0, 4.0))

        return curve

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

        epsilon = 1e-8
        deviations = (
            abs(np.log((fp['bass_pct'] + epsilon) / 0.4561)),
            abs(np.log((fp['air_pct'] + epsilon) / 0.0063)),
            abs(np.log((fp['mid_pct'] + epsilon) / 0.1983)),
        )
        mean_deviation = float(np.mean(deviations))
        eq_blend = 0.35 + 0.55 * (1.0 - np.exp(-mean_deviation))

        return float(eq_blend)

    def _generate_compression(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
    ) -> dict[str, float]:
        """
        Generate compression parameters.

        Compression strength follows a smooth bell over the dynamics axis:
        minimal near either extreme and strongest around the corpus center.

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

        compression_response = np.exp(
            -0.5 * ((effective_dynamics - 0.55) / 0.18) ** 2
        )
        return {
            'ratio': float(1.0 + 0.8 * compression_response),
            'threshold': float(-18.0 - 8.0 * effective_dynamics),
            'attack': float(12.0 + 18.0 * effective_dynamics),
            'release': float(120.0 + 130.0 * effective_dynamics),
            'amount': float(0.55 * compression_response),
        }

    def _generate_expansion(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
    ) -> dict[str, float]:
        """
        Generate expansion parameters (de-mastering).

        Expansion strength decays continuously as measured dynamics increase.

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

        inverse_dynamics = 1.0 - effective_dynamics
        return {
            'target_crest_increase': float(3.0 * inverse_dynamics),
            'amount': float(0.85 * inverse_dynamics ** 2),
        }

    def _calculate_dynamics_blend(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
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

        return float(np.clip(base_blend, 0.2, 0.9))

    def _generate_limiter(self, coords: ProcessingCoordinates) -> dict[str, float]:
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
        preference: PreferenceVector | None
    ) -> float:
        """
        Calculate target stereo width.

        Move continuously toward a conservative center while retaining most of
        the source width.

        Args:
            coords: Processing space coordinates
            preference: Optional user preference

        Returns:
            Target stereo width (0.0 to 1.0)
        """
        fp = coords.fingerprint
        current_width = fp.get('stereo_width', 0.7)

        target_width = (
            current_width
            + 0.45 * (0.72 - current_width)
            + 0.04 * (coords.spectral_balance - 0.5)
        )

        # Apply user stereo preference
        if preference:
            # Stereo bias shifts target (-1 = narrower, +1 = wider)
            target_width += preference.stereo_bias * 0.2

        return float(0.5 + 0.45 * np.tanh((target_width - 0.5) / 0.45))
