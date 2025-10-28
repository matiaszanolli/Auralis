#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fingerprint Normalization Demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demonstrates how to use FingerprintNormalizer for similarity comparison

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.library import LibraryManager
from auralis.analysis.fingerprint import FingerprintNormalizer


def demo_normalization():
    """Demonstrate fingerprint normalization"""
    print("=" * 70)
    print("FINGERPRINT NORMALIZATION DEMO")
    print("=" * 70)

    # Initialize library
    print("\n1. Initializing library...")
    library = LibraryManager()

    # Check fingerprint count
    fp_count = library.fingerprints.get_count()
    print(f"   Found {fp_count} fingerprints in library")

    if fp_count < 10:
        print("\n   ⚠️  Need at least 10 fingerprints for normalization")
        print("   Run library scan with fingerprint extraction first")
        return

    # Create normalizer
    print("\n2. Creating normalizer...")
    normalizer = FingerprintNormalizer(use_robust=True)

    # Fit to library
    print("\n3. Fitting normalizer to library...")
    success = normalizer.fit(library.fingerprints, min_samples=10)

    if not success:
        print("   ❌ Failed to fit normalizer")
        return

    print("   ✅ Normalization statistics calculated")

    # Show statistics summary
    print("\n4. Normalization Statistics:")
    print("-" * 70)
    stats = normalizer.get_stats_summary()

    # Group by category
    categories = {
        'Frequency (7D)': ['sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
                          'upper_mid_pct', 'presence_pct', 'air_pct'],
        'Dynamics (3D)': ['lufs', 'crest_db', 'bass_mid_ratio'],
        'Temporal (4D)': ['tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio'],
        'Spectral (3D)': ['spectral_centroid', 'spectral_rolloff', 'spectral_flatness'],
        'Harmonic (3D)': ['harmonic_ratio', 'pitch_stability', 'chroma_energy'],
        'Variation (3D)': ['dynamic_range_variation', 'loudness_variation_std', 'peak_consistency'],
        'Stereo (2D)': ['stereo_width', 'phase_correlation'],
    }

    for category, dims in categories.items():
        print(f"\n   {category}:")
        for dim in dims:
            if dim in stats:
                s = stats[dim]
                print(f"     {dim:25s}: range=[{s['min']:7.2f}, {s['max']:7.2f}] "
                      f"mean={s['mean']:7.2f} std={s['std']:6.2f}")

    # Test normalization
    print("\n5. Testing normalization on first fingerprint...")
    fingerprints = library.fingerprints.get_all(limit=1)

    if fingerprints:
        fp = fingerprints[0]
        print(f"   Track ID: {fp.track_id}")

        # Get original vector
        original = fp.to_vector()
        print(f"\n   Original values (first 5 dims):")
        for i, name in enumerate(normalizer.DIMENSION_NAMES[:5]):
            print(f"     {name:20s}: {original[i]:8.3f}")

        # Normalize
        normalized = normalizer.normalize(original)
        print(f"\n   Normalized values (first 5 dims):")
        for i, name in enumerate(normalizer.DIMENSION_NAMES[:5]):
            print(f"     {name:20s}: {normalized[i]:8.3f} [0-1 scale]")

        # Verify all values are in [0, 1]
        assert np.all(normalized >= 0.0) and np.all(normalized <= 1.0)
        print("\n   ✅ All normalized values in [0, 1] range")

        # Test denormalization
        denormalized = normalizer.denormalize(normalized)
        print(f"\n   Denormalized values (first 5 dims):")
        for i, name in enumerate(normalizer.DIMENSION_NAMES[:5]):
            print(f"     {name:20s}: {denormalized[i]:8.3f} (original: {original[i]:8.3f})")

        # Check reconstruction error
        error = np.mean(np.abs(original - denormalized))
        print(f"\n   Reconstruction error: {error:.6f}")

    # Save statistics
    print("\n6. Saving normalization statistics...")
    stats_path = Path.home() / ".auralis" / "fingerprint_normalization.json"
    normalizer.save(str(stats_path))
    print(f"   ✅ Saved to {stats_path}")

    # Test loading
    print("\n7. Testing statistics reload...")
    normalizer2 = FingerprintNormalizer()
    normalizer2.load(str(stats_path))
    print(f"   ✅ Loaded successfully (fitted={normalizer2.is_fitted()})")

    print("\n" + "=" * 70)
    print("NORMALIZATION DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    demo_normalization()
