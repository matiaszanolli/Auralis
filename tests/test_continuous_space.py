# -*- coding: utf-8 -*-

"""
Tests for Continuous Processing Space
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests coordinate mapping, parameter generation, and preference biasing.
"""

import pytest

from auralis.core.processing.continuous_space import (
    PreferenceVector,
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

    def test_energy_coordinate_is_monotonic_without_clipped_ranges(self):
        mapper = ProcessingSpaceMapper()
        values = [
            mapper.map_fingerprint_to_space(
                self._fingerprint(lufs=lufs)
            ).energy_level
            for lufs in (-60.0, -40.0, -30.0, -20.0, -14.0, -10.0, -5.0, 0.0)
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
            energy_level=0.2,       # Very quiet
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

        # Should have significant headroom (dynamic material)
        assert params.peak_target_db <= -0.8, f"Expected headroom (< -0.8), got {params.peak_target_db:.2f}"

        # Should have minimal compression
        assert params.compression_params['amount'] < 0.4, f"Expected light compression (< 0.4), got {params.compression_params['amount']:.2f}"

        # Expansion influence should approach zero smoothly.
        assert params.expansion_params['amount'] < 0.05

    def test_loud_compressed_track_parameters(self):
        """Test parameters for loud, compressed track (should be expanded)"""
        coords = ProcessingCoordinates(
            spectral_balance=0.5,   # Balanced
            dynamic_range=0.2,      # Very compressed
            energy_level=0.9,       # Very loud
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

        # Should have less headroom (compressed material)
        assert params.peak_target_db >= -0.5, f"Expected less headroom (> -0.5), got {params.peak_target_db:.2f}"

        # Compression influence should approach zero smoothly.
        assert params.compression_params['amount'] < 0.15

        # Should expand to restore dynamics
        assert params.expansion_params['amount'] > 0.5, f"Expected expansion (> 0.5), got {params.expansion_params['amount']:.2f}"
        assert params.expansion_params['target_crest_increase'] >= 2.0, f"Expected crest increase >= 2dB, got {params.expansion_params['target_crest_increase']:.1f}"

    def test_bass_deficient_track_eq(self):
        """Test EQ curve generation for bass-deficient track"""
        coords = ProcessingCoordinates(
            spectral_balance=0.7,   # Bright (lacking bass)
            dynamic_range=0.5,
            energy_level=0.6,
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

        # Air above the corpus center receives a signed cut.
        assert params.eq_curve['high_shelf_gain'] < 0.0

        # Should have high EQ blend (unbalanced material)
        assert params.eq_blend > 0.5


class TestPreferenceVector:
    """Test user preference system"""

    def test_preset_to_preference_conversion(self):
        """Test legacy preset conversion to preference vectors"""
        warm = PreferenceVector.from_preset_name('warm')
        assert warm.spectral_bias < 0, "Warm should be darker (negative spectral bias)"
        assert warm.bass_boost > 0, "Warm should boost bass"

        bright = PreferenceVector.from_preset_name('bright')
        assert bright.spectral_bias > 0, "Bright should be brighter (positive spectral bias)"
        assert bright.treble_boost > 0, "Bright should boost treble"

        punchy = PreferenceVector.from_preset_name('punchy')
        assert punchy.bass_boost > 0, "Punchy should boost bass"
        assert punchy.loudness_bias > 0, "Punchy should be louder"

        gentle = PreferenceVector.from_preset_name('gentle')
        assert gentle.dynamic_bias > 0, "Gentle should preserve dynamics"
        assert gentle.loudness_bias < 0, "Gentle should be quieter"

    def test_preference_bias_application(self):
        """Test that preferences bias parameter generation"""
        coords = ProcessingCoordinates(
            spectral_balance=0.5,
            dynamic_range=0.5,
            energy_level=0.5,
            fingerprint={
                'bass_pct': 0.28, 'mid_pct': 0.35, 'air_pct': 0.012,
                'presence_pct': 0.015, 'crest_db': 12.0, 'lufs': -16.0,
                'stereo_width': 0.7
            }
        )

        generator = ContinuousParameterGenerator()

        # No preference (baseline)
        params_neutral = generator.generate_parameters(coords, None)

        # Bass boost preference
        bass_pref = PreferenceVector(bass_boost=0.8)
        params_bass = generator.generate_parameters(coords, bass_pref)

        # Bass boost should increase low shelf gain
        assert params_bass.eq_curve['low_shelf_gain'] > params_neutral.eq_curve['low_shelf_gain'], \
            "Bass preference should increase bass EQ"

        # Loudness preference
        loud_pref = PreferenceVector(loudness_bias=0.5)
        params_loud = generator.generate_parameters(coords, loud_pref)

        # Loudness bias should increase target LUFS
        assert params_loud.target_lufs > params_neutral.target_lufs, \
            "Loudness preference should increase target LUFS"

        # Dynamic preservation preference
        dynamic_pref = PreferenceVector(dynamic_bias=0.5)
        params_dynamic = generator.generate_parameters(coords, dynamic_pref)

        # Dynamic bias should reduce compression amount
        assert params_dynamic.compression_params['amount'] <= params_neutral.compression_params['amount'], \
            "Dynamic preference should reduce compression"


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
