# -*- coding: utf-8 -*-

"""
Tests for Phase 2.5.1 EQ Gain Saturation Optimization

Tests the non-linear saturation applied to EQ gains to prevent extreme values
from synthetic or edge-case fingerprints.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.parameter_mapper import (
    EQParameterMapper,
    ParameterMapper,
)


class TestEQGainSaturation:
    """Tests for EQ gain saturation (Phase 2.5.1)"""

    def test_saturation_initialization(self):
        """Test that EQ mapper initializes with saturation capability"""
        mapper = EQParameterMapper()
        assert hasattr(mapper, '_apply_gain_saturation')
        assert callable(mapper._apply_gain_saturation)

    def test_saturation_preserves_linear_region(self):
        """Test that gains within nominal range are unchanged"""
        mapper = EQParameterMapper()
        gains = {0: 5.0, 1: -8.0, 2: 0.0, 3: 12.0, 4: -12.0}

        saturated = mapper._apply_gain_saturation(gains, nominal_max=12.0, hard_max=18.0)

        # All gains within ±12dB should be unchanged
        assert saturated[0] == 5.0
        assert saturated[1] == -8.0
        assert saturated[2] == 0.0
        assert saturated[3] == 12.0
        assert saturated[4] == -12.0

    def test_saturation_compresses_extreme_positive(self):
        """Test that extreme positive gains are compressed"""
        mapper = EQParameterMapper()
        gains = {0: 25.0}  # Way beyond ±12dB

        saturated = mapper._apply_gain_saturation(gains, nominal_max=12.0, hard_max=18.0)

        # Gain should be compressed but not hard-clipped
        assert 12.0 < saturated[0] <= 18.0

    def test_saturation_compresses_extreme_negative(self):
        """Test that extreme negative gains are compressed"""
        mapper = EQParameterMapper()
        gains = {0: -25.0}  # Way beyond ±12dB

        saturated = mapper._apply_gain_saturation(gains, nominal_max=12.0, hard_max=18.0)

        # Gain should be compressed but not hard-clipped
        assert -18.0 <= saturated[0] < -12.0

    def test_saturation_hard_clips_beyond_max(self):
        """Test that gains above hard_max are clipped"""
        mapper = EQParameterMapper()
        gains = {0: 30.0, 1: -30.0}

        saturated = mapper._apply_gain_saturation(gains, nominal_max=12.0, hard_max=18.0)

        # Should be hard-clipped to ±18dB
        assert saturated[0] == 18.0
        assert saturated[1] == -18.0

    def test_saturation_smooth_knee(self):
        """Test that saturation curve has smooth knee (non-linear)"""
        mapper = EQParameterMapper()

        # Create gains progressively exceeding nominal range
        gains = {
            0: 12.0,   # At boundary
            1: 14.0,   # Slightly over
            2: 16.0,   # More over
            3: 18.0,   # At hard max
            4: 20.0,   # Beyond hard max
            5: 30.0,   # Far beyond
        }

        saturated = mapper._apply_gain_saturation(gains, nominal_max=12.0, hard_max=18.0)

        # Verify monotonic increase (saturation curve is monotonic)
        values = [saturated[i] for i in range(6)]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1], "Saturation curve should be monotonic"

        # Verify behavior in saturation region
        # Band 0 at nominal boundary: unchanged
        assert saturated[0] == 12.0
        # Bands 1-3 in saturation region: compressed but below hard_max
        assert 12.0 < saturated[1] < 18.0, "Band in saturation should be compressed"
        assert 13.0 < saturated[2] < 18.0
        assert 15.0 < saturated[3] < 18.0
        # Bands 4-5 at/beyond hard_max: clipped to hard_max
        assert saturated[4] == 18.0, "Gain beyond hard_max should be hard-clipped"
        assert saturated[5] == 18.0, "Gain far beyond should be hard-clipped"

    def test_saturation_symmetry(self):
        """Test that saturation is symmetric for positive and negative gains"""
        mapper = EQParameterMapper()

        gains = {0: 25.0, 1: -25.0}
        saturated = mapper._apply_gain_saturation(gains, nominal_max=12.0, hard_max=18.0)

        # Positive and negative should have same magnitude
        assert abs(saturated[0]) == abs(saturated[1])
        assert saturated[0] > 0
        assert saturated[1] < 0

    def test_saturation_preserves_zero(self):
        """Test that zero gain is preserved"""
        mapper = EQParameterMapper()
        gains = {0: 0.0}

        saturated = mapper._apply_gain_saturation(gains)
        assert saturated[0] == 0.0

    def test_integration_with_parameter_mapper(self):
        """Test saturation integration in full parameter generation"""
        # Create extreme bass-heavy fingerprint
        extreme_fp = {
            'sub_bass_pct': 0.9,
            'bass_pct': 0.8,
            'low_mid_pct': 0.3,
            'mid_pct': 0.1,
            'upper_mid_pct': 0.05,
            'presence_pct': 0.02,
            'air_pct': 0.01,
            'lufs': -10.0,
            'crest_db': 14.0,
            'bass_mid_ratio': 3.0,
            'harmonic_ratio': 0.9,
            'pitch_stability': 0.95,
            'chroma_energy': 0.9,
            'spectral_centroid': 100.0,
            'spectral_rolloff': 3000.0,
            'spectral_flatness': 0.2,
            'loudness_variation_std': 0.5,
            'dynamic_range_variation': 5.0,
            'peak_consistency': 0.95,
            'tempo_bpm': 60.0,
            'rhythm_stability': 0.9,
            'transient_density': 1.0,
            'silence_ratio': 0.5,
            'stereo_width': 0.0,
            'phase_correlation': 1.0,
        }

        mapper = ParameterMapper()
        params = mapper.generate_mastering_parameters(extreme_fp, target_lufs=-16.0)

        # Verify all gains respect hard limit
        for band_idx, gain in params['eq']['gains'].items():
            assert -18.0 <= gain <= 18.0, \
                f"Band {band_idx} gain {gain:.1f}dB exceeds hard limit ±18dB"

        # Count how many are within nominal range
        nominal_count = sum(
            1 for gain in params['eq']['gains'].values()
            if -12.0 <= gain <= 12.0
        )

        # Most should be in nominal range
        assert nominal_count >= 20, \
            f"Expected at least 20 bands in nominal range, got {nominal_count}"

    def test_saturation_with_bright_content(self):
        """Test saturation doesn't break bright content"""
        bright_fp = {
            'sub_bass_pct': 0.01,
            'bass_pct': 0.05,
            'low_mid_pct': 0.1,
            'mid_pct': 0.15,
            'upper_mid_pct': 0.25,
            'presence_pct': 0.25,
            'air_pct': 0.2,
            'lufs': -16.0,
            'crest_db': 10.0,
            'bass_mid_ratio': 0.3,
            'harmonic_ratio': 0.5,
            'pitch_stability': 0.7,
            'chroma_energy': 0.4,
            'spectral_centroid': 5000.0,
            'spectral_rolloff': 16000.0,
            'spectral_flatness': 0.6,
            'loudness_variation_std': 1.5,
            'dynamic_range_variation': 2.0,
            'peak_consistency': 0.8,
            'tempo_bpm': 140.0,
            'rhythm_stability': 0.8,
            'transient_density': 4.0,
            'silence_ratio': 0.1,
            'stereo_width': 0.8,
            'phase_correlation': 0.8,
        }

        mapper = ParameterMapper()
        params = mapper.generate_mastering_parameters(bright_fp)

        # All gains should still be valid
        for band_idx, gain in params['eq']['gains'].items():
            assert isinstance(gain, (int, float))
            assert -18.0 <= gain <= 18.0


