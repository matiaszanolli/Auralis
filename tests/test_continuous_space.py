# -*- coding: utf-8 -*-

"""
Tests for Continuous Processing Space
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests coordinate mapping, parameter generation, and preference biasing.
"""

import pytest
import numpy as np
from auralis.core.processing.continuous_space import (
    ProcessingCoordinates,
    ProcessingParameters,
    PreferenceVector,
    ProcessingSpaceMapper
)
from auralis.core.processing.parameter_generator import ContinuousParameterGenerator


class TestProcessingSpaceMapper:
    """Test fingerprint to coordinate mapping"""

    def test_dark_compressed_quiet_track(self):
        """Test mapping for dark, compressed, quiet track (typical mastered pop)"""
        fingerprint = {
            # Frequency distribution (bass-heavy, dark)
            'bass_pct': 35.0,           # High bass
            'mid_pct': 30.0,
            'air_pct': 8.0,             # Low air
            'presence_pct': 10.0,       # Low presence
            'spectral_centroid': 2000.0,  # Low centroid

            # Dynamics (compressed)
            'crest_db': 9.5,            # Low crest = compressed
            'dynamic_range_variation': 0.2,
            'loudness_variation_std': 1.0,

            # Energy (quiet)
            'lufs': -25.0,              # Quiet

            # Stereo
            'stereo_width': 0.6,
            'phase_correlation': 0.95,
        }

        mapper = ProcessingSpaceMapper()
        coords = mapper.map_fingerprint_to_space(fingerprint)

        # Expect: Low spectral balance (dark), low dynamics (compressed), low energy (quiet)
        assert coords.spectral_balance < 0.4, f"Expected dark (< 0.4), got {coords.spectral_balance:.2f}"
        assert coords.dynamic_range < 0.3, f"Expected compressed (< 0.3), got {coords.dynamic_range:.2f}"
        assert coords.energy_level < 0.4, f"Expected quiet (< 0.4), got {coords.energy_level:.2f}"

    def test_bright_dynamic_loud_track(self):
        """Test mapping for bright, dynamic, loud track (typical live recording)"""
        fingerprint = {
            # Frequency distribution (bright, treble-heavy)
            'bass_pct': 20.0,           # Low bass
            'mid_pct': 35.0,
            'air_pct': 15.0,            # High air
            'presence_pct': 18.0,       # High presence
            'spectral_centroid': 5000.0,  # High centroid

            # Dynamics (very dynamic)
            'crest_db': 17.0,           # High crest = dynamic
            'dynamic_range_variation': 0.8,
            'loudness_variation_std': 4.0,

            # Energy (loud)
            'lufs': -12.0,              # Loud

            # Stereo
            'stereo_width': 0.8,
            'phase_correlation': 0.85,
        }

        mapper = ProcessingSpaceMapper()
        coords = mapper.map_fingerprint_to_space(fingerprint)

        # Expect: High spectral balance (bright), high dynamics, high energy (loud)
        assert coords.spectral_balance > 0.6, f"Expected bright (> 0.6), got {coords.spectral_balance:.2f}"
        assert coords.dynamic_range > 0.7, f"Expected dynamic (> 0.7), got {coords.dynamic_range:.2f}"
        assert coords.energy_level > 0.8, f"Expected loud (> 0.8), got {coords.energy_level:.2f}"

    def test_balanced_track(self):
        """Test mapping for balanced track (well-mastered reference)"""
        fingerprint = {
            # Frequency distribution (balanced)
            'bass_pct': 28.0,
            'mid_pct': 35.0,
            'air_pct': 12.0,
            'presence_pct': 15.0,
            'spectral_centroid': 3500.0,

            # Dynamics (moderate)
            'crest_db': 13.0,
            'dynamic_range_variation': 0.5,
            'loudness_variation_std': 2.5,

            # Energy (moderate)
            'lufs': -14.0,

            # Stereo
            'stereo_width': 0.7,
            'phase_correlation': 0.9,
        }

        mapper = ProcessingSpaceMapper()
        coords = mapper.map_fingerprint_to_space(fingerprint)

        # Expect: Moderate values across all dimensions
        assert 0.4 < coords.spectral_balance < 0.6, f"Expected balanced spectral (0.4-0.6), got {coords.spectral_balance:.2f}"
        assert 0.4 < coords.dynamic_range < 0.6, f"Expected moderate dynamics (0.4-0.6), got {coords.dynamic_range:.2f}"
        assert 0.6 < coords.energy_level <= 0.8, f"Expected moderate energy (0.6-0.8), got {coords.energy_level:.2f}"


