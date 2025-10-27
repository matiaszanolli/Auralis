#!/usr/bin/env python3
"""
Test Preset Integration
~~~~~~~~~~~~~~~~~~~~~~~

Verify that different presets produce distinct audio output.
"""

import numpy as np
from auralis.core.config import UnifiedConfig, create_preset_profiles
from auralis.core.hybrid_processor import HybridProcessor

def test_preset_integration():
    """Test that each preset produces different processing results"""

    print("=" * 60)
    print("Testing Preset Integration")
    print("=" * 60)

    # Set random seed for reproducible results
    np.random.seed(42)

    # Create test audio (sine wave + noise)
    sample_rate = 44100
    duration = 2.0  # 2 seconds
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Generate test audio: 440Hz sine + harmonics + noise
    audio = (
        0.3 * np.sin(2 * np.pi * 440 * t) +      # Fundamental
        0.1 * np.sin(2 * np.pi * 880 * t) +      # 2nd harmonic
        0.05 * np.sin(2 * np.pi * 1320 * t) +    # 3rd harmonic
        0.02 * np.random.randn(len(t))           # Noise
    )

    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.8

    # Make stereo
    audio = np.column_stack([audio, audio])

    presets = ['adaptive', 'gentle', 'warm', 'bright', 'punchy']
    results = {}

    print("\nProcessing with each preset...")
    print("-" * 60)

    for preset_name in presets:
        print(f"\n{preset_name.upper()} Preset:")

        # Create config with preset
        config = UnifiedConfig()
        config.set_processing_mode("adaptive")
        config.mastering_profile = preset_name

        # Get preset profile to show settings
        preset_profile = config.get_preset_profile()
        if preset_profile:
            print(f"  Target LUFS: {preset_profile.target_lufs:.1f}")
            print(f"  Bass Boost: {preset_profile.low_shelf_gain:+.1f} dB")
            print(f"  Treble Boost: {preset_profile.high_shelf_gain:+.1f} dB")
            print(f"  Compression: {preset_profile.compression_ratio:.1f}:1")
            print(f"  EQ Blend: {preset_profile.eq_blend:.1f}")
            print(f"  Dynamics Blend: {preset_profile.dynamics_blend:.1f}")

        # Process audio (make a copy to avoid any potential state issues)
        processor = HybridProcessor(config)
        processed = processor.process(audio.copy())

        # Analyze results
        rms = np.sqrt(np.mean(processed ** 2))
        peak = np.max(np.abs(processed))
        crest_factor = peak / (rms + 1e-6)

        results[preset_name] = {
            'rms': rms,
            'peak': peak,
            'crest_factor': crest_factor,
            'processed': processed
        }

        print(f"  Output RMS: {rms:.4f}")
        print(f"  Output Peak: {peak:.4f}")
        print(f"  Crest Factor: {crest_factor:.2f}")

    # Compare results
    print("\n" + "=" * 60)
    print("COMPARISON ANALYSIS")
    print("=" * 60)

    # Check that presets produce different results
    rms_values = [results[p]['rms'] for p in presets]
    peak_values = [results[p]['peak'] for p in presets]
    crest_values = [results[p]['crest_factor'] for p in presets]

    rms_range = max(rms_values) - min(rms_values)
    peak_range = max(peak_values) - min(peak_values)
    crest_range = max(crest_values) - min(crest_values)

    print(f"\nRMS Range: {rms_range:.4f} ({min(rms_values):.4f} to {max(rms_values):.4f})")
    print(f"Peak Range: {peak_range:.4f} ({min(peak_values):.4f} to {max(peak_values):.4f})")
    print(f"Crest Factor Range: {crest_range:.2f} ({min(crest_values):.2f} to {max(crest_values):.2f})")

    # Verify presets are distinct
    if rms_range > 0.01:
        print("\n✅ PASS: Presets produce significantly different RMS levels")
    else:
        print("\n❌ FAIL: Presets produce nearly identical RMS levels")

    if crest_range > 0.1:
        print("✅ PASS: Presets produce different dynamics (crest factor)")
    else:
        print("❌ FAIL: Presets produce nearly identical dynamics")

    # Expected behaviors
    print("\n" + "-" * 60)
    print("Expected Behavior Verification:")
    print("-" * 60)

    gentle_rms = results['gentle']['rms']
    punchy_rms = results['punchy']['rms']

    if punchy_rms > gentle_rms:
        print("✅ Punchy is louder than Gentle (expected)")
    else:
        print("⚠️  Punchy should be louder than Gentle")

    gentle_crest = results['gentle']['crest_factor']
    punchy_crest = results['punchy']['crest_factor']

    if gentle_crest > punchy_crest:
        print("✅ Gentle has more dynamics than Punchy (expected)")
    else:
        print("⚠️  Gentle should preserve more dynamics than Punchy")

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)

    return results


if __name__ == "__main__":
    results = test_preset_integration()
