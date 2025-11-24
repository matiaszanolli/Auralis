# -*- coding: utf-8 -*-

"""
Tests for Parameter Mapper

Tests the conversion of 25D fingerprints to mastering parameters (EQ, dynamics, levels).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import numpy as np
from auralis.analysis.fingerprint.parameter_mapper import (
    ParameterMapper,
    EQParameterMapper,
    DynamicsParameterMapper,
    LevelParameterMapper,
    HarmonicParameterMapper,
)


@pytest.fixture
def sample_fingerprint():
    """Sample 25D fingerprint for testing"""
    return {
        # Frequency Distribution (7D)
        'sub_bass_pct': 0.15,
        'bass_pct': 0.25,
        'low_mid_pct': 0.18,
        'mid_pct': 0.22,
        'upper_mid_pct': 0.12,
        'presence_pct': 0.05,
        'air_pct': 0.03,
        # Dynamics (3D)
        'lufs': -12.5,
        'crest_db': 8.3,
        'bass_mid_ratio': 1.1,
        # Temporal (4D)
        'tempo_bpm': 120.0,
        'rhythm_stability': 0.92,
        'transient_density': 3.5,
        'silence_ratio': 0.02,
        # Spectral (3D)
        'spectral_centroid': 2800.0,
        'spectral_rolloff': 8000.0,
        'spectral_flatness': 0.45,
        # Harmonic (3D)
        'harmonic_ratio': 0.78,
        'pitch_stability': 0.85,
        'chroma_energy': 0.65,
        # Variation (3D)
        'dynamic_range_variation': 2.1,
        'loudness_variation_std': 1.3,
        'peak_consistency': 0.88,
        # Stereo (2D)
        'stereo_width': 0.7,
        'phase_correlation': 0.92,
    }


class TestEQParameterMapper:
    """Tests for EQ parameter mapping"""

    def test_eq_mapper_initialization(self):
        """Test EQ mapper initializes with correct frequency bands"""
        mapper = EQParameterMapper()
        assert len(mapper.eq_bands) == 31
        assert mapper.eq_bands[0] == 20
        assert mapper.eq_bands[-1] == 20000

    def test_frequency_to_eq_mapping(self, sample_fingerprint):
        """Test mapping frequency distribution to EQ gains"""
        mapper = EQParameterMapper()
        eq_gains = mapper.map_frequency_to_eq(sample_fingerprint)

        # Should have gains for all bands
        assert len(eq_gains) == 31

        # Gains should be in dB range
        for band, gain in eq_gains.items():
            assert isinstance(gain, float)
            assert -12 <= gain <= 12  # Typical EQ range

        # Bass-heavy should have positive bass gains
        bass_gains = [eq_gains[i] for i in range(4, 12)]
        assert np.mean(bass_gains) > 0  # Bass emphasized

    def test_spectral_to_eq_mapping(self, sample_fingerprint):
        """Test spectral dimension EQ adjustments"""
        mapper = EQParameterMapper()
        spectral_gains = mapper.map_spectral_to_eq(sample_fingerprint)

        # Should return adjustments (may be empty for neutral spectral content)
        assert isinstance(spectral_gains, dict)

        # All gains should be within reasonable range
        for gain in spectral_gains.values():
            assert -4 <= gain <= 4

    def test_eq_with_bright_content(self):
        """Test EQ mapping for bright content (high spectral centroid)"""
        bright_fp = {
            'spectral_centroid': 4500.0,  # Bright
            'spectral_rolloff': 15000.0,
            'spectral_flatness': 0.3,
            # Minimal required fields
            'sub_bass_pct': 0.1, 'bass_pct': 0.15, 'low_mid_pct': 0.15,
            'mid_pct': 0.2, 'upper_mid_pct': 0.15, 'presence_pct': 0.15, 'air_pct': 0.15,
        }

        mapper = EQParameterMapper()
        spectral_gains = mapper.map_spectral_to_eq(bright_fp)

        # Bright content should reduce upper mids
        assert any(g < 0 for g in spectral_gains.values())

    def test_eq_with_dull_content(self):
        """Test EQ mapping for dull content (low spectral centroid)"""
        dull_fp = {
            'spectral_centroid': 1200.0,  # Dull
            'spectral_rolloff': 4000.0,
            'spectral_flatness': 0.3,
            # Minimal required fields
            'sub_bass_pct': 0.2, 'bass_pct': 0.3, 'low_mid_pct': 0.2,
            'mid_pct': 0.15, 'upper_mid_pct': 0.08, 'presence_pct': 0.04, 'air_pct': 0.01,
        }

        mapper = EQParameterMapper()
        spectral_gains = mapper.map_spectral_to_eq(dull_fp)

        # Dull content should boost presence
        assert any(g > 0 for g in spectral_gains.values())


class TestDynamicsParameterMapper:
    """Tests for dynamics parameter mapping"""

    def test_compressor_mapping(self, sample_fingerprint):
        """Test dynamics to compressor conversion"""
        mapper = DynamicsParameterMapper()
        comp_params = mapper.map_to_compressor(sample_fingerprint)

        # Check all required fields
        assert 'threshold' in comp_params
        assert 'ratio' in comp_params
        assert 'attack_ms' in comp_params
        assert 'release_ms' in comp_params
        assert 'makeup_gain' in comp_params

        # Validate ranges
        assert -40 <= comp_params['threshold'] <= 0  # dB
        assert 1.0 <= comp_params['ratio'] <= 8.0  # Compression ratio
        assert 5.0 <= comp_params['attack_ms'] <= 50.0  # ms
        assert 50.0 <= comp_params['release_ms'] <= 500.0  # ms

    def test_low_crest_compression(self):
        """Test smooth content gets gentle compression"""
        low_crest_fp = {
            'lufs': -16.0,
            'crest_db': 4.0,  # Low crest = smooth
            'bass_mid_ratio': 1.0,
        }

        mapper = DynamicsParameterMapper()
        comp_params = mapper.map_to_compressor(low_crest_fp)

        # Smooth content should have gentle compression
        assert comp_params['ratio'] < 3.0

    def test_high_crest_compression(self):
        """Test dynamic content gets aggressive compression"""
        high_crest_fp = {
            'lufs': -16.0,
            'crest_db': 12.0,  # High crest = dynamic
            'bass_mid_ratio': 1.0,
        }

        mapper = DynamicsParameterMapper()
        comp_params = mapper.map_to_compressor(high_crest_fp)

        # Dynamic content should have more aggressive compression
        assert comp_params['ratio'] > 3.0
        assert comp_params['attack_ms'] < 20.0  # Fast attack

    def test_multiband_mapping(self, sample_fingerprint):
        """Test multiband compression setup"""
        mapper = DynamicsParameterMapper()
        multiband = mapper.map_to_multiband(sample_fingerprint)

        # Should have 3 bands
        assert 'low' in multiband
        assert 'mid' in multiband
        assert 'high' in multiband

        # Each band should have compressor settings
        for band_name, band_settings in multiband.items():
            assert 'threshold' in band_settings
            assert 'ratio' in band_settings
            assert 'attack_ms' in band_settings
            assert 'release_ms' in band_settings

    def test_bass_heavy_content_multiband(self):
        """Test bass-heavy content gets more low-band compression"""
        bass_heavy_fp = {
            'bass_pct': 0.40,  # Very bass-heavy
            'mid_pct': 0.20,
            'dynamic_range_variation': 3.0,
        }

        mapper = DynamicsParameterMapper()
        multiband = mapper.map_to_multiband(bass_heavy_fp)

        # Low band should have higher ratio for bass-heavy content
        assert multiband['low']['ratio'] > multiband['mid']['ratio']


class TestLevelParameterMapper:
    """Tests for level matching parameter mapping"""

    def test_level_matching_calculation(self, sample_fingerprint):
        """Test LUFS to level matching conversion"""
        mapper = LevelParameterMapper()
        level_params = mapper.map_to_level_matching(sample_fingerprint, target_lufs=-16.0)

        # Check required fields
        assert 'target_lufs' in level_params
        assert 'gain' in level_params
        assert 'headroom' in level_params
        assert 'safety_margin' in level_params

        # Gain should bring level to target
        assert level_params['target_lufs'] == -16.0

    def test_level_gain_calculation(self):
        """Test gain calculation for different LUFS values"""
        loud_fp = {'lufs': -10.0, 'loudness_variation_std': 1.0, 'crest_db': 8.0}
        quiet_fp = {'lufs': -20.0, 'loudness_variation_std': 1.0, 'crest_db': 8.0}

        mapper = LevelParameterMapper()
        target = -16.0

        loud_params = mapper.map_to_level_matching(loud_fp, target_lufs=target)
        quiet_params = mapper.map_to_level_matching(quiet_fp, target_lufs=target)

        # Loud content should need negative gain
        assert loud_params['gain'] < 0

        # Quiet content should need positive gain
        assert quiet_params['gain'] > 0

    def test_headroom_calculation(self):
        """Test headroom based on peaks and variation"""
        dynamic_fp = {'lufs': -16.0, 'loudness_variation_std': 3.0, 'crest_db': 12.0}
        smooth_fp = {'lufs': -16.0, 'loudness_variation_std': 0.5, 'crest_db': 4.0}

        mapper = LevelParameterMapper()
        dynamic_params = mapper.map_to_level_matching(dynamic_fp)
        smooth_params = mapper.map_to_level_matching(smooth_fp)

        # Dynamic content needs more headroom
        assert dynamic_params['headroom'] > smooth_params['headroom']


class TestHarmonicParameterMapper:
    """Tests for harmonic enhancement mapping"""

    def test_harmonic_enhancement(self, sample_fingerprint):
        """Test harmonic dimension mapping"""
        mapper = HarmonicParameterMapper()
        harmonic_params = mapper.map_to_harmonic_enhancement(sample_fingerprint)

        # Check required fields
        assert 'saturation' in harmonic_params
        assert 'exciter' in harmonic_params
        assert 'pitch_stability_score' in harmonic_params
        assert 'harmonic_enhancement_enabled' in harmonic_params

        # Values should be in sensible ranges
        assert 0.0 <= harmonic_params['saturation'] <= 1.0
        assert 0.0 <= harmonic_params['exciter'] <= 1.0

    def test_harmonic_rich_content(self):
        """Test harmonic-rich content gets saturation"""
        harmonic_fp = {
            'harmonic_ratio': 0.85,  # Very harmonic
            'pitch_stability': 0.95,  # Very stable
            'chroma_energy': 0.8,  # Strong harmonic energy
        }

        mapper = HarmonicParameterMapper()
        params = mapper.map_to_harmonic_enhancement(harmonic_fp)

        # Should enable harmonic enhancement and apply saturation
        assert params['harmonic_enhancement_enabled'] is True
        assert params['saturation'] > 0.1

    def test_percussive_content(self):
        """Test percussive content gets exciter"""
        percussive_fp = {
            'harmonic_ratio': 0.35,  # More percussive
            'pitch_stability': 0.6,  # Less stable
            'chroma_energy': 0.3,  # Weak harmonic energy
        }

        mapper = HarmonicParameterMapper()
        params = mapper.map_to_harmonic_enhancement(percussive_fp)

        # Should enable exciter for weak harmonics
        assert params['exciter'] > 0.1


class TestParameterMapper:
    """Integration tests for complete parameter mapper"""

    def test_mapper_initialization(self):
        """Test parameter mapper initializes with all sub-mappers"""
        mapper = ParameterMapper()

        assert hasattr(mapper, 'eq_mapper')
        assert hasattr(mapper, 'dynamics_mapper')
        assert hasattr(mapper, 'level_mapper')
        assert hasattr(mapper, 'harmonic_mapper')

    def test_complete_parameter_generation(self, sample_fingerprint):
        """Test complete mastering parameter generation"""
        mapper = ParameterMapper()
        params = mapper.generate_mastering_parameters(
            fingerprint=sample_fingerprint,
            target_lufs=-16.0,
            enable_multiband=False
        )

        # Check all required sections
        assert 'eq' in params
        assert 'dynamics' in params
        assert 'level' in params
        assert 'harmonic' in params
        assert 'metadata' in params

        # EQ section
        assert params['eq']['enabled'] is True
        assert 'gains' in params['eq']
        assert len(params['eq']['gains']) == 31

        # Dynamics section
        assert params['dynamics']['enabled'] is True
        assert 'standard' in params['dynamics']
        assert 'threshold' in params['dynamics']['standard']

        # Level section
        assert params['level']['target_lufs'] == -16.0

    def test_multiband_parameter_generation(self, sample_fingerprint):
        """Test parameter generation with multiband enabled"""
        mapper = ParameterMapper()
        params = mapper.generate_mastering_parameters(
            fingerprint=sample_fingerprint,
            target_lufs=-16.0,
            enable_multiband=True
        )

        # Multiband should be present when enabled
        assert 'multiband' in params['dynamics']
        assert 'low' in params['dynamics']['multiband']
        assert 'mid' in params['dynamics']['multiband']
        assert 'high' in params['dynamics']['multiband']

    def test_parameter_consistency(self, sample_fingerprint):
        """Test that parameters are consistent and don't have invalid values"""
        mapper = ParameterMapper()
        params = mapper.generate_mastering_parameters(sample_fingerprint)

        # All EQ gains should be numeric
        for band, gain in params['eq']['gains'].items():
            assert isinstance(gain, (int, float))
            assert -20 <= gain <= 20  # Reasonable EQ range

        # Compressor params should be valid
        comp = params['dynamics']['standard']
        assert -40 <= comp['threshold'] <= 0
        assert 1.0 <= comp['ratio'] <= 8.0
        assert comp['attack_ms'] > 0
        assert comp['release_ms'] > 0

    @pytest.mark.boundary
    def test_extreme_fingerprints(self):
        """Test parameter mapper with extreme fingerprint values"""
        # Very bass-heavy
        bass_fp = {
            'sub_bass_pct': 0.8, 'bass_pct': 0.7, 'low_mid_pct': 0.3,
            'mid_pct': 0.1, 'upper_mid_pct': 0.05, 'presence_pct': 0.02, 'air_pct': 0.01,
            'lufs': -10.0, 'crest_db': 14.0, 'bass_mid_ratio': 3.0,
            'harmonic_ratio': 0.9, 'pitch_stability': 0.95, 'chroma_energy': 0.9,
            'spectral_centroid': 100.0, 'spectral_rolloff': 3000.0, 'spectral_flatness': 0.2,
            'loudness_variation_std': 0.5, 'dynamic_range_variation': 5.0, 'peak_consistency': 0.95,
            'tempo_bpm': 60.0, 'rhythm_stability': 0.9, 'transient_density': 1.0, 'silence_ratio': 0.5,
            'stereo_width': 0.0, 'phase_correlation': 1.0,
        }

        mapper = ParameterMapper()
        params = mapper.generate_mastering_parameters(bass_fp)

        # Should not crash and produce valid output
        assert 'eq' in params
        assert 'dynamics' in params

        # Very bright and dynamic
        bright_fp = {
            'sub_bass_pct': 0.01, 'bass_pct': 0.05, 'low_mid_pct': 0.1,
            'mid_pct': 0.15, 'upper_mid_pct': 0.25, 'presence_pct': 0.25, 'air_pct': 0.2,
            'lufs': -20.0, 'crest_db': 16.0, 'bass_mid_ratio': 0.2,
            'harmonic_ratio': 0.3, 'pitch_stability': 0.5, 'chroma_energy': 0.2,
            'spectral_centroid': 8000.0, 'spectral_rolloff': 18000.0, 'spectral_flatness': 0.8,
            'loudness_variation_std': 4.0, 'dynamic_range_variation': 8.0, 'peak_consistency': 0.6,
            'tempo_bpm': 180.0, 'rhythm_stability': 0.7, 'transient_density': 8.0, 'silence_ratio': 0.1,
            'stereo_width': 1.0, 'phase_correlation': 0.5,
        }

        params = mapper.generate_mastering_parameters(bright_fp)
        assert 'eq' in params
        assert 'dynamics' in params


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
