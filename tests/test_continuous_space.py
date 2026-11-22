# -*- coding: utf-8 -*-

"""
Tests for Continuous Processing Space
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests coordinate mapping and parameter generation.
"""

import pytest

from auralis.core.processing.continuous_space import (
    ProcessingCoordinates,
    ProcessingSpaceMapper,
)
from auralis.core.processing.parameter_generator import ContinuousParameterGenerator


class TestProcessingSpaceMapper:
    """Test fingerprint to coordinate mapping"""

    @staticmethod
    def _fingerprint(**overrides):
        fingerprint = {
            'sub_bass_pct': 0.05,
            'bass_pct': 0.46,
            'low_mid_pct': 0.15,
            'mid_pct': 0.22,
            'upper_mid_pct': 0.07,
            'presence_pct': 0.03,
            'air_pct': 0.01,
            'spectral_centroid': 0.0986,
            'crest_db': 13.4207,
            'dynamic_range_variation': 0.5,
            'loudness_variation_std': 1.6336,
            'lufs': -14.3887,
            'stereo_width': 0.30,
            'phase_correlation': 0.70,
        }
        fingerprint.update(overrides)
        return fingerprint

    def test_spectral_coordinate_is_strictly_continuous(self):
        mapper = ProcessingSpaceMapper()
        fingerprints = [
            self._fingerprint(
                sub_bass_pct=0.10,
                bass_pct=0.68 - shift,
                low_mid_pct=0.12,
                upper_mid_pct=0.03 + shift * 0.35,
                presence_pct=0.01 + shift * 0.35,
                air_pct=0.005 + shift * 0.30,
                spectral_centroid=0.04 + shift * 0.22,
            )
            for shift in (0.00, 0.08, 0.16, 0.24, 0.32)
        ]

        values = [
            mapper.map_fingerprint_to_space(fp).spectral_balance
            for fp in fingerprints
        ]

        assert all(0.0 < value < 1.0 for value in values)
        assert all(left < right for left, right in zip(values, values[1:]))

    def test_dynamic_coordinate_is_monotonic_without_plateaus(self):
        mapper = ProcessingSpaceMapper()
        values = [
            mapper.map_fingerprint_to_space(
                self._fingerprint(crest_db=crest)
            ).dynamic_range
            for crest in (5.0, 8.0, 11.0, 14.0, 18.0, 24.0)
        ]

        assert all(0.0 < value < 1.0 for value in values)
        assert all(left < right for left, right in zip(values, values[1:]))

    def test_loudness_variation_changes_dynamic_coordinate_smoothly(self):
        mapper = ProcessingSpaceMapper()
        values = [
            mapper.map_fingerprint_to_space(
                self._fingerprint(loudness_variation_std=variation)
            ).dynamic_range
            for variation in (0.0, 0.25, 1.0, 2.5, 6.0, 15.0)
        ]

        assert all(0.0 < value < 1.0 for value in values)
        assert all(left < right for left, right in zip(values, values[1:]))



