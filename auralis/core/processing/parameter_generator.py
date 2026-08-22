"""
Continuous Parameter Generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generates DSP processing parameters from processing space coordinates.
Implements intelligent parameter selection based on audio characteristics.

``ContinuousParameterGenerator`` is a thin facade: the per-family math
(dynamics/loudness, EQ, stereo) lives in sibling modules
(``parameter_generator_dynamics.py``, ``parameter_generator_eq.py``,
``parameter_generator_stereo.py``, #4511) and is composed here. The class
keeps every original method name as a real bound method (not just an
alias) so existing per-method mocking/patching (e.g.
``ContinuousParameterGenerator._generate_eq_curve_from_target``) keeps
working exactly as before the split.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from .continuous_space import (
    PreferenceVector,
    ProcessingCoordinates,
    ProcessingParameters,
)
from .parameter_generator_dynamics import (
    calculate_dynamics_blend as _calculate_dynamics_blend_impl,
    calculate_peak_target as _calculate_peak_target_impl,
    calculate_target_lufs as _calculate_target_lufs_impl,
    generate_compression as _generate_compression_impl,
    generate_expansion as _generate_expansion_impl,
    generate_limiter as _generate_limiter_impl,
)
from .parameter_generator_eq import (
    calculate_eq_blend as _calculate_eq_blend_impl,
    generate_eq_curve as _generate_eq_curve_impl,
    generate_eq_curve_from_target as _generate_eq_curve_from_target_impl,
)
from .parameter_generator_stereo import (
    calculate_stereo_width as _calculate_stereo_width_impl,
)

__all__ = ["ContinuousParameterGenerator"]


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

    # -- Loudness/dynamics family (parameter_generator_dynamics.py) --------

    def _calculate_target_lufs(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
    ) -> float:
        """Calculate target LUFS. See parameter_generator_dynamics.calculate_target_lufs."""
        return _calculate_target_lufs_impl(coords, preference)

    def _calculate_peak_target(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
    ) -> float:
        """Calculate peak normalization target. See parameter_generator_dynamics.calculate_peak_target."""
        return _calculate_peak_target_impl(coords, preference)

    def _generate_compression(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
    ) -> dict[str, float]:
        """Generate compression parameters. See parameter_generator_dynamics.generate_compression."""
        return _generate_compression_impl(coords, preference)

    def _generate_expansion(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
    ) -> dict[str, float]:
        """Generate expansion parameters. See parameter_generator_dynamics.generate_expansion."""
        return _generate_expansion_impl(coords, preference)

    def _calculate_dynamics_blend(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
    ) -> float:
        """Calculate dynamics processing blend. See parameter_generator_dynamics.calculate_dynamics_blend."""
        return _calculate_dynamics_blend_impl(coords, preference)

    def _generate_limiter(self, coords: ProcessingCoordinates) -> dict[str, float]:
        """Generate limiter parameters. See parameter_generator_dynamics.generate_limiter."""
        return _generate_limiter_impl(coords)

    # -- EQ family (parameter_generator_eq.py) ------------------------------

    def _generate_eq_curve(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
    ) -> dict[str, float]:
        """Generate the legacy deficit-based EQ curve. See parameter_generator_eq.generate_eq_curve."""
        return _generate_eq_curve_impl(coords, preference)

    def _generate_eq_curve_from_target(
        self,
        coords: ProcessingCoordinates,
        target_spectrum: dict[str, float],
        preference: PreferenceVector | None,
    ) -> dict[str, float]:
        """Compute the delta-from-target EQ curve. See parameter_generator_eq.generate_eq_curve_from_target."""
        return _generate_eq_curve_from_target_impl(coords, target_spectrum, preference)

    def _calculate_eq_blend(self, coords: ProcessingCoordinates) -> float:
        """Calculate how much EQ to apply. See parameter_generator_eq.calculate_eq_blend."""
        return _calculate_eq_blend_impl(coords)

    # -- Stereo family (parameter_generator_stereo.py) ----------------------

    def _calculate_stereo_width(
        self,
        coords: ProcessingCoordinates,
        preference: PreferenceVector | None
    ) -> float:
        """Calculate target stereo width. See parameter_generator_stereo.calculate_stereo_width."""
        return _calculate_stereo_width_impl(coords, preference)
