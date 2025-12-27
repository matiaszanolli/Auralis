#!/usr/bin/env python3
"""
Comprehensive preset testing with diverse material types.
Tests adaptive processing across different genres and input levels.
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

def test_track(input_path, preset_name, expected_behavior):
    """Test processing a single track."""
    print(f"\n{'='*80}")
    print(f"Track: {input_path.name}")
    print(f"Preset: {preset_name}")
    print(f"Material Type: {expected_behavior['type']}")
    print(f"{'='*80}")

    # Load audio
    audio, sr = load_audio(str(input_path))

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
    changes = {
        'peak': proc_metrics['peak_db'] - orig_metrics['peak_db'],
        'rms': proc_metrics['rms_db'] - orig_metrics['rms_db'],
        'crest': proc_metrics['crest_db'] - orig_metrics['crest_db'],
        'lufs': proc_metrics['lufs'] - orig_metrics['lufs'],
    }

    print("\nCHANGES:")
    print(f"  Peak Δ:       {changes['peak']:+6.2f} dB")
    print(f"  RMS Δ:        {changes['rms']:+6.2f} dB")
    print(f"  Crest Δ:      {changes['crest']:+6.2f} dB")
    print(f"  LUFS Δ:       {changes['lufs']:+6.2f} dB")

    # Compare with expected Matchering behavior
    if 'matchering_rms_change' in expected_behavior:
        rms_diff = changes['rms'] - expected_behavior['matchering_rms_change']
        crest_diff = changes['crest'] - expected_behavior['matchering_crest_change']

        print("\nCOMPARISON WITH MATCHERING:")
        print(f"  Expected RMS Δ:   {expected_behavior['matchering_rms_change']:+.2f} dB")
        print(f"  Expected Crest Δ: {expected_behavior['matchering_crest_change']:+.2f} dB")
        print(f"  RMS diff:         {rms_diff:+.2f} dB")
        print(f"  Crest diff:       {crest_diff:+.2f} dB")

        # Assessment
        rms_ok = abs(rms_diff) < 2.0
        crest_ok = abs(crest_diff) < 2.0

        if rms_ok and crest_ok:
            print("  ✅ GOOD - Close to Matchering behavior")
            assessment = "good"
        elif rms_ok or crest_ok:
            print("  ⚠️  ACCEPTABLE - Partially matches Matchering")
            assessment = "acceptable"
        else:
            print("  ❌ NEEDS TUNING - Differs significantly from Matchering")
            assessment = "needs_tuning"
    else:
        assessment = "no_reference"

    # Save output
    output_path = f"/tmp/auralis_{preset_name}_{input_path.stem}.wav"
    save(output_path, processed_audio, sr, subtype='PCM_16')
    print(f"\nSaved to: {output_path}")

    return {
        'track': input_path.name,
        'preset': preset_name,
        'material_type': expected_behavior['type'],
        'original': orig_metrics,
        'processed': proc_metrics,
        'changes': changes,
        'assessment': assessment,
        'expected': expected_behavior,
    }

def main():
    print("="*80)
    print("COMPREHENSIVE PRESET TESTING")
    print("Testing Adaptive Processing with Diverse Material")
    print("="*80)

    test_cases = [
        # CATEGORY 1: Under-leveled Industrial Metal (Static-X)
        {
            'path': '/mnt/Musica/Musica/Static-X/Wisconsin Death Trip/Bled For Days.mp3',
            'preset': 'punchy',
            'expected': {
                'type': 'under_leveled_industrial',
                'matchering_rms_change': 5.96,
                'matchering_crest_change': 1.89,
            }
        },

        # CATEGORY 2: Live Thrash Metal (Testament)
        {
            'path': '/mnt/Musica/Musica/Testament/Live/1995-Live at the Fillmore/01 The Preacher.mp3',
            'preset': 'live',
            'expected': {
                'type': 'live_recording',
                'matchering_rms_change': 1.87,
                'matchering_crest_change': -1.97,
            }
        },
        {
            'path': '/mnt/Musica/Musica/Testament/2000-The Very Best of Testament/04 The New Order.mp3',
            'preset': 'punchy',
            'expected': {
                'type': 'live_recording',
                'matchering_rms_change': 2.52,
                'matchering_crest_change': -2.62,
            }
        },

        # CATEGORY 3: Moderate Thrash (Slayer)
        {
            'path': '/mnt/Musica/Musica/VA - 100 Greatest Thrash Metal Songs (2010)/051. South Of Heaven - Slayer.mp3',
            'preset': 'punchy',
            'expected': {
                'type': 'well_mastered_metal',
                'matchering_rms_change': 2.80,
                'matchering_crest_change': -1.80,
            }
        },

        # CATEGORY 4: Well-mastered classic rock (Iron Maiden Powerslave)
        {
            'path': '/mnt/Musica/Musica/Iron Maiden/1984 - Powerslave/03 2 Minutes to Midnight.mp3',
            'preset': 'adaptive',
            'expected': {
                'type': 'well_mastered_classic',
                'matchering_rms_change': -4.51,
                'matchering_crest_change': 5.97,
            }
        },
        {
            'path': '/mnt/Musica/Musica/Iron Maiden/1984 - Powerslave/02 Powerslave.mp3',
            'preset': 'adaptive',
            'expected': {
                'type': 'well_mastered_classic',
                'matchering_rms_change': -0.97,
                'matchering_crest_change': 2.93,
            }
        },

        # CATEGORY 5: New Wave / Rock (Soda Stereo)
        {
            'path': '/mnt/Musica/Musica/Soda Stereo/Doble Vida/01 Soda Stereo - Picnic en el 4° B.mp3',
            'preset': 'adaptive',
            'expected': {
                'type': 'well_mastered_new_wave',
                'matchering_rms_change': 3.55,
                'matchering_crest_change': -2.23,
            }
        },
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        track_path = Path(test_case['path'])

        if not track_path.exists():
            print(f"\n⚠️  Skipping test {i}/{len(test_cases)}: {test_case['path']} - file not found")
            continue

        print(f"\n\n{'#'*80}")
        print(f"TEST {i}/{len(test_cases)}")
        print(f"{'#'*80}")

        try:
            result = test_track(track_path, test_case['preset'], test_case['expected'])
            results.append(result)
        except Exception as e:
            print(f"\n❌ ERROR processing {track_path.name}: {e}")
            import traceback
            traceback.print_exc()

    # Generate summary report
    if results:
        print("\n\n" + "="*80)
        print("SUMMARY REPORT")
        print("="*80)

        # Group by material type
        material_types = {}
        for result in results:
            mat_type = result['material_type']
            if mat_type not in material_types:
                material_types[mat_type] = []
            material_types[mat_type].append(result)

        for mat_type, type_results in material_types.items():
            print(f"\n{mat_type.upper().replace('_', ' ')}:")
            print(f"  Tracks tested: {len(type_results)}")

            avg_rms = np.mean([r['changes']['rms'] for r in type_results])
            avg_crest = np.mean([r['changes']['crest'] for r in type_results])

            print(f"  Average RMS Δ:   {avg_rms:+.2f} dB")
            print(f"  Average Crest Δ: {avg_crest:+.2f} dB")

            # Show individual assessments
            good = sum(1 for r in type_results if r['assessment'] == 'good')
            acceptable = sum(1 for r in type_results if r['assessment'] == 'acceptable')
            needs_tuning = sum(1 for r in type_results if r['assessment'] == 'needs_tuning')

            print(f"  Assessment: {good} good, {acceptable} acceptable, {needs_tuning} needs tuning")

        # Overall statistics
        print(f"\n\nOVERALL STATISTICS:")
        print(f"  Total tracks tested: {len(results)}")

        total_good = sum(1 for r in results if r['assessment'] == 'good')
        total_acceptable = sum(1 for r in results if r['assessment'] == 'acceptable')
        total_needs_tuning = sum(1 for r in results if r['assessment'] == 'needs_tuning')

        success_rate = (total_good + total_acceptable) / len(results) * 100

        print(f"  ✅ Good: {total_good}")
        print(f"  ⚠️  Acceptable: {total_acceptable}")
        print(f"  ❌ Needs tuning: {total_needs_tuning}")
        print(f"  Success rate: {success_rate:.1f}%")

if __name__ == "__main__":
    main()