class TestContinuousParameterGenerator:
    """Test parameter generation from coordinates"""

    def test_quiet_dynamic_track_parameters(self):
        """Test parameters for quiet, dynamic track (should be raised and preserved)"""
        coords = ProcessingCoordinates(
            spectral_balance=0.5,   # Balanced
            dynamic_range=0.8,      # Very dynamic
            fingerprint={
                'bass_pct': 0.28, 'mid_pct': 0.35, 'air_pct': 0.12,
                'presence_pct': 0.15, 'crest_db': 16.0, 'lufs': -25.0,
                'stereo_width': 0.6
            }
        )

        generator = ContinuousParameterGenerator()
        params = generator.generate_parameters(coords)

        # Should raise LUFS significantly but preserve dynamics
        assert -18.0 <= params.target_lufs <= -14.0, f"Expected raised LUFS (-18 to -14), got {params.target_lufs:.1f}"

        # Should have minimal compression
        assert params.compression_params['amount'] < 0.4, f"Expected light compression (< 0.4), got {params.compression_params['amount']:.2f}"

    def test_loud_compressed_track_parameters(self):
        """Test parameters for loud, compressed track (should be expanded)"""
        coords = ProcessingCoordinates(
            spectral_balance=0.5,   # Balanced
            dynamic_range=0.2,      # Very compressed
            fingerprint={
                'bass_pct': 0.28, 'mid_pct': 0.35, 'air_pct': 0.12,
                'presence_pct': 0.15, 'crest_db': 9.0, 'lufs': -10.0,
                'stereo_width': 0.7
            }
        )

        generator = ContinuousParameterGenerator()
        params = generator.generate_parameters(coords)

        # Should preserve loudness (already loud)
        assert -12.0 <= params.target_lufs <= -9.0, f"Expected preserved loudness (-12 to -9), got {params.target_lufs:.1f}"

        # Compression influence should approach zero smoothly.
        assert params.compression_params['amount'] < 0.15

    def test_bass_deficient_track_eq(self):
        """Test EQ curve generation for bass-deficient track"""
        coords = ProcessingCoordinates(
            spectral_balance=0.7,   # Bright (lacking bass)
            dynamic_range=0.5,
            fingerprint={
                'bass_pct': 0.15,
                'mid_pct': 0.35,
                'air_pct': 0.018,
                'presence_pct': 0.020,
                'crest_db': 12.0,
                'lufs': -14.0,
                'stereo_width': 0.7
            }
        )

        generator = ContinuousParameterGenerator()
        params = generator.generate_parameters(coords)

        # Should boost bass significantly
        assert params.eq_curve['low_shelf_gain'] > 1.0, f"Expected bass boost (> 1.0), got {params.eq_curve['low_shelf_gain']:.2f}"

        # The air share does not drive the shelf: the fingerprint analyses at 22.05 kHz,
        # so its 8-20 kHz band stops at 11 kHz and is too noisy to correct from.
        assert params.eq_curve['high_shelf_gain'] == 0.0

        # Should have high EQ blend (unbalanced material)
        assert params.eq_blend > 0.5


class TestEndToEndProcessing:
    """Test complete coordinate → parameters pipeline"""

    def test_magazine_shot_by_both_sides(self):
        """Test with Magazine track fingerprint (real data)"""
        # This is the track you tested - narrow, needs bass and stereo expansion
        fingerprint = {
            'sub_bass_pct': 0.05,
            'bass_pct': 0.22,
            'low_mid_pct': 0.18,
            'mid_pct': 0.38,
            'upper_mid_pct': 0.09,
            'air_pct': 0.02,
            'presence_pct': 0.06,
            'spectral_centroid': 0.20,
            'crest_db': 14.5,           # Good dynamics
            'dynamic_range_variation': 0.6,
            'loudness_variation_std': 3.0,
            'lufs': -15.0,              # Moderate loudness
            'stereo_width': 0.45,       # Narrow (needs expansion)
            'phase_correlation': 0.92,
        }

        mapper = ProcessingSpaceMapper()
        coords = mapper.map_fingerprint_to_space(fingerprint)

        generator = ContinuousParameterGenerator()
        params = generator.generate_parameters(coords)

        # Should boost bass (deficit)
        assert params.eq_curve['low_shelf_gain'] > 1.0, \
            f"Expected significant bass boost (> 1.0dB), got {params.eq_curve['low_shelf_gain']:.2f}"

        # The continuous width target moves upward from the measured 0.45.
        assert params.stereo_width_target > fingerprint['stereo_width']

        # Should preserve dynamics (already good)
        assert params.compression_params['amount'] <= 0.5, \
            f"Expected light compression (<= 0.5), got {params.compression_params['amount']:.2f}"

        # Should raise loudness moderately
        assert -15.0 <= params.target_lufs <= -12.0, \
            f"Expected moderate loudness raise (-15 to -12), got {params.target_lufs:.1f}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


class TestNoPreferenceMachinery:
    """The PreferenceVector bias layer is gone (#6123): it only ever saw the neutral vector."""

    def test_generate_parameters_takes_coordinates_and_an_optional_target(self):
        import inspect

        params = list(inspect.signature(ContinuousParameterGenerator.generate_parameters).parameters)
        assert params == ["self", "coords", "target_spectrum"]

    def test_the_preference_vector_type_no_longer_exists(self):
        import auralis.core.processing.continuous_space as space
        import auralis.core.processing.continuous_space_types as types

        assert not hasattr(space, "PreferenceVector") and not hasattr(types, "PreferenceVector")
