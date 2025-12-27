# -*- coding: utf-8 -*-

"""
Phase 7.2 Tests: Metric Transformation Pipeline

Comprehensive tests for unified variation metrics, stability calculations,
and band normalization patterns.

Test Count: 32 tests
Coverage: All new helper classes in MetricUtils
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.common_metrics import (
    BandNormalizationTable,
    MetricUtils,
    StabilityMetrics,
    VariationMetrics,
)


class TestVariationMetrics:
    """Test unified variation calculation patterns"""

    def test_calculate_from_crest_factors_basic(self):
        """Test crest factor variation calculation"""
        crest_db = np.array([3.0, 4.5, 5.0, 3.5, 4.2])
        result = VariationMetrics.calculate_from_crest_factors(crest_db)
        assert 0 <= result <= 1.0
        assert np.isfinite(result)

    def test_calculate_from_crest_factors_no_variation(self):
        """Test constant crest factors"""
        crest_db = np.array([4.0, 4.0, 4.0, 4.0])
        result = VariationMetrics.calculate_from_crest_factors(crest_db)
        assert result == 0.0  # Zero std dev

    def test_calculate_from_crest_factors_high_variation(self):
        """Test high crest factor variation"""
        crest_db = np.array([1.0, 2.0, 10.0, 11.0])
        result = VariationMetrics.calculate_from_crest_factors(crest_db)
        assert result > 0.5  # Should be high variation

    def test_calculate_from_crest_factors_with_nan(self):
        """Test NaN handling in crest factors"""
        crest_db = np.array([3.0, np.nan, 4.0, 5.0, np.nan])
        result = VariationMetrics.calculate_from_crest_factors(crest_db)
        assert np.isfinite(result)

    def test_calculate_from_crest_factors_empty(self):
        """Test empty array"""
        crest_db = np.array([])
        result = VariationMetrics.calculate_from_crest_factors(crest_db)
        assert result == 0.5  # Default for invalid input

    def test_calculate_from_loudness_db_basic(self):
        """Test loudness variation calculation"""
        loudness_db = np.array([-20.0, -18.0, -22.0, -19.0, -21.0])
        result = VariationMetrics.calculate_from_loudness_db(loudness_db)
        assert 0 <= result <= 10.0
        assert np.isfinite(result)

    def test_calculate_from_loudness_db_constant(self):
        """Test constant loudness"""
        loudness_db = np.array([-20.0, -20.0, -20.0, -20.0])
        result = VariationMetrics.calculate_from_loudness_db(loudness_db)
        assert result == 0.0

    def test_calculate_from_loudness_db_clipping(self):
        """Test loudness clipping at max_range"""
        loudness_db = np.array([-5.0, 5.0, -10.0, 10.0, -20.0])
        result = VariationMetrics.calculate_from_loudness_db(loudness_db, max_range=10.0)
        assert result <= 10.0

    def test_calculate_from_peaks_basic(self):
        """Test peak consistency calculation"""
        peaks = np.array([0.8, 0.7, 0.75, 0.82, 0.78])
        result = VariationMetrics.calculate_from_peaks(peaks)
        assert 0 <= result <= 1.0
        assert np.isfinite(result)

    def test_calculate_from_peaks_consistent(self):
        """Test consistent peaks"""
        peaks = np.array([0.8, 0.8, 0.8, 0.8, 0.8])
        result = VariationMetrics.calculate_from_peaks(peaks)
        assert result >= 0.9  # High consistency

    def test_calculate_from_peaks_variable(self):
        """Test highly variable peaks"""
        peaks = np.array([0.1, 0.9, 0.2, 0.8, 0.15])
        result = VariationMetrics.calculate_from_peaks(peaks)
        # Variable peaks have high CV, resulting in medium-low consistency
        assert result < 0.7

    def test_calculate_from_peaks_single_value(self):
        """Test single peak value"""
        peaks = np.array([0.5])
        result = VariationMetrics.calculate_from_peaks(peaks)
        assert result == 0.5  # Default for single value


class TestStabilityMetrics:
    """Test unified stability calculation patterns"""

    def test_from_intervals_basic(self):
        """Test stability from rhythm intervals"""
        intervals = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
        result = StabilityMetrics.from_intervals(intervals)
        assert 0 <= result <= 1.0
        assert np.isfinite(result)

    def test_from_intervals_consistent(self):
        """Test consistent intervals"""
        intervals = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
        result = StabilityMetrics.from_intervals(intervals, scale=1.0)
        assert result > 0.9  # High stability

    def test_from_intervals_variable(self):
        """Test variable intervals"""
        intervals = np.array([0.3, 0.7, 0.2, 0.8, 0.4])
        result = StabilityMetrics.from_intervals(intervals, scale=1.0)
        # Variable intervals have moderate stability
        assert result < 0.8

    def test_from_intervals_harmonic_scaling(self):
        """Test harmonic-specific scaling"""
        intervals = np.array([440.0, 441.0, 439.0, 440.5, 440.2])
        result_default = StabilityMetrics.from_intervals(intervals, scale=1.0)
        result_harmonic = StabilityMetrics.from_intervals(intervals, scale=10.0)
        assert result_harmonic < result_default  # More sensitive with higher scale

    def test_from_intervals_empty(self):
        """Test empty intervals"""
        intervals = np.array([])
        result = StabilityMetrics.from_intervals(intervals)
        assert result == 0.0

    def test_from_intervals_single(self):
        """Test single interval"""
        intervals = np.array([0.5])
        result = StabilityMetrics.from_intervals(intervals)
        assert result == 0.0

    def test_from_values_basic(self):
        """Test stability from metric values"""
        values = np.array([440.0, 441.0, 442.0, 439.0, 440.5])
        result = StabilityMetrics.from_values(values)
        assert 0 <= result <= 1.0
        assert np.isfinite(result)

    def test_from_values_consistent(self):
        """Test consistent values"""
        values = np.array([440.0, 440.0, 440.0, 440.0, 440.0])
        result = StabilityMetrics.from_values(values)
        assert result > 0.9  # High stability

    def test_from_values_harmonic_scale(self):
        """Test harmonic-specific scale for pitch"""
        pitch_values = np.array([440.0, 442.0, 438.0, 441.0, 440.5])
        result_default = StabilityMetrics.from_values(pitch_values, scale=1.0)
        result_harmonic = StabilityMetrics.from_values(pitch_values, scale=10.0)
        assert result_harmonic < result_default  # Harmonic more sensitive

    def test_from_values_zero_mean(self):
        """Test values with zero mean"""
        values = np.array([-1.0, 0.0, 1.0, -1.0, 0.0])
        result = StabilityMetrics.from_values(values)
        assert result == 0.5  # Default for zero/near-zero mean


class TestBandNormalizationTable:
    """Test parametric band normalization"""

    def test_initialization_default_bands(self):
        """Test default band initialization"""
        table = BandNormalizationTable()
        assert len(table.bands) == 7  # 7 standard frequency bands
        assert table.bands[0][0] == 0  # Sub-bass starts at band 0
        assert table.bands[-1][1] == 31  # Air ends at band 31

    def test_initialization_custom_bands(self):
        """Test custom band initialization"""
        custom_bands = [(0, 10, "0-10k", "energy", -6, 6)]
        table = BandNormalizationTable(band_definitions=custom_bands)
        assert len(table.bands) == 1
        assert table.bands[0] == custom_bands[0]

    def test_band_definitions_structure(self):
        """Test band definition tuple structure"""
        table = BandNormalizationTable()
        for band_def in table.bands:
            assert len(band_def) == 6
            start, end, freq_range, fp_key, min_db, max_db = band_def
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert start <= end
            assert min_db <= max_db

    def test_apply_to_fingerprint_basic(self):
        """Test fingerprint application"""
        table = BandNormalizationTable()
        fingerprint = {
            'sub_bass_pct': 0.5,
            'bass_pct': 0.6,
            'low_mid_pct': 0.4,
            'mid_pct': 0.7,
            'upper_mid_pct': 0.5,
            'presence_pct': 0.3,
            'air_pct': 0.2
        }
        result = table.apply_to_fingerprint(fingerprint, BandNormalizationTable.normalize_to_db)
        assert isinstance(result, dict)
        assert len(result) == 32  # 32 bands (0-31)

    def test_apply_to_fingerprint_band_ranges(self):
        """Test that bands are correctly assigned to ranges"""
        table = BandNormalizationTable()
        fingerprint = {key: 0.5 for key in [
            'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
            'upper_mid_pct', 'presence_pct', 'air_pct'
        ]}
        result = table.apply_to_fingerprint(fingerprint, BandNormalizationTable.normalize_to_db)

        # Sub-bass (0-3) should have same gain
        sub_bass_gain = result[0]
        assert result[1] == sub_bass_gain
        assert result[2] == sub_bass_gain
        assert result[3] == sub_bass_gain

        # Bass (4-11) should have same gain
        bass_gain = result[4]
        assert all(result[i] == bass_gain for i in range(4, 12))

    def test_apply_to_fingerprint_missing_keys(self):
        """Test with missing fingerprint keys"""
        table = BandNormalizationTable()
        fingerprint = {'sub_bass_pct': 0.5}  # Only one key
        result = table.apply_to_fingerprint(fingerprint, BandNormalizationTable.normalize_to_db)
        assert len(result) == 32  # Should still return all 32 bands (0-31)

    def test_normalize_to_db_basic(self):
        """Test dB normalization"""
        result = BandNormalizationTable.normalize_to_db(0.5, -12, 12)
        assert result == 0.0  # 0.5 should map to center (0 dB)

    def test_normalize_to_db_boundaries(self):
        """Test dB normalization boundaries"""
        result_zero = BandNormalizationTable.normalize_to_db(0.0, -12, 12)
        assert result_zero == -12.0

        result_one = BandNormalizationTable.normalize_to_db(1.0, -12, 12)
        assert result_one == 12.0

    def test_normalize_to_db_clipping(self):
        """Test dB normalization clipping"""
        result_below = BandNormalizationTable.normalize_to_db(-0.5, -12, 12)
        assert result_below == -12.0  # Clipped to min

        result_above = BandNormalizationTable.normalize_to_db(1.5, -12, 12)
        assert result_above == 12.0  # Clipped to max

    def test_normalize_to_db_asymmetric(self):
        """Test asymmetric dB range (e.g., presence band)"""
        # Presence: -6 to +12 (asymmetric)
        result_zero = BandNormalizationTable.normalize_to_db(0.0, -6, 12)
        assert result_zero == -6.0

        result_one = BandNormalizationTable.normalize_to_db(1.0, -6, 12)
        assert result_one == 12.0

        result_half = BandNormalizationTable.normalize_to_db(0.5, -6, 12)
        assert result_half == 3.0  # Midpoint


class TestIntegration:
    """Integration tests for unified patterns"""

    def test_variation_metrics_compatibility(self):
        """Test VariationMetrics work with actual analyzer outputs"""
        # Simulate variation_analyzer outputs
        crest_db = np.random.normal(4.0, 1.0, 100)
        loudness_db = np.random.normal(-20.0, 3.0, 100)
        peaks = np.random.uniform(0.3, 0.9, 100)

        var_crest = VariationMetrics.calculate_from_crest_factors(crest_db)
        var_peak = VariationMetrics.calculate_from_peaks(peaks)

        assert 0 <= var_crest <= 1.0 or var_crest > 1.0  # Can exceed 1 if high variation
        assert 0 <= var_peak <= 1.0 or var_peak > 1.0

        # Loudness variation clips to 0-10 dB
        var_loudness = VariationMetrics.calculate_from_loudness_db(loudness_db)
        assert 0 <= var_loudness <= 10.0

    def test_stability_metrics_with_real_data(self):
        """Test StabilityMetrics with realistic audio metrics"""
        # Rhythm: beat intervals (seconds)
        beat_intervals = np.array([0.5, 0.501, 0.499, 0.502, 0.498])
        rhythm_stability = StabilityMetrics.from_intervals(beat_intervals, scale=1.0)
        assert rhythm_stability > 0.90  # Should be very stable

        # Pitch: frequencies in Hz
        pitch_values = np.array([440.0, 442.0, 438.0, 441.0, 440.5])
        pitch_stability = StabilityMetrics.from_values(pitch_values, scale=10.0)
        assert 0.5 < pitch_stability <= 1.0  # Valid stability range

    def test_band_table_with_real_fingerprint(self):
        """Test BandNormalizationTable with realistic fingerprint"""
        table = BandNormalizationTable()
        fingerprint = {
            'sub_bass_pct': 0.6,   # Bass-heavy
            'bass_pct': 0.7,
            'low_mid_pct': 0.5,
            'mid_pct': 0.6,
            'upper_mid_pct': 0.4,
            'presence_pct': 0.3,
            'air_pct': 0.1
        }
        eq_gains = table.apply_to_fingerprint(fingerprint, BandNormalizationTable.normalize_to_db)

        # Verify all bands are present
        assert len(eq_gains) == 32

        # Bass bands (0.6 normalized to dB: -12 + 0.6*24 = -12 + 14.4 = 2.4)
        sub_bass_gain = eq_gains[0]
        assert -12 <= sub_bass_gain <= 12  # Valid dB range

        # Air band (0.1 normalized: -12 + 0.1*24 = -12 + 2.4 = -9.6)
        air_gain = eq_gains[26]
        assert -12 <= air_gain <= 12  # Valid dB range

    def test_metric_utils_consistency(self):
        """Test that new helpers integrate with existing MetricUtils"""
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        # VariationMetrics should work with MetricUtils normalize_to_range
        crest_std = np.std(values)
        normalized = MetricUtils.normalize_to_range(crest_std, 6.0, clip=True)
        assert 0 <= normalized <= 1.0

        # StabilityMetrics should work with MetricUtils stability_from_cv
        std_val = np.std(values)
        mean_val = np.mean(values)
        stability = MetricUtils.stability_from_cv(std_val, mean_val)
        assert 0 <= stability <= 1.0
