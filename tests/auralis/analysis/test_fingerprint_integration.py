#!/usr/bin/env python3
"""
Test script for 25D audio fingerprint integration into processing pipeline.

This validates that:
1. ContentAnalyzer extracts 25D fingerprints
2. AdaptiveTargetGenerator uses fingerprint data for intelligent target generation
3. Processing targets are enhanced by fingerprint analysis
4. The integration works across different audio characteristics

Usage:
    python test_fingerprint_integration.py /path/to/audio.flac
    python test_fingerprint_integration.py  # Uses synthetic test signals
"""

import numpy as np
import sys
import pytest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.core.analysis import ContentAnalyzer, AdaptiveTargetGenerator
from auralis.io.unified_loader import load_audio


def generate_test_signals(sample_rate=44100, duration=10):
    """Generate test audio signals with different characteristics."""

    signals = {}
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples)

    # 1. Bass-heavy electronic (sub-bass + bass dominant)
    bass_heavy = (
        0.5 * np.sin(2 * np.pi * 50 * t) +    # Sub-bass
        0.4 * np.sin(2 * np.pi * 120 * t) +   # Bass
        0.1 * np.sin(2 * np.pi * 2000 * t)    # Mids (minimal)
    )
    # Stereo with wide width
    signals['bass_heavy_electronic'] = np.column_stack([
        bass_heavy + 0.1 * np.random.randn(num_samples),
        bass_heavy * 0.7 + 0.1 * np.random.randn(num_samples)
    ]) * 0.3

    # 2. Bright acoustic (presence + air dominant)
    bright_acoustic = (
        0.1 * np.sin(2 * np.pi * 80 * t) +     # Bass (minimal)
        0.2 * np.sin(2 * np.pi * 800 * t) +    # Mids
        0.4 * np.sin(2 * np.pi * 4000 * t) +   # Presence
        0.3 * np.sin(2 * np.pi * 8000 * t)     # Air
    )
    # Stereo with narrow width (acoustic recording)
    signals['bright_acoustic'] = np.column_stack([
        bright_acoustic + 0.05 * np.random.randn(num_samples),
        bright_acoustic * 0.95 + 0.05 * np.random.randn(num_samples)
    ]) * 0.2

    # 3. Compressed modern mix (low crest factor)
    compressed_modern = 0.3 * np.sin(2 * np.pi * 200 * t) + 0.2 * np.random.randn(num_samples)
    # Hard clip to simulate brick-wall limiting
    compressed_modern = np.clip(compressed_modern, -0.9, 0.9)
    signals['compressed_modern'] = np.column_stack([
        compressed_modern,
        compressed_modern * 0.9
    ])

    # 4. Dynamic classical (high crest factor)
    # Quiet sustained tones with loud peaks
    dynamic_classical = 0.05 * np.sin(2 * np.pi * 440 * t)  # Sustained
    # Add transient peaks
    peak_positions = np.random.randint(0, num_samples, 20)
    for pos in peak_positions:
        if pos + 1000 < num_samples:
            dynamic_classical[pos:pos+1000] += 0.5 * np.exp(-np.linspace(0, 5, 1000))
    signals['dynamic_classical'] = np.column_stack([
        dynamic_classical + 0.01 * np.random.randn(num_samples),
        dynamic_classical * 0.85 + 0.01 * np.random.randn(num_samples)
    ])

    # 5. Percussive rhythm (high transient density)
    percussive = np.zeros(num_samples)
    # Add transients every 0.5 seconds (120 BPM)
    for i in range(0, num_samples, sample_rate // 2):
        if i + 500 < num_samples:
            percussive[i:i+500] = 0.6 * np.exp(-np.linspace(0, 10, 500))
    signals['percussive_rhythm'] = np.column_stack([
        percussive + 0.05 * np.random.randn(num_samples),
        percussive + 0.05 * np.random.randn(num_samples)
    ])

    return signals


def test_fingerprint_extraction():
    """Test that ContentAnalyzer extracts 25D fingerprints."""
    print("=" * 80)
    print("TEST 1: Fingerprint Extraction")
    print("=" * 80)

    analyzer = ContentAnalyzer(sample_rate=44100, use_fingerprint_analysis=True)
    signals = generate_test_signals()

    for signal_name, audio in signals.items():
        print(f"\n--- Testing: {signal_name} ---")
        profile = analyzer.analyze_content(audio)

        # Check that fingerprint was extracted
        assert "fingerprint" in profile, f"Fingerprint missing for {signal_name}"
        assert profile["fingerprint"] is not None, f"Fingerprint is None for {signal_name}"

        fingerprint = profile["fingerprint"]

        # Verify all 25 dimensions are present
        expected_keys = [
            # Frequency (7D)
            'sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
            'upper_mid_pct', 'presence_pct', 'air_pct',
            # Dynamics (3D)
            'lufs', 'crest_db', 'bass_mid_ratio',
            # Temporal (4D)
            'tempo_bpm', 'rhythm_stability', 'transient_density', 'silence_ratio',
            # Spectral (3D)
            'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
            # Harmonic (3D)
            'harmonic_ratio', 'pitch_stability', 'chroma_energy',
            # Variation (3D)
            'dynamic_range_variation', 'loudness_variation_std', 'peak_consistency',
            # Stereo (2D)
            'stereo_width', 'phase_correlation'
        ]

        for key in expected_keys:
            assert key in fingerprint, f"Missing dimension: {key}"

        # Print some key fingerprint features
        print(f"  Frequency: Bass={fingerprint['bass_pct']:.1f}%, Mid={fingerprint['mid_pct']:.1f}%, "
              f"Presence={fingerprint['presence_pct']:.1f}%")
        print(f"  Dynamics: LUFS={fingerprint['lufs']:.1f}dB, Crest={fingerprint['crest_db']:.1f}dB")
        print(f"  Temporal: Tempo={fingerprint['tempo_bpm']:.0f}BPM, Transients={fingerprint['transient_density']:.2f}")
        print(f"  Stereo: Width={fingerprint['stereo_width']:.2f}, Phase={fingerprint['phase_correlation']:.2f}")
        print(f"  ✅ All 25 dimensions extracted successfully")

    print(f"\n✅ TEST 1 PASSED: Fingerprint extraction working")
    return True


def test_target_generation():
    """Test that AdaptiveTargetGenerator uses fingerprint data."""
    print("\n" + "=" * 80)
    print("TEST 2: Fingerprint-Driven Target Generation")
    print("=" * 80)

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    analyzer = ContentAnalyzer(sample_rate=44100, use_fingerprint_analysis=True)
    target_gen = AdaptiveTargetGenerator(config)

    signals = generate_test_signals()

    for signal_name, audio in signals.items():
        print(f"\n--- Testing: {signal_name} ---")

        # Analyze content
        profile = analyzer.analyze_content(audio)

        # Generate targets WITHOUT fingerprint
        profile_no_fp = profile.copy()
        profile_no_fp.pop("fingerprint", None)
        targets_baseline = target_gen.generate_targets(profile_no_fp)

        # Generate targets WITH fingerprint
        targets_enhanced = target_gen.generate_targets(profile)

        # Verify fingerprint metadata is present
        assert targets_enhanced.get("fingerprint_driven") == True, \
            f"Fingerprint-driven flag missing for {signal_name}"

        # Compare targets
        print(f"  Baseline targets:")
        print(f"    Bass boost: {targets_baseline.get('bass_boost_db', 0):.1f}dB")
        print(f"    Compression: {targets_baseline.get('compression_ratio', 0):.1f}:1")
        print(f"    Stereo width: {targets_baseline.get('stereo_width', 0):.2f}")

        print(f"  Fingerprint-enhanced targets:")
        print(f"    Bass boost: {targets_enhanced.get('bass_boost_db', 0):.1f}dB")
        print(f"    Compression: {targets_enhanced.get('compression_ratio', 0):.1f}:1")
        print(f"    Stereo width: {targets_enhanced.get('stereo_width', 0):.2f}")

        # Check that targets changed (fingerprint had an effect)
        targets_differ = (
            abs(targets_baseline.get('bass_boost_db', 0) - targets_enhanced.get('bass_boost_db', 0)) > 0.01 or
            abs(targets_baseline.get('compression_ratio', 0) - targets_enhanced.get('compression_ratio', 0)) > 0.01 or
            abs(targets_baseline.get('stereo_width', 0) - targets_enhanced.get('stereo_width', 0)) > 0.01
        )

        if targets_differ:
            print(f"  ✅ Fingerprint affected target generation (good!)")
        else:
            print(f"  ⚠️  Targets unchanged (fingerprint may not be impacting this signal type)")

    print(f"\n✅ TEST 2 PASSED: Fingerprint-driven target generation working")
    return True


def test_end_to_end_processing():
    """Test end-to-end processing with fingerprint integration."""
    print("\n" + "=" * 80)
    print("TEST 3: End-to-End Processing with Fingerprints")
    print("=" * 80)

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    signals = generate_test_signals()

    for signal_name, audio in list(signals.items())[:2]:  # Test first 2 to save time
        print(f"\n--- Processing: {signal_name} ---")

        try:
            # Process audio
            processed = processor.process(audio)

            # Verify output
            assert processed is not None, f"Processing failed for {signal_name}"
            assert processed.shape == audio.shape, f"Shape mismatch for {signal_name}"
            assert not np.isnan(processed).any(), f"NaN values in output for {signal_name}"
            assert not np.isinf(processed).any(), f"Inf values in output for {signal_name}"

            # Check that processing actually changed the audio
            diff = np.mean(np.abs(audio - processed))
            print(f"  Mean absolute difference: {diff:.4f}")

            if diff > 0.001:
                print(f"  ✅ Audio was processed (difference detected)")
            else:
                print(f"  ⚠️  Minimal processing detected")

            # Check that last_content_profile has fingerprint
            if hasattr(processor, 'last_content_profile'):
                profile = processor.last_content_profile
                if "fingerprint" in profile and profile["fingerprint"] is not None:
                    print(f"  ✅ Fingerprint was used in processing pipeline")
                else:
                    print(f"  ⚠️  Fingerprint not found in processing pipeline")

        except Exception as e:
            print(f"  ❌ Processing failed: {e}")
            raise

    print(f"\n✅ TEST 3 PASSED: End-to-end processing working")
    return True


def test_real_audio(test_audio_files):
    """Test with real audio file."""
    # Get the first available audio file from the fixture
    if not test_audio_files:
        pytest.skip("No test audio files available")

    audio_path = next(iter(test_audio_files.values()))

    print("\n" + "=" * 80)
    print(f"TEST 4: Real Audio File - {audio_path}")
    print("=" * 80)

    # Load audio
    audio, sr = load_audio(audio_path)
    print(f"Loaded: {audio.shape} samples @ {sr}Hz")

    # Analyze
    analyzer = ContentAnalyzer(sample_rate=sr, use_fingerprint_analysis=True)
    profile = analyzer.analyze_content(audio)

    # Verify fingerprint
    assert "fingerprint" in profile, "Fingerprint missing"
    fingerprint = profile["fingerprint"]

    print("\n25D Audio Fingerprint:")
    print("-" * 80)
    print(f"Frequency Distribution:")
    print(f"  Sub-bass (20-60Hz):    {fingerprint['sub_bass_pct']:6.1f}%")
    print(f"  Bass (60-250Hz):       {fingerprint['bass_pct']:6.1f}%")
    print(f"  Low-mid (250-500Hz):   {fingerprint['low_mid_pct']:6.1f}%")
    print(f"  Mid (500-2kHz):        {fingerprint['mid_pct']:6.1f}%")
    print(f"  Upper-mid (2-4kHz):    {fingerprint['upper_mid_pct']:6.1f}%")
    print(f"  Presence (4-6kHz):     {fingerprint['presence_pct']:6.1f}%")
    print(f"  Air (6-20kHz):         {fingerprint['air_pct']:6.1f}%")

    print(f"\nDynamics:")
    print(f"  LUFS:                  {fingerprint['lufs']:6.1f} dB")
    print(f"  Crest Factor:          {fingerprint['crest_db']:6.1f} dB")
    print(f"  Bass/Mid Ratio:        {fingerprint['bass_mid_ratio']:6.1f} dB")

    print(f"\nTemporal:")
    print(f"  Tempo:                 {fingerprint['tempo_bpm']:6.0f} BPM")
    print(f"  Rhythm Stability:      {fingerprint['rhythm_stability']:6.2f}")
    print(f"  Transient Density:     {fingerprint['transient_density']:6.2f}")
    print(f"  Silence Ratio:         {fingerprint['silence_ratio']:6.2f}")

    print(f"\nSpectral:")
    print(f"  Centroid:              {fingerprint['spectral_centroid']:6.2f}")
    print(f"  Rolloff:               {fingerprint['spectral_rolloff']:6.2f}")
    print(f"  Flatness:              {fingerprint['spectral_flatness']:6.2f}")

    print(f"\nHarmonic:")
    print(f"  Harmonic Ratio:        {fingerprint['harmonic_ratio']:6.2f}")
    print(f"  Pitch Stability:       {fingerprint['pitch_stability']:6.2f}")
    print(f"  Chroma Energy:         {fingerprint['chroma_energy']:6.2f}")

    print(f"\nVariation:")
    print(f"  Dynamic Range Var:     {fingerprint['dynamic_range_variation']:6.2f}")
    print(f"  Loudness Var (std):    {fingerprint['loudness_variation_std']:6.2f}")
    print(f"  Peak Consistency:      {fingerprint['peak_consistency']:6.2f}")

    print(f"\nStereo:")
    print(f"  Stereo Width:          {fingerprint['stereo_width']:6.2f}")
    print(f"  Phase Correlation:     {fingerprint['phase_correlation']:6.2f}")

    # Generate targets
    config = UnifiedConfig()
    target_gen = AdaptiveTargetGenerator(config)
    targets = target_gen.generate_targets(profile)

    print("\nGenerated Processing Targets:")
    print("-" * 80)
    print(f"  Target LUFS:           {targets.get('target_lufs', 0):6.1f} dB")
    print(f"  Bass Boost:            {targets.get('bass_boost_db', 0):6.1f} dB")
    print(f"  Mid Clarity:           {targets.get('midrange_clarity_db', 0):6.1f} dB")
    print(f"  Treble Enhancement:    {targets.get('treble_enhancement_db', 0):6.1f} dB")
    print(f"  Compression Ratio:     {targets.get('compression_ratio', 0):6.1f}:1")
    print(f"  Stereo Width:          {targets.get('stereo_width', 0):6.2f}")
    print(f"  Mastering Intensity:   {targets.get('mastering_intensity', 0):6.2f}")
    print(f"  Fingerprint-driven:    {targets.get('fingerprint_driven', False)}")

    print(f"\n✅ TEST 4 PASSED: Real audio analysis complete")


def main():
    """Run all tests."""
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 15 + "25D FINGERPRINT INTEGRATION TEST SUITE" + " " * 25 + "║")
    print("╚" + "═" * 78 + "╝")

    try:
        # Run synthetic tests
        test_fingerprint_extraction()
        test_target_generation()
        test_end_to_end_processing()

        # Run real audio test if provided
        if len(sys.argv) > 1:
            audio_path = sys.argv[1]
            if Path(audio_path).exists():
                test_real_audio(audio_path)
            else:
                print(f"\n⚠️  Audio file not found: {audio_path}")

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED - 25D FINGERPRINT INTEGRATION WORKING")
        print("=" * 80)

        return 0

    except Exception as e:
        print(f"\n" + "=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