class TestSaturationCurveProperties:
    """Tests for mathematical properties of saturation curve"""

    def test_saturation_curve_is_bounded(self):
        """Test that saturation curve never exceeds hard_max"""
        mapper = EQParameterMapper()

        # Test wide range of input values
        test_gains = {i: float(i - 25) for i in range(51)}  # -25 to 25 dB

        saturated = mapper._apply_gain_saturation(test_gains, nominal_max=12.0, hard_max=18.0)

        for gain in saturated.values():
            assert -18.0 <= gain <= 18.0, f"Gain {gain:.1f}dB exceeded bounds"

    def test_saturation_curve_preserves_ordering(self):
        """Test that saturation preserves relative gain ordering"""
        mapper = EQParameterMapper()

        # Create strictly increasing gains
        gains = {i: float(i - 15) for i in range(31)}  # -15 to 15 dB

        saturated = mapper._apply_gain_saturation(gains)

        # Verify monotonic increase is preserved
        prev_gain = saturated[0]
        for i in range(1, 31):
            assert saturated[i] >= prev_gain, \
                f"Saturation broke ordering at band {i}"
            prev_gain = saturated[i]

    def test_saturation_behavior_with_different_limits(self):
        """Test saturation with different nominal and hard limits"""
        mapper = EQParameterMapper()
        gains = {0: 20.0}

        # Tight limits
        tight = mapper._apply_gain_saturation(gains, nominal_max=8.0, hard_max=12.0)
        assert tight[0] == 12.0  # Beyond hard_max, so hard-clipped

        # Loose limits - gain is still in saturation region (15 < 20 < 25)
        loose = mapper._apply_gain_saturation(gains, nominal_max=15.0, hard_max=25.0)
        assert 15.0 < loose[0] < 25.0  # In saturation region, compressed but not clipped
        # Saturation curve compresses the excess, result will be between nominal and hard_max
        assert loose[0] > 18.5  # Compressed but mostly preserved


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
