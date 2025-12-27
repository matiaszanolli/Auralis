#!/usr/bin/env python3
"""
Test adaptive processing with different material types.
Compares Auralis output with Matchering references.
"""

from pathlib import Path

import numpy as np

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.dsp.basic import rms
from auralis.dsp.utils import calculate_loudness_units
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio


def analyze_audio(audio):
    """Analyze audio and return metrics."""
    peak = np.max(np.abs(audio))
    peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf

    rms_value = rms(audio)
    rms_db = 20 * np.log10(rms_value) if rms_value > 0 else -np.inf

    crest_db = peak_db - rms_db

    lufs = calculate_loudness_units(audio, 44100)

    return {
        'peak_db': peak_db,
        'rms_db': rms_db,
        'crest_db': crest_db,
        'lufs': lufs,
    }

def test_track(input_path, preset_name="adaptive", output_suffix=""):
    """Test processing a single track."""
    print(f"\nTesting: {input_path.name}")
    print(f"Preset: {preset_name}")
    print("=" * 80)

    # Load audio
    audio, sr = load_audio(str(input_path))
    print(f"Loaded audio: {audio.shape}, Sample rate: {sr} Hz")

    # Analyze original
    orig_metrics = analyze_audio(audio)
    print("\nORIGINAL:")
    print(f"  Peak:         {orig_metrics['peak_db']:6.2f} dB")
    print(f"  RMS:          {orig_metrics['rms_db']:6.2f} dB")
    print(f"  Crest Factor: {orig_metrics['crest_db']:6.2f} dB")
    print(f"  LUFS:         {orig_metrics['lufs']:6.2f}")

    # Process with Auralis
    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    config.set_mastering_preset(preset_name)

    processor = HybridProcessor(config)
    processed_audio = processor.process(audio)

    # Analyze processed
    proc_metrics = analyze_audio(processed_audio)
    print("\nAURALIS PROCESSED:")
    print(f"  Peak:         {proc_metrics['peak_db']:6.2f} dB")
    print(f"  RMS:          {proc_metrics['rms_db']:6.2f} dB")
    print(f"  Crest Factor: {proc_metrics['crest_db']:6.2f} dB")
    print(f"  LUFS:         {proc_metrics['lufs']:6.2f}")

    # Calculate changes
    peak_change = proc_metrics['peak_db'] - orig_metrics['peak_db']
    rms_change = proc_metrics['rms_db'] - orig_metrics['rms_db']
    crest_change = proc_metrics['crest_db'] - orig_metrics['crest_db']
    lufs_change = proc_metrics['lufs'] - orig_metrics['lufs']

    print("\nCHANGES:")
    print(f"  Peak Δ:       {peak_change:+6.2f} dB")
    print(f"  RMS Δ:        {rms_change:+6.2f} dB")
    print(f"  Crest Δ:      {crest_change:+6.2f} dB")
    print(f"  LUFS Δ:       {lufs_change:+6.2f} dB")

    # Save output
    output_path = f"/tmp/auralis_test_{input_path.stem}{output_suffix}.wav"
    save(output_path, processed_audio, sr, subtype='PCM_16')
    print(f"\nSaved to: {output_path}")

    return {
        'original': orig_metrics,
        'processed': proc_metrics,
        'changes': {
            'peak': peak_change,
            'rms': rms_change,
            'crest': crest_change,
            'lufs': lufs_change,
        }
    }

def main():
    print("=" * 80)
    print("AURALIS ADAPTIVE PROCESSING TEST")
    print("Testing with Heavy Metal/Industrial Material")
    print("=" * 80)

    # Test cases with expected Matchering behavior
    test_cases = [
        {
            'name': 'Static-X - Bled For Days (Under-leveled)',
            'path': '/mnt/Musica/Musica/Static-X/Wisconsin Death Trip/Bled For Days.mp3',
            'preset': 'punchy',
            'expected': {
                'rms_change': 5.96,  # Matchering: +5.96 dB
                'crest_change': 1.89,  # Matchering: +1.89 dB
            }
        },
        {
            'name': 'Static-X - December (Very under-leveled)',
            'path': '/mnt/Musica/Musica/Static-X/Wisconsin Death Trip/December.mp3',
            'preset': 'punchy',
            'expected': {
                'rms_change': 3.72,  # Matchering: +3.72 dB
                'crest_change': 2.43,  # Matchering: +2.43 dB
            }
        },
        {
            'name': 'Static-X - Fix (Under-leveled)',
            'path': '/mnt/Musica/Musica/Static-X/Wisconsin Death Trip/Fix.mp3',
            'preset': 'punchy',
            'expected': {
                'rms_change': 6.73,  # Matchering: +6.73 dB
                'crest_change': 1.32,  # Matchering: +1.32 dB
            }
        },
    ]

    results = []

    for test_case in test_cases:
        track_path = Path(test_case['path'])
        if not track_path.exists():
            print(f"\n⚠️  Skipping {test_case['name']} - file not found")
            continue

        print(f"\n\n{'=' * 80}")
        print(f"TEST CASE: {test_case['name']}")
        print(f"Expected RMS Δ: {test_case['expected']['rms_change']:+.2f} dB")
        print(f"Expected Crest Δ: {test_case['expected']['crest_change']:+.2f} dB")
        print(f"{'=' * 80}")

        result = test_track(track_path, preset_name=test_case['preset'])
        result['test_case'] = test_case
        results.append(result)

        # Compare with expected
        rms_diff = result['changes']['rms'] - test_case['expected']['rms_change']
        crest_diff = result['changes']['crest'] - test_case['expected']['crest_change']

        print("\nCOMPARISON WITH MATCHERING:")
        print(f"  RMS Δ diff:   {rms_diff:+.2f} dB (Auralis: {result['changes']['rms']:+.2f}, Matchering: {test_case['expected']['rms_change']:+.2f})")
        print(f"  Crest Δ diff: {crest_diff:+.2f} dB (Auralis: {result['changes']['crest']:+.2f}, Matchering: {test_case['expected']['crest_change']:+.2f})")

        # Assessment
        rms_ok = abs(rms_diff) < 2.0  # Within 2 dB is good
        crest_ok = abs(crest_diff) < 2.0

        if rms_ok and crest_ok:
            print("  ✅ GOOD - Close to Matchering behavior")
        elif rms_ok or crest_ok:
            print("  ⚠️  ACCEPTABLE - Partially matches Matchering")
        else:
            print("  ❌ NEEDS TUNING - Differs significantly from Matchering")

    # Summary
    if results:
        print("\n\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        avg_rms_change = np.mean([r['changes']['rms'] for r in results])
        avg_crest_change = np.mean([r['changes']['crest'] for r in results])

        print(f"\nAuralis Average Changes ({len(results)} tracks):")
        print(f"  RMS Δ:   {avg_rms_change:+.2f} dB")
        print(f"  Crest Δ: {avg_crest_change:+.2f} dB")

        print(f"\nMatchering Expected (from analysis):")
        print(f"  RMS Δ:   +5.47 dB (average for Static-X)")
        print(f"  Crest Δ: +1.88 dB (average for Static-X)")

        diff_rms = avg_rms_change - 5.47
        diff_crest = avg_crest_change - 1.88

        print(f"\nDifference:")
        print(f"  RMS:   {diff_rms:+.2f} dB")
        print(f"  Crest: {diff_crest:+.2f} dB")

if __name__ == "__main__":
    main()
