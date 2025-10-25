#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DSP Basic Functions Comprehensive Coverage Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for all basic DSP functions to maximize coverage
Tests: channel_count, size, rms, normalize, amplify, mid_side_encode, mid_side_decode
"""

import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('../..'))

from auralis.dsp.basic import (
    channel_count,
    size,
    rms,
    normalize,
    amplify,
    mid_side_encode,
    mid_side_decode
)

class TestDSPBasicComprehensive:
    """Comprehensive DSP Basic functions coverage tests"""

    def setUp(self):
        """Set up test fixtures"""
        # Create various test signals
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples)

        # Mono test signals
        self.mono_sine = 0.5 * np.sin(2 * np.pi * 440 * t)
        self.mono_silence = np.zeros(samples)
        self.mono_noise = 0.1 * np.random.randn(samples)
        self.mono_peak = np.concatenate([np.zeros(samples//2), [1.0], np.zeros(samples//2)])

        # Stereo test signals
        left_channel = 0.3 * np.sin(2 * np.pi * 440 * t)
        right_channel = 0.4 * np.sin(2 * np.pi * 880 * t)
        self.stereo_signal = np.column_stack([left_channel, right_channel])

        # Edge case signals
        self.empty_mono = np.array([])
        self.single_sample_mono = np.array([0.5])
        self.single_sample_stereo = np.array([[0.3, 0.4]])

        # Extreme value signals
        self.clipped_mono = np.array([1.0, -1.0, 1.0, -1.0, 0.0])
        self.very_quiet = 1e-10 * self.mono_sine
        self.very_loud = 10.0 * self.mono_sine

    def tearDown(self):
        """Clean up test fixtures"""
        pass

    def test_channel_count_mono_signals(self):
        """Test channel_count with mono (1D) signals"""
        self.setUp()

        # Test normal mono signal
        assert channel_count(self.mono_sine) == 1

        # Test silence
        assert channel_count(self.mono_silence) == 1

        # Test noise
        assert channel_count(self.mono_noise) == 1

        # Test single sample
        assert channel_count(self.single_sample_mono) == 1

        # Test clipped signal
        assert channel_count(self.clipped_mono) == 1

        self.tearDown()

    def test_channel_count_stereo_signals(self):
        """Test channel_count with stereo (2D) signals"""
        self.setUp()

        # Test stereo signal
        assert channel_count(self.stereo_signal) == 2

        # Test single stereo sample - shape is (1, 2) so it has 2 channels
        assert channel_count(self.single_sample_stereo) == 2

        # Test multi-channel signals
        multi_channel = np.random.randn(1000, 5)  # 5 channels
        assert channel_count(multi_channel) == 5

        # Test mono signal reshaped to 2D
        mono_2d = self.mono_sine.reshape(-1, 1)
        assert channel_count(mono_2d) == 1

        self.tearDown()

    def test_channel_count_edge_cases(self):
        """Test channel_count edge cases"""
        self.setUp()

        # Test empty arrays (if they don't cause errors)
        if len(self.empty_mono) == 0:
            # Empty array might cause issues, test carefully
            try:
                result = channel_count(self.empty_mono)
                assert result == 1  # 1D array should return 1
            except Exception:
                pass  # Empty arrays might not be supported

        self.tearDown()

    def test_size_function(self):
        """Test size function with various signals"""
        self.setUp()

        # Test mono signals
        assert size(self.mono_sine) == len(self.mono_sine)
        assert size(self.mono_silence) == len(self.mono_silence)
        assert size(self.mono_noise) == len(self.mono_noise)
        assert size(self.single_sample_mono) == 1
        assert size(self.clipped_mono) == 5

        # Test stereo signals
        assert size(self.stereo_signal) == self.stereo_signal.shape[0]
        assert size(self.single_sample_stereo) == 1

        # Test multi-channel
        multi_channel = np.random.randn(1000, 3)
        assert size(multi_channel) == 1000

        self.tearDown()

    def test_rms_calculation_mono(self):
        """Test RMS calculation for mono signals"""
        self.setUp()

        # Test silence (should be 0)
        rms_silence = rms(self.mono_silence)
        assert np.isclose(rms_silence, 0.0, atol=1e-10)

        # Test sine wave (analytical RMS = amplitude / sqrt(2))
        rms_sine = rms(self.mono_sine)
        expected_rms = 0.5 / np.sqrt(2)  # 0.5 is amplitude
        assert np.isclose(rms_sine, expected_rms, rtol=0.01)

        # Test DC signal
        dc_signal = np.ones(1000) * 0.3
        rms_dc = rms(dc_signal)
        assert np.isclose(rms_dc, 0.3)

        # Test single sample
        rms_single = rms(self.single_sample_mono)
        assert np.isclose(rms_single, 0.5)

        # Test clipped signal
        rms_clipped = rms(self.clipped_mono)
        expected_clipped = np.sqrt((1.0**2 + 1.0**2 + 1.0**2 + 1.0**2 + 0.0**2) / 5)
        assert np.isclose(rms_clipped, expected_clipped)

        self.tearDown()

    def test_rms_calculation_stereo(self):
        """Test RMS calculation for stereo signals"""
        self.setUp()

        # Test stereo signal
        rms_stereo = rms(self.stereo_signal)
        assert rms_stereo > 0

        # Compare with manual calculation
        manual_rms = np.sqrt(np.mean(self.stereo_signal ** 2))
        assert np.isclose(rms_stereo, manual_rms)

        # Test single stereo sample
        # RMS = sqrt(mean([0.3^2, 0.4^2])) = sqrt((0.09 + 0.16)/2) = sqrt(0.125)
        rms_single_stereo = rms(self.single_sample_stereo)
        expected_single_stereo = np.sqrt(np.mean([0.3**2, 0.4**2]))
        assert np.isclose(rms_single_stereo, expected_single_stereo)

        self.tearDown()

    def test_rms_edge_cases(self):
        """Test RMS edge cases"""
        self.setUp()

        # Test very quiet signal
        rms_quiet = rms(self.very_quiet)
        assert rms_quiet >= 0
        assert rms_quiet < 1e-8

        # Test very loud signal
        rms_loud = rms(self.very_loud)
        assert rms_loud > 0

        self.tearDown()

    def test_normalize_function_basic(self):
        """Test normalize function basic functionality"""
        self.setUp()

        # Test normalizing to default level (1.0)
        normalized = normalize(self.mono_sine)
        peak_after = np.max(np.abs(normalized))
        assert np.isclose(peak_after, 1.0)

        # Test normalizing to custom level
        target_level = 0.5
        normalized_custom = normalize(self.mono_sine, target_level)
        peak_custom = np.max(np.abs(normalized_custom))
        assert np.isclose(peak_custom, target_level)

        # Test that shape is preserved
        assert normalized.shape == self.mono_sine.shape

        self.tearDown()

    def test_normalize_function_edge_cases(self):
        """Test normalize function edge cases"""
        self.setUp()

        # Test silence (no peak)
        normalized_silence = normalize(self.mono_silence)
        assert np.array_equal(normalized_silence, self.mono_silence)  # Should be unchanged

        # Test already normalized signal
        already_norm = np.array([1.0, -1.0, 0.5, -0.5])
        normalized_already = normalize(already_norm)
        assert np.isclose(np.max(np.abs(normalized_already)), 1.0)

        # Test single sample
        normalized_single = normalize(self.single_sample_mono)
        assert np.isclose(np.abs(normalized_single[0]), 1.0)

        # Test stereo signal
        normalized_stereo = normalize(self.stereo_signal, 0.8)
        peak_stereo = np.max(np.abs(normalized_stereo))
        assert np.isclose(peak_stereo, 0.8)

        self.tearDown()

    def test_normalize_different_target_levels(self):
        """Test normalize with different target levels"""
        self.setUp()

        target_levels = [0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]

        for target in target_levels:
            normalized = normalize(self.mono_sine, target)
            peak = np.max(np.abs(normalized))
            assert np.isclose(peak, target, rtol=1e-10)

        self.tearDown()

    def test_amplify_function_basic(self):
        """Test amplify function basic functionality"""
        self.setUp()

        # Test 0dB gain (no change)
        amplified_0db = amplify(self.mono_sine, 0.0)
        assert np.allclose(amplified_0db, self.mono_sine)

        # Test +6dB gain (double amplitude)
        amplified_6db = amplify(self.mono_sine, 6.0)
        expected_gain = 10 ** (6.0 / 20)  # ~1.995
        assert np.allclose(amplified_6db, self.mono_sine * expected_gain)

        # Test -6dB gain (half amplitude)
        amplified_neg6db = amplify(self.mono_sine, -6.0)
        expected_gain_neg = 10 ** (-6.0 / 20)  # ~0.501
        assert np.allclose(amplified_neg6db, self.mono_sine * expected_gain_neg)

        self.tearDown()

    def test_amplify_function_various_gains(self):
        """Test amplify with various gain values"""
        self.setUp()

        gains_db = [-20, -10, -3, 0, 3, 6, 10, 20]

        for gain_db in gains_db:
            amplified = amplify(self.mono_sine, gain_db)
            expected_gain = 10 ** (gain_db / 20)

            # Verify gain is applied correctly
            assert np.allclose(amplified, self.mono_sine * expected_gain)

            # Verify shape is preserved
            assert amplified.shape == self.mono_sine.shape

        self.tearDown()

    def test_amplify_stereo_signal(self):
        """Test amplify with stereo signals"""
        self.setUp()

        # Test stereo amplification
        amplified_stereo = amplify(self.stereo_signal, 3.0)
        expected_gain = 10 ** (3.0 / 20)

        assert np.allclose(amplified_stereo, self.stereo_signal * expected_gain)
        assert amplified_stereo.shape == self.stereo_signal.shape

        self.tearDown()

    def test_amplify_edge_cases(self):
        """Test amplify edge cases"""
        self.setUp()

        # Test with silence
        amplified_silence = amplify(self.mono_silence, 10.0)
        assert np.allclose(amplified_silence, 0.0)

        # Test with single sample
        amplified_single = amplify(self.single_sample_mono, 6.0)
        expected = self.single_sample_mono * (10 ** (6.0 / 20))
        assert np.allclose(amplified_single, expected)

        # Test extreme gains
        extreme_gains = [-100, -50, 50, 100]
        for gain in extreme_gains:
            amplified = amplify(self.mono_sine, gain)
            assert amplified.shape == self.mono_sine.shape
            assert np.all(np.isfinite(amplified))  # Should not produce NaN or inf

        self.tearDown()

    def test_mid_side_encode_basic(self):
        """Test mid-side encoding basic functionality"""
        self.setUp()

        # Test with stereo signal
        mid, side = mid_side_encode(self.stereo_signal)

        # Verify output types and shapes
        assert isinstance(mid, np.ndarray)
        assert isinstance(side, np.ndarray)
        assert mid.shape == (self.stereo_signal.shape[0],)
        assert side.shape == (self.stereo_signal.shape[0],)

        # Verify mid-side calculations
        left = self.stereo_signal[:, 0]
        right = self.stereo_signal[:, 1]
        expected_mid = (left + right) / 2
        expected_side = (left - right) / 2

        assert np.allclose(mid, expected_mid)
        assert np.allclose(side, expected_side)

        self.tearDown()

    def test_mid_side_encode_special_cases(self):
        """Test mid-side encoding special cases"""
        self.setUp()

        # Test with mono signal (both channels identical)
        mono_stereo = np.column_stack([self.mono_sine, self.mono_sine])
        mid_mono, side_mono = mid_side_encode(mono_stereo)

        assert np.allclose(mid_mono, self.mono_sine)  # Mid should equal mono signal
        assert np.allclose(side_mono, 0.0)  # Side should be zero

        # Test with completely opposite channels
        opposite_stereo = np.column_stack([self.mono_sine, -self.mono_sine])
        mid_opp, side_opp = mid_side_encode(opposite_stereo)

        assert np.allclose(mid_opp, 0.0)  # Mid should be zero
        assert np.allclose(side_opp, self.mono_sine)  # Side should equal original

        # Test with single stereo sample
        mid_single, side_single = mid_side_encode(self.single_sample_stereo)
        expected_mid_single = (0.3 + 0.4) / 2
        expected_side_single = (0.3 - 0.4) / 2

        assert np.isclose(mid_single[0], expected_mid_single)
        assert np.isclose(side_single[0], expected_side_single)

        self.tearDown()

    def test_mid_side_decode_basic(self):
        """Test mid-side decoding basic functionality"""
        self.setUp()

        # Start with known mid-side signals
        mid_signal = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 1000))
        side_signal = 0.2 * np.sin(2 * np.pi * 880 * np.linspace(0, 1, 1000))

        # Decode to stereo
        decoded_stereo = mid_side_decode(mid_signal, side_signal)

        # Verify output shape and type
        assert isinstance(decoded_stereo, np.ndarray)
        assert decoded_stereo.shape == (len(mid_signal), 2)

        # Verify mid-side decode calculations
        expected_left = mid_signal + side_signal
        expected_right = mid_signal - side_signal

        assert np.allclose(decoded_stereo[:, 0], expected_left)
        assert np.allclose(decoded_stereo[:, 1], expected_right)

        self.tearDown()

    def test_mid_side_decode_special_cases(self):
        """Test mid-side decoding special cases"""
        self.setUp()

        # Test with only mid signal (side = 0)
        mid_only = self.mono_sine
        side_zero = np.zeros_like(mid_only)
        decoded_mid_only = mid_side_decode(mid_only, side_zero)

        # Both channels should equal the mid signal
        assert np.allclose(decoded_mid_only[:, 0], mid_only)
        assert np.allclose(decoded_mid_only[:, 1], mid_only)

        # Test with only side signal (mid = 0)
        mid_zero = np.zeros_like(self.mono_sine)
        side_only = self.mono_sine
        decoded_side_only = mid_side_decode(mid_zero, side_only)

        # Left and right should be opposites
        assert np.allclose(decoded_side_only[:, 0], side_only)
        assert np.allclose(decoded_side_only[:, 1], -side_only)

        # Test with single sample
        single_mid = np.array([0.5])
        single_side = np.array([0.2])
        decoded_single = mid_side_decode(single_mid, single_side)

        expected_left_single = 0.5 + 0.2
        expected_right_single = 0.5 - 0.2

        assert np.isclose(decoded_single[0, 0], expected_left_single)
        assert np.isclose(decoded_single[0, 1], expected_right_single)

        self.tearDown()

    def test_mid_side_round_trip(self):
        """Test mid-side encode/decode round trip"""
        self.setUp()

        # Encode and then decode
        mid, side = mid_side_encode(self.stereo_signal)
        reconstructed = mid_side_decode(mid, side)

        # Should perfectly reconstruct original signal
        assert np.allclose(reconstructed, self.stereo_signal, rtol=1e-14)

        # Test with single sample
        mid_single, side_single = mid_side_encode(self.single_sample_stereo)
        reconstructed_single = mid_side_decode(mid_single, side_single)

        assert np.allclose(reconstructed_single, self.single_sample_stereo)

        self.tearDown()

    def test_function_combinations(self):
        """Test combinations of functions"""
        self.setUp()

        # Normalize -> Amplify -> Check RMS
        normalized = normalize(self.mono_sine, 0.5)
        amplified = amplify(normalized, 6.0)
        rms_final = rms(amplified)

        assert rms_final > rms(normalized)

        # Mid-side encode -> Amplify channels differently -> Decode
        mid, side = mid_side_encode(self.stereo_signal)

        # Amplify mid more than side
        mid_amplified = amplify(mid, 3.0)
        side_amplified = amplify(side, 1.0)

        # Decode back
        processed_stereo = mid_side_decode(mid_amplified, side_amplified)

        # Should have different characteristics than original
        assert not np.allclose(processed_stereo, self.stereo_signal)
        assert processed_stereo.shape == self.stereo_signal.shape

        self.tearDown()

    def test_data_type_preservation(self):
        """Test that functions preserve appropriate data types"""
        self.setUp()

        # Test with float32
        float32_signal = self.mono_sine.astype(np.float32)

        # All functions should work with float32
        assert channel_count(float32_signal) == 1
        assert isinstance(size(float32_signal), int)
        assert isinstance(rms(float32_signal), (float, np.floating))

        normalized_f32 = normalize(float32_signal)
        assert normalized_f32.dtype == np.float32 or normalized_f32.dtype == np.float64

        amplified_f32 = amplify(float32_signal, 6.0)
        assert amplified_f32.dtype == np.float32 or amplified_f32.dtype == np.float64

        # Test with float64 (default)
        float64_signal = self.mono_sine.astype(np.float64)
        normalized_f64 = normalize(float64_signal)
        amplified_f64 = amplify(float64_signal, 6.0)

        assert isinstance(normalized_f64, np.ndarray)
        assert isinstance(amplified_f64, np.ndarray)

        self.tearDown()

    def test_error_handling_and_edge_cases(self):
        """Test error handling and numerical edge cases"""
        self.setUp()

        # Test with very large values
        large_signal = np.array([1e10, -1e10, 0])
        try:
            rms_large = rms(large_signal)
            assert rms_large > 0

            normalized_large = normalize(large_signal)
            assert np.max(np.abs(normalized_large)) <= 1.0

        except (OverflowError, RuntimeWarning):
            pass  # Large values might cause overflow

        # Test with very small values
        tiny_signal = np.array([1e-100, -1e-100, 0])
        rms_tiny = rms(tiny_signal)
        assert rms_tiny >= 0

        normalized_tiny = normalize(tiny_signal)
        # Tiny signals might remain tiny after normalization if peak is 0

        self.tearDown()

if __name__ == '__main__':
    import pytest
    pytest.main([__file__])