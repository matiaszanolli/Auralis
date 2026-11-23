# -*- coding: utf-8 -*-

"""
Tests for Continuous Processing Space
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests coordinate mapping (parameters come from mastering_targets, #6356).
"""

import pytest

from auralis.core.processing.continuous_space import ProcessingSpaceMapper


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



if __name__ == '__main__':
    pytest.main([__file__, '-v'])


class TestNoPreferenceMachinery:
    """The PreferenceVector bias layer is gone (#6123): it only ever saw the neutral vector."""

    def test_the_preference_vector_type_no_longer_exists(self):
        import auralis.core.processing.continuous_space as space
        import auralis.core.processing.continuous_space_types as types

        assert not hasattr(space, "PreferenceVector") and not hasattr(types, "PreferenceVector")
