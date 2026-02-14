#!/usr/bin/env python
"""
Minimal test to verify fix for issue #2150.
Tests that compression/expansion functions don't modify input arrays in-place.
"""

import sys
import numpy as np

# Import directly to avoid problematic imports in __init__.py
sys.path.insert(0, '/mnt/data/src/matchering')

from auralis.core.processing.base.compression_expansion import (
    CompressionStrategies,
    ExpansionStrategies,
)


def test_compression_preserves_input():
    """Verify apply_soft_knee_compression() doesn't modify input array."""
    print("Testing compression input preservation...")

    # Create test audio
    original = np.random.randn(48000).astype(np.float32) * 0.5
    original_copy = original.copy()

    # Apply compression
    result = CompressionStrategies.apply_soft_knee_compression(
        original, compression_amount=0.85
    )

    # Verify input unchanged
    if np.array_equal(original, original_copy):
        print("✅ PASS: Compression preserved input array")
        return True
    else:
        print("❌ FAIL: Compression modified input array")
        return False


def test_expansion_preserves_input():
    """Verify apply_peak_enhancement_expansion() doesn't modify input array."""
    print("Testing expansion input preservation...")

    # Create test audio
    original = np.random.randn(48000).astype(np.float32) * 0.3
    original_copy = original.copy()

    # Apply expansion
    result = ExpansionStrategies.apply_peak_enhancement_expansion(
        original, expansion_amount=0.7
    )

    # Verify input unchanged
    if np.array_equal(original, original_copy):
        print("✅ PASS: Expansion preserved input array")
        return True
    else:
        print("❌ FAIL: Expansion modified input array")
        return False


def test_multiple_applications():
    """Verify same buffer can be reused for multiple operations."""
    print("Testing multiple applications with same buffer...")

    original = np.random.randn(48000).astype(np.float32) * 0.5

    # Apply compression twice
    result1 = CompressionStrategies.apply_soft_knee_compression(
        original, compression_amount=0.8
    )
    result2 = CompressionStrategies.apply_soft_knee_compression(
        original, compression_amount=0.8
    )

    # Results should be identical
    if np.allclose(result1, result2):
        print("✅ PASS: Multiple applications produced identical results")
        return True
    else:
        print("❌ FAIL: Multiple applications produced different results")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("Issue #2150 - In-place modification fix verification")
    print("=" * 60)
    print()

    all_passed = True

    all_passed &= test_compression_preserves_input()
    print()

    all_passed &= test_expansion_preserves_input()
    print()

    all_passed &= test_multiple_applications()
    print()

    print("=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED - Fix verified!")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
