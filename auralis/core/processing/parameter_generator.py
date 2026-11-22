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
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


from .continuous_space_types import ProcessingCoordinates, ProcessingParameters
from .parameter_generator_dynamics import (
    calculate_target_lufs as _calculate_target_lufs_impl,
    generate_compression as _generate_compression_impl,
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
    parameters for that position.
    """

    def generate_parameters(
        self,
        coords: ProcessingCoordinates,
        target_spectrum: dict[str, float] | None = None,
    ) -> ProcessingParameters:
        """
        Generate all processing parameters from space coordinates.

        Args:
            coords: Position in 3D processing space
            target_spectrum: Optional target band fractions from the soft k-NN
                reference cloud (see target_derivation.derive_target). When
                provided, the EQ curve is computed as a signed, capped delta
                from source toward target (symmetric: can boost OR cut).
                When None, falls back to the legacy deficit-based curve.

        Returns:
            ProcessingParameters with all DSP settings
        """
        eq_curve = (
            self._generate_eq_curve_from_target(coords, target_spectrum)
            if target_spectrum is not None
            else self._generate_eq_curve(coords)
        )

        # Generate parameters for each processing stage
        return ProcessingParameters(
            # Loudness targets
            target_lufs=self._calculate_target_lufs(coords),

            # EQ curve
            eq_curve=eq_curve,
            eq_blend=self._calculate_eq_blend(coords),

            # Dynamics
            compression_params=self._generate_compression(coords),

            # Stereo processing
            stereo_width_target=self._calculate_stereo_width(coords),
        )

    # -- Loudness/dynamics family (parameter_generator_dynamics.py) --------

    def _calculate_target_lufs(self, coords: ProcessingCoordinates) -> float:
        """Calculate target LUFS. See parameter_generator_dynamics.calculate_target_lufs."""
        return _calculate_target_lufs_impl(coords)

    def _generate_compression(self, coords: ProcessingCoordinates) -> dict[str, float]:
        """Generate compression parameters. See parameter_generator_dynamics.generate_compression."""
        return _generate_compression_impl(coords)

    # -- EQ family (parameter_generator_eq.py) ------------------------------

    def _generate_eq_curve(self, coords: ProcessingCoordinates) -> dict[str, float]:
        """Generate the legacy deficit-based EQ curve. See parameter_generator_eq.generate_eq_curve."""
        return _generate_eq_curve_impl(coords)

    def _generate_eq_curve_from_target(
        self,
        coords: ProcessingCoordinates,
        target_spectrum: dict[str, float],
    ) -> dict[str, float]:
        """Compute the delta-from-target EQ curve. See parameter_generator_eq.generate_eq_curve_from_target."""
        return _generate_eq_curve_from_target_impl(coords, target_spectrum)

    def _calculate_eq_blend(self, coords: ProcessingCoordinates) -> float:
        """Calculate how much EQ to apply. See parameter_generator_eq.calculate_eq_blend."""
        return _calculate_eq_blend_impl(coords)

    # -- Stereo family (parameter_generator_stereo.py) ----------------------

    def _calculate_stereo_width(self, coords: ProcessingCoordinates) -> float:
        """Calculate target stereo width. See parameter_generator_stereo.calculate_stereo_width."""
        return _calculate_stereo_width_impl(coords)
