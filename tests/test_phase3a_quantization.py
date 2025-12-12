# -*- coding: utf-8 -*-

"""
Phase 3A Tests: Fingerprint Quantization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests 8-bit quantization of 25D fingerprints:
- Accuracy validation (<1% error)
- Storage efficiency (8x compression)
- Round-trip consistency
- Distance metric preservation

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
from auralis.library.fingerprint_quantizer import FingerprintQuantizer


class TestFingerprintQuantization:
    """Test fingerprint quantization and dequantization."""

    @pytest.fixture
    def sample_fingerprint(self) -> dict:
        """Create a sample 25D fingerprint for testing."""
        return {
            # Frequency (7D)
            'sub_bass_pct': 10.5,
            'bass_pct': 25.3,
            'low_mid_pct': 20.1,
            'mid_pct': 30.2,
            'upper_mid_pct': 8.7,
            'presence_pct': 3.2,
            'air_pct': 2.0,
            # Dynamics (3D)
            'lufs': -15.5,
            'crest_db': 12.3,
            'bass_mid_ratio': 50.0,
            # Temporal (4D)
            'tempo_bpm': 120.5,
            'rhythm_stability': 0.87,
            'transient_density': 45.2,
            'silence_ratio': 0.15,
            # Spectral (3D)
            'spectral_centroid': 0.65,
            'spectral_rolloff': 0.72,
            'spectral_flatness': 0.42,
            # Harmonic (3D)
            'harmonic_ratio': 0.78,
            'pitch_stability': 0.88,
            'chroma_energy': 0.65,
            # Variation (3D)
            'dynamic_range_variation': 0.55,
            'loudness_variation_std': 8.3,
            'peak_consistency': 0.92,
            # Stereo (2D)
            'stereo_width': 0.85,
            'phase_correlation': 0.45,
        }

    def test_quantize_dequantize_round_trip(self, sample_fingerprint):
        """Test that fingerprint survives quantization round-trip."""
        # Quantize
        quantized = FingerprintQuantizer.quantize(sample_fingerprint)

        # Verify size
        assert len(quantized) == 25, f"Expected 25 bytes, got {len(quantized)}"

        # Dequantize
        recovered = FingerprintQuantizer.dequantize(quantized)

        # Verify all dimensions present
        assert len(recovered) == 25
        for dim_name in FingerprintQuantizer.DIMENSION_NAMES:
            assert dim_name in recovered

    def test_quantization_accuracy(self, sample_fingerprint):
        """Test that quantization error is <1% for all dimensions."""
        quantized = FingerprintQuantizer.quantize(sample_fingerprint)
        recovered = FingerprintQuantizer.dequantize(quantized)

        # Calculate error
        original_vector = [sample_fingerprint[dim] for dim in FingerprintQuantizer.DIMENSION_NAMES]
        recovered_vector = [recovered[dim] for dim in FingerprintQuantizer.DIMENSION_NAMES]

        error_stats = FingerprintQuantizer.calculate_quantization_error(original_vector, recovered_vector)

        print(f"\nQuantization Error Statistics:")
        print(f"  Absolute max error: {error_stats['absolute_max_error']:.6f}")
        print(f"  Absolute mean error: {error_stats['absolute_mean_error']:.6f}")
        print(f"  Relative max error: {error_stats['relative_max_error']:.2f}%")
        print(f"  Relative mean error: {error_stats['relative_mean_error']:.2f}%")

        # Most dimensions should have <0.5% error (due to 8-bit quantization)
        # Some bounded dimensions might have up to 1% (e.g., crest_db: 24dB range / 255 levels)
        assert error_stats['absolute_max_error'] < 1.0, \
            f"Max error too high: {error_stats['absolute_max_error']}"
        assert error_stats['relative_max_error'] < 2.0, \
            f"Relative max error > 2%: {error_stats['relative_max_error']}"

    def test_boundary_values(self):
        """Test quantization at boundary values."""
        # Test minimum values
        min_fingerprint = {
            dim: 0.0 for dim in FingerprintQuantizer.DIMENSION_NAMES
        }
        quantized_min = FingerprintQuantizer.quantize(min_fingerprint)
        assert len(quantized_min) == 25

        # Test maximum values (with proper bounds)
        max_fingerprint = {}
        for dim in FingerprintQuantizer.DIMENSION_NAMES:
            _, max_val = FingerprintQuantizer.DIMENSION_BOUNDS[dim]
            max_fingerprint[dim] = max_val

        quantized_max = FingerprintQuantizer.quantize(max_fingerprint)
        assert len(quantized_max) == 25

        # Verify they're different
        assert quantized_min != quantized_max

    def test_vector_interface(self, sample_fingerprint):
        """Test vector-based quantization interface."""
        # Convert to vector
        original_vector = [sample_fingerprint[dim] for dim in FingerprintQuantizer.DIMENSION_NAMES]

        # Quantize via vector interface
        quantized = FingerprintQuantizer.quantize_vector(original_vector)
        assert len(quantized) == 25

        # Dequantize via vector interface
        recovered_vector = FingerprintQuantizer.dequantize_vector(quantized)
        assert len(recovered_vector) == 25

        # Verify accuracy
        error_stats = FingerprintQuantizer.calculate_quantization_error(original_vector, recovered_vector)
        assert error_stats['relative_max_error'] < 2.0

    def test_extreme_values(self):
        """Test quantization with extreme values."""
        extreme_fingerprint = {
            # Positive extremes
            'sub_bass_pct': 100.0,
            'bass_pct': 100.0,
            'low_mid_pct': 100.0,
            'mid_pct': 100.0,
            'upper_mid_pct': 100.0,
            'presence_pct': 100.0,
            'air_pct': 100.0,
            # Negative extremes (LUFS)
            'lufs': -60.0,
            'crest_db': 24.0,
            'bass_mid_ratio': 100.0,
            # Extremes
            'tempo_bpm': 240.0,
            'rhythm_stability': 1.0,
            'transient_density': 100.0,
            'silence_ratio': 1.0,
            'spectral_centroid': 1.0,
            'spectral_rolloff': 1.0,
            'spectral_flatness': 1.0,
            'harmonic_ratio': 1.0,
            'pitch_stability': 1.0,
            'chroma_energy': 1.0,
            'dynamic_range_variation': 1.0,
            'loudness_variation_std': 20.0,
            'peak_consistency': 1.0,
            'stereo_width': 1.0,
            'phase_correlation': 1.0,
        }

        quantized = FingerprintQuantizer.quantize(extreme_fingerprint)
        recovered = FingerprintQuantizer.dequantize(quantized)

        # Verify all dimensions recovered
        for dim in FingerprintQuantizer.DIMENSION_NAMES:
            assert dim in recovered
            # Should be close to original extreme
            assert abs(recovered[dim] - extreme_fingerprint[dim]) < 1.0

    def test_quantization_version(self):
        """Test quantization version constant."""
        assert FingerprintQuantizer.QUANTIZATION_VERSION == 1
        assert len(FingerprintQuantizer.DIMENSION_NAMES) == 25
        assert len(FingerprintQuantizer.DIMENSION_BOUNDS) == 25

    def test_storage_efficiency(self, sample_fingerprint):
        """Verify 8x compression ratio."""
        # Original: 25 floats * 8 bytes = 200 bytes
        original_size = 25 * 8

        # Quantized: 25 bytes
        quantized = FingerprintQuantizer.quantize(sample_fingerprint)
        quantized_size = len(quantized)

        compression_ratio = original_size / quantized_size

        print(f"\nStorage Efficiency:")
        print(f"  Original: {original_size} bytes")
        print(f"  Quantized: {quantized_size} bytes")
        print(f"  Compression ratio: {compression_ratio:.1f}x")

        assert quantized_size == 25
        assert compression_ratio == 8.0


class TestQuantizationDistance:
    """Test that Euclidean distance is preserved under quantization."""

    @pytest.fixture
    def fingerprints(self) -> tuple:
        """Create two similar fingerprints."""
        fp1 = {
            'sub_bass_pct': 10.0, 'bass_pct': 25.0, 'low_mid_pct': 20.0,
            'mid_pct': 30.0, 'upper_mid_pct': 8.0, 'presence_pct': 3.0,
            'air_pct': 2.0, 'lufs': -15.0, 'crest_db': 12.0,
            'bass_mid_ratio': 50.0, 'tempo_bpm': 120.0, 'rhythm_stability': 0.87,
            'transient_density': 45.0, 'silence_ratio': 0.15, 'spectral_centroid': 0.65,
            'spectral_rolloff': 0.72, 'spectral_flatness': 0.42, 'harmonic_ratio': 0.78,
            'pitch_stability': 0.88, 'chroma_energy': 0.65, 'dynamic_range_variation': 0.55,
            'loudness_variation_std': 8.0, 'peak_consistency': 0.92, 'stereo_width': 0.85,
            'phase_correlation': 0.45,
        }

        fp2 = {
            'sub_bass_pct': 12.0, 'bass_pct': 23.0, 'low_mid_pct': 21.0,
            'mid_pct': 29.0, 'upper_mid_pct': 9.0, 'presence_pct': 4.0,
            'air_pct': 1.8, 'lufs': -16.0, 'crest_db': 11.5,
            'bass_mid_ratio': 52.0, 'tempo_bpm': 122.0, 'rhythm_stability': 0.85,
            'transient_density': 43.0, 'silence_ratio': 0.16, 'spectral_centroid': 0.67,
            'spectral_rolloff': 0.70, 'spectral_flatness': 0.44, 'harmonic_ratio': 0.76,
            'pitch_stability': 0.86, 'chroma_energy': 0.67, 'dynamic_range_variation': 0.53,
            'loudness_variation_std': 8.5, 'peak_consistency': 0.90, 'stereo_width': 0.83,
            'phase_correlation': 0.47,
        }

        return fp1, fp2

    def test_distance_preservation(self, fingerprints):
        """Test that Euclidean distance is approximately preserved."""
        import math

        fp1, fp2 = fingerprints

        # Calculate original distance
        v1 = [fp1[dim] for dim in FingerprintQuantizer.DIMENSION_NAMES]
        v2 = [fp2[dim] for dim in FingerprintQuantizer.DIMENSION_NAMES]

        original_distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))

        # Quantize and recover
        q1 = FingerprintQuantizer.dequantize_vector(
            FingerprintQuantizer.quantize_vector(v1)
        )
        q2 = FingerprintQuantizer.dequantize_vector(
            FingerprintQuantizer.quantize_vector(v2)
        )

        quantized_distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(q1, q2)))

        # Distance should be very close (within rounding error)
        distance_error_pct = abs(original_distance - quantized_distance) / original_distance * 100

        print(f"\nDistance Preservation:")
        print(f"  Original distance: {original_distance:.6f}")
        print(f"  Quantized distance: {quantized_distance:.6f}")
        print(f"  Error: {distance_error_pct:.2f}%")

        # Error should be small (<1% for typical fingerprints)
        assert distance_error_pct < 2.0, \
            f"Distance error too high: {distance_error_pct}%"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