class TestContinuousParameterGenerator:
    """Test parameter generation from coordinates"""

    def test_quiet_dynamic_track_parameters(self):
        """Test parameters for quiet, dynamic track (should be raised and preserved)"""
        coords = ProcessingCoordinates(
            spectral_balance=0.5,   # Balanced
            dynamic_range=0.8,      # Very dynamic
            energy_level=0.2,       # Very quiet
            fingerprint={
                'bass_pct': 28.0, 'mid_pct': 35.0, 'air_pct': 12.0,
                'presence_pct': 15.0, 'crest_db': 16.0, 'lufs': -25.0,
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

        # Should not expand (already dynamic)
        assert params.expansion_params['amount'] == 0.0, f"Expected no expansion, got {params.expansion_params['amount']:.2f}"

    def test_loud_compressed_track_parameters(self):
        """Test parameters for loud, compressed track (should be expanded)"""
        coords = ProcessingCoordinates(
            spectral_balance=0.5,   # Balanced
            dynamic_range=0.2,      # Very compressed
            energy_level=0.9,       # Very loud
            fingerprint={
                'bass_pct': 28.0, 'mid_pct': 35.0, 'air_pct': 12.0,
                'presence_pct': 15.0, 'crest_db': 9.0, 'lufs': -10.0,
                'stereo_width': 0.7
            }
        )

        generator = ContinuousParameterGenerator()
        params = generator.generate_parameters(coords)

        # Should preserve loudness (already loud)
        assert -12.0 <= params.target_lufs <= -9.0, f"Expected preserved loudness (-12 to -9), got {params.target_lufs:.1f}"

        # Should have less headroom (compressed material)
        assert params.peak_target_db >= -0.5, f"Expected less headroom (> -0.5), got {params.peak_target_db:.2f}"

        # Should not compress (already compressed)
        assert params.compression_params['amount'] == 0.0, f"Expected no compression, got {params.compression_params['amount']:.2f}"

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
                'bass_pct': 15.0,       # Low bass (deficit: 15% from ideal 30%)
                'mid_pct': 35.0,
                'air_pct': 18.0,        # High air (excess)
                'presence_pct': 20.0,
                'crest_db': 12.0,
                'lufs': -14.0,
                'stereo_width': 0.7
            }
        )

        generator = ContinuousParameterGenerator()
        params = generator.generate_parameters(coords)

        # Should boost bass significantly
        assert params.eq_curve['low_shelf_gain'] > 1.0, f"Expected bass boost (> 1.0), got {params.eq_curve['low_shelf_gain']:.2f}"

        # Should not boost air (already high)
        assert params.eq_curve['high_shelf_gain'] < 1.0, f"Expected minimal air boost (< 1.0), got {params.eq_curve['high_shelf_gain']:.2f}"

        # Should have high EQ blend (unbalanced material)
        assert params.eq_blend >= 0.65, f"Expected high EQ blend (>= 0.65), got {params.eq_blend:.2f}"


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
                'bass_pct': 28.0, 'mid_pct': 35.0, 'air_pct': 12.0,
                'presence_pct': 15.0, 'crest_db': 12.0, 'lufs': -16.0,
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
            'bass_pct': 22.0,           # Low bass (needs boost)
            'mid_pct': 38.0,
            'air_pct': 10.0,            # Low air
            'presence_pct': 12.0,
            'spectral_centroid': 3200.0,
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

        # Should expand stereo (narrow)
        assert params.stereo_width_target > 0.65, \
            f"Expected stereo expansion (> 0.65), got {params.stereo_width_target:.2f}"

        # Should preserve dynamics (already good)
        assert params.compression_params['amount'] <= 0.5, \
            f"Expected light compression (<= 0.5), got {params.compression_params['amount']:.2f}"

        # Should raise loudness moderately
        assert -15.0 <= params.target_lufs <= -12.0, \
            f"Expected moderate loudness raise (-15 to -12), got {params.target_lufs:.1f}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
