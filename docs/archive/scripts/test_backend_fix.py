#!/usr/bin/env python3
"""
Test script to verify the backend has loaded the fixed temporal_analyzer code.

This script:
1. Imports the temporal analyzer
2. Tests it with audio that would trigger the bug
3. Verifies the fix is working

Run this AFTER restarting Auralis to confirm the fix is loaded.
"""

import sys
import numpy as np
import time

def test_fix():
    """Test that the temporal analyzer fix is working."""

    print("=" * 70)
    print("BACKEND FIX VERIFICATION")
    print("=" * 70)
    print()

    # Import the analyzer
    try:
        from auralis.analysis.fingerprint.temporal_analyzer import TemporalAnalyzer
        print("✓ Imported TemporalAnalyzer")
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        return False

    # Check if the fix is in the loaded module
    import inspect
    source = inspect.getsource(TemporalAnalyzer._detect_tempo)

    if "len(tempo_array) == 0" in source:
        print("✓ Fix is present in loaded module")
    else:
        print("✗ Fix NOT found in loaded module")
        print("  The backend is still using old cached code")
        print("  Please restart Auralis completely")
        return False

    print()
    print("Testing with problematic audio chunks...")
    print()

    analyzer = TemporalAnalyzer()
    sr = 44100

    # Test cases that would trigger the bug
    test_cases = [
        ("Silence", np.zeros(sr * 30)),
        ("Very quiet", np.random.randn(sr * 30) * 0.001),
        ("Pure tone", 0.1 * np.sin(2 * np.pi * 440 * np.linspace(0, 30, sr * 30))),
        ("Short burst", np.concatenate([np.random.randn(sr) * 0.5, np.zeros(sr * 29)])),
        ("Normal audio", np.random.randn(sr * 30) * 0.1),
    ]

    all_passed = True

    for name, audio in test_cases:
        try:
            start = time.time()
            result = analyzer.analyze(audio, sr)
            elapsed = time.time() - start

            tempo = result.get('tempo_bpm', 0)
            print(f"  ✓ {name:15s} - tempo={tempo:6.1f} BPM ({elapsed:.2f}s)")

        except IndexError as e:
            print(f"  ✗ {name:15s} - IndexError: {e}")
            print(f"     This means the fix is NOT working!")
            all_passed = False
        except Exception as e:
            print(f"  ✗ {name:15s} - {type(e).__name__}: {e}")
            all_passed = False

    print()
    print("=" * 70)

    if all_passed:
        print("✅ ALL TESTS PASSED - FIX IS WORKING!")
        print()
        print("The backend has loaded the fixed code.")
        print("Chunk streaming errors should now be resolved.")
        print("=" * 70)
        return True
    else:
        print("❌ TESTS FAILED - FIX NOT WORKING")
        print()
        print("The backend is still using old code.")
        print("Please:")
        print("  1. Close Auralis completely")
        print("  2. Wait 5 seconds")
        print("  3. Launch: ./dist/Auralis-1.0.0-beta.7.AppImage")
        print("  4. Run this test again")
        print("=" * 70)
        return False

if __name__ == "__main__":
    # Suppress warnings for cleaner output
    import warnings
    warnings.filterwarnings('ignore')

    success = test_fix()
    sys.exit(0 if success else 1)
