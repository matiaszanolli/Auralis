"""
Continuous Processing Space
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Maps audio fingerprints to continuous parameter space for adaptive processing.
Replaces discrete presets with intelligent parameter generation.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import math
from dataclasses import dataclass


def _smooth_unit(value: float, center: float, scale: float) -> float:
    """Map an unbounded measurement smoothly into the open interval ``(0, 1)``.

    NaN maps to the neutral midpoint: ``tanh(nan)`` is ``nan``, and one NaN
    coordinate makes every generated parameter NaN (#5505). ±Inf saturates to
    the interval's ends, exactly like a large-but-finite input already does
    through ``tanh`` — collapsing Inf to the midpoint conflated "undefined"
    with "extreme" (#5534).
    """
    value = float(value)
    if math.isnan(value):
        return 0.5
    if value == math.inf:
        return 1.0
    if value == -math.inf:
        return 0.0
    return 0.5 + 0.5 * math.tanh((value - center) / (2.0 * scale))


from .continuous_space_types import PreferenceVector, ProcessingCoordinates, ProcessingParameters  # noqa: E402


class ProcessingSpaceMapper:
    """
    Maps 25D audio fingerprints to 3D processing space coordinates.

    The mapper transforms the high-dimensional fingerprint into a compact
    3-dimensional representation that captures the essential characteristics
    for processing decisions:
    - Relative spectral balance
    - Dynamic variation
    - Integrated energy

    All mappings are smooth and strictly monotonic. The calibration constants
    are robust centers and scales from a deterministic 512-track corpus sample
    (July 2026); they center the coordinate system without creating content
    classes, branch boundaries, or clipped acceptance ranges.
    """

    _SPECTRAL_LOG_RATIO_CENTER = -1.6901
    _SPECTRAL_LOG_RATIO_SCALE = 0.5045
    _CENTROID_CENTER = 0.0986
    _CENTROID_SCALE = 0.0240
    _CREST_CENTER_DB = 13.4207
    _CREST_SCALE_DB = 1.7884
    _LOUDNESS_VARIATION_LOG_CENTER = 0.9680
    _LOUDNESS_VARIATION_LOG_SCALE = 0.3855
    _LUFS_CENTER = -14.3887
    _LUFS_SCALE = 2.7732
    _ENERGY_EPSILON = 1e-8

    def map_fingerprint_to_space(self, fingerprint: dict[str, float]) -> ProcessingCoordinates:
        """
        Convert 25D fingerprint to 3D processing space position.

        Args:
            fingerprint: 25D audio fingerprint dictionary

        Returns:
            ProcessingCoordinates with position in 3D space
        """
        spectral_balance = self._calculate_spectral_balance(fingerprint)
        dynamic_range = self._calculate_dynamic_range(fingerprint)
        energy_level = self._calculate_energy_level(fingerprint)

        return ProcessingCoordinates(
            spectral_balance=spectral_balance,
            dynamic_range=dynamic_range,
            energy_level=energy_level,
            fingerprint=fingerprint
        )

    def _calculate_spectral_balance(self, fp: dict[str, float]) -> float:
        """
        Calculate a continuous spectral coordinate from band energy and centroid.

        Args:
            fp: Fingerprint dictionary

        Returns:
            Spectral balance score (0.0 to 1.0)
        """
        low_energy = (
            fp.get('sub_bass_pct', 0.0)
            + fp['bass_pct']
            + fp.get('low_mid_pct', 0.0)
        )
        high_energy = (
            fp.get('upper_mid_pct', 0.0)
            + fp['presence_pct']
            + fp['air_pct']
        )
        low_total = low_energy + self._ENERGY_EPSILON
        high_total = high_energy + self._ENERGY_EPSILON
        # The band fractions are sanitized (no NaN/Inf) but not clamped, so a
        # tiny negative sum can push a total through zero (#5534). Each side
        # of the ratio saturates monotonically toward its asymptote as it
        # approaches zero (log -> ±Inf -> _smooth_unit's end values), so
        # continue that saturation instead of dividing by zero or jumping to
        # the neutral fallback. NaN energies keep falling through to the NaN
        # branch and stay neutral (#5505).
        if low_total <= 0.0:
            log_high_low = math.inf
        elif high_total <= 0.0:
            log_high_low = -math.inf
        else:
            ratio = high_total / low_total
            if math.isnan(ratio):
                log_high_low = math.nan
            elif ratio <= 0.0:
                # Tiny/huge underflow: the limit of the curve, not an error.
                log_high_low = -math.inf
            else:
                log_high_low = math.log(ratio)

        band_coordinate = _smooth_unit(
            log_high_low,
            self._SPECTRAL_LOG_RATIO_CENTER,
            self._SPECTRAL_LOG_RATIO_SCALE,
        )
        centroid_coordinate = _smooth_unit(
            fp['spectral_centroid'],
            self._CENTROID_CENTER,
            self._CENTROID_SCALE,
        )

        return float(0.7 * band_coordinate + 0.3 * centroid_coordinate)

    def _calculate_dynamic_range(self, fp: dict[str, float]) -> float:
        """
        Calculate a continuous dynamics coordinate.

        Args:
            fp: Fingerprint dictionary

        Returns:
            Dynamic range score (0.0 to 1.0)
        """
        crest_coordinate = _smooth_unit(
            fp['crest_db'],
            self._CREST_CENTER_DB,
            self._CREST_SCALE_DB,
        )
        loudness_variation = max(0.0, fp.get('loudness_variation_std', 0.0))
        variation_coordinate = _smooth_unit(
            math.log1p(loudness_variation),
            self._LOUDNESS_VARIATION_LOG_CENTER,
            self._LOUDNESS_VARIATION_LOG_SCALE,
        )

        # ``dynamic_range_variation`` is intentionally excluded here. The
        # July-2026 corpus pass found the existing metric saturated at 1.0 for
        # every one of 508 successful tracks, so it carries no mastering signal.
        return float(0.75 * crest_coordinate + 0.25 * variation_coordinate)

    def _calculate_energy_level(self, fp: dict[str, float]) -> float:
        """
        Calculate a continuous energy coordinate from integrated loudness.

        Args:
            fp: Fingerprint dictionary

        Returns:
            Energy level score (0.0 to 1.0)
        """
        return _smooth_unit(fp['lufs'], self._LUFS_CENTER, self._LUFS_SCALE)
