"""
Test compression and expansion functions preserve input arrays.

This test suite verifies that compression and expansion functions
adhere to the critical invariant: "Never modify input arrays in-place."

Related to issue #2150.
"""

import numpy as np
import pytest

from auralis.core.processing.base.compression_expansion import (
    CompressionStrategies,
    ExpansionStrategies,
)


class TestCompressionInvariant:
    """Test that compression functions don't modify input arrays."""

    def test_soft_knee_compression_preserves_input(self):
        """Verify apply_soft_knee_compression() doesn't modify input array."""
        # Create test audio with some peaks
        original = np.random.randn(48000).astype(np.float32)
        original *= 0.5  # Scale to reasonable level

        # Create a copy to compare against
        original_copy = original.copy()

        # Apply compression
        result = CompressionStrategies.apply_soft_knee_compression(
            original, compression_amount=0.85
        )

        # Verify input array was NOT modified
        np.testing.assert_array_equal(
            original,
            original_copy,
            err_msg="apply_soft_knee_compression() modified input array in-place"
        )

        # Verify result is different from input (compression happened)
        assert not np.array_equal(result, original), (
            "Compression should modify the audio"
        )

    def test_soft_knee_compression_with_high_peaks(self):
        """Test compression with audio that has high peaks above threshold."""
        # Create audio with deliberate high peaks
        original = np.zeros(48000, dtype=np.float32)
        original[1000] = 0.8
        original[2000] = -0.9
        original[3000] = 0.95

        original_copy = original.copy()

        # Apply compression that should trigger threshold processing
        result = CompressionStrategies.apply_soft_knee_compression(
            original, compression_amount=0.9
        )

        # Verify input unchanged
        np.testing.assert_array_equal(
            original,
            original_copy,
            err_msg="Compression modified input when processing peaks"
        )

    def test_clip_blend_compression_preserves_input(self):
        """Verify apply_clip_blend_compression() doesn't modify input array."""
        original = np.random.randn(48000).astype(np.float32)
        original *= 0.5
        original_copy = original.copy()

        comp_params = {'ratio': 2.0, 'amount': 0.7}
        result = CompressionStrategies.apply_clip_blend_compression(
            original, comp_params
        )

        # Verify input array was NOT modified
        np.testing.assert_array_equal(
            original,
            original_copy,
            err_msg="apply_clip_blend_compression() modified input array"
        )


class TestExpansionInvariant:
    """Test that expansion functions don't modify input arrays."""

    def test_peak_enhancement_expansion_preserves_input(self):
        """Verify apply_peak_enhancement_expansion() doesn't modify input array."""
        # Create test audio with some peaks
        original = np.random.randn(48000).astype(np.float32)
        original *= 0.3  # Lower level for expansion

        original_copy = original.copy()

        # Apply expansion
        result = ExpansionStrategies.apply_peak_enhancement_expansion(
            original, expansion_amount=0.7
        )

        # Verify input array was NOT modified
        np.testing.assert_array_equal(
            original,
            original_copy,
            err_msg="apply_peak_enhancement_expansion() modified input array in-place"
        )

        # Verify result is different from input (expansion happened)
        assert not np.array_equal(result, original), (
            "Expansion should modify the audio"
        )

    def test_peak_enhancement_expansion_with_high_peaks(self):
        """Test expansion with audio that has peaks above expansion threshold."""
        # Create audio with deliberate peaks that should trigger expansion
        original = np.zeros(48000, dtype=np.float32)
        original[1000] = 0.5
        original[2000] = -0.6
        original[3000] = 0.7
        # Add some RMS level
        original += np.random.randn(48000).astype(np.float32) * 0.05

        original_copy = original.copy()

        # Apply expansion that should trigger above-threshold processing
        result = ExpansionStrategies.apply_peak_enhancement_expansion(
            original, expansion_amount=0.8
        )

        # Verify input unchanged
        np.testing.assert_array_equal(
            original,
            original_copy,
            err_msg="Expansion modified input when processing peaks"
        )

    def test_rms_reduction_expansion_preserves_input(self):
        """Verify apply_rms_reduction_expansion() doesn't modify input array."""
        original = np.random.randn(48000).astype(np.float32)
        original *= 0.3
        original_copy = original.copy()

        exp_params = {'target_crest_increase': 3.0, 'amount': 0.7}
        result = ExpansionStrategies.apply_rms_reduction_expansion(
            original, exp_params
        )

        # Verify input array was NOT modified
        np.testing.assert_array_equal(
            original,
            original_copy,
            err_msg="apply_rms_reduction_expansion() modified input array"
        )


class TestMultipleApplications:
    """Test that functions can be safely applied multiple times to same buffer."""

    def test_reuse_same_buffer_for_compression(self):
        """Verify same buffer can be used multiple times for compression."""
        original = np.random.randn(48000).astype(np.float32)

        # Apply compression twice with same input buffer
        result1 = CompressionStrategies.apply_soft_knee_compression(
            original, compression_amount=0.8
        )
        result2 = CompressionStrategies.apply_soft_knee_compression(
            original, compression_amount=0.8
        )

        # Results should be identical (deterministic)
        np.testing.assert_array_almost_equal(
            result1, result2,
            err_msg="Multiple compressions with same input should produce same output"
        )

    def test_reuse_same_buffer_for_expansion(self):
        """Verify same buffer can be used multiple times for expansion."""
        original = np.random.randn(48000).astype(np.float32)
        original *= 0.3

        # Apply expansion twice with same input buffer
        result1 = ExpansionStrategies.apply_peak_enhancement_expansion(
            original, expansion_amount=0.7
        )
        result2 = ExpansionStrategies.apply_peak_enhancement_expansion(
            original, expansion_amount=0.7
        )

        # Results should be identical (deterministic)
        np.testing.assert_array_almost_equal(
            result1, result2,
            err_msg="Multiple expansions with same input should produce same output"
        )


class TestReturnedArrayProperties:
    """Test that returned arrays have correct properties."""

    def test_compression_returns_ndarray(self):
        """Verify compression returns np.ndarray, not list."""
        original = np.random.randn(48000).astype(np.float32)

        result = CompressionStrategies.apply_soft_knee_compression(
            original, compression_amount=0.85
        )

        assert isinstance(result, np.ndarray), (
            "Compression must return np.ndarray, not list"
        )

    def test_expansion_returns_ndarray(self):
        """Verify expansion returns np.ndarray, not list."""
        original = np.random.randn(48000).astype(np.float32)
        original *= 0.3

        result = ExpansionStrategies.apply_peak_enhancement_expansion(
            original, expansion_amount=0.7
        )

        assert isinstance(result, np.ndarray), (
            "Expansion must return np.ndarray, not list"
        )

    def test_compression_preserves_sample_count(self):
        """Verify compression doesn't change sample count."""
        original = np.random.randn(48000).astype(np.float32)

        result = CompressionStrategies.apply_soft_knee_compression(
            original, compression_amount=0.85
        )

        assert len(result) == len(original), (
            "Compression must preserve sample count"
        )

    def test_expansion_preserves_sample_count(self):
        """Verify expansion doesn't change sample count."""
        original = np.random.randn(48000).astype(np.float32)
        original *= 0.3

        result = ExpansionStrategies.apply_peak_enhancement_expansion(
            original, expansion_amount=0.7
        )

        assert len(result) == len(original), (
            "Expansion must preserve sample count"
        )
