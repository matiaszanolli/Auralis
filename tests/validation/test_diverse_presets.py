#!/usr/bin/env python3
"""
Test preset system with diverse real-world material

This script tests all 5 presets on different production eras:
- 1980s: Dead Kennedys (natural dynamics)
- 1994: Rolling Stones (pre-loudness wars)
- 2008: Metallica Death Magnetic (peak loudness wars)
- 2012: Meshuggah (modern heavy production)
"""

import numpy as np
from pathlib import Path
from auralis.core.unified_config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.io.unified_loader import load_audio
from auralis.dsp.unified import calculate_loudness_units, rms

# Test files from user's collection
TEST_FILES = [
    {
        'path': '/mnt/Musica/Musica/(1980) Fresh Fruit For Rotting Vegetables/13 Holiday In Cambodia.flac',
        'era': '1980s Punk',
        'expected': 'Natural dynamics, likely quiet (-20 to -25 LUFS)'
    },
    {
        'path': '/mnt/Musica/Musica/(The) Rolling Stones - Voodoo Lounge (1994)(UK & Europe)[LP][24-96][FLAC]/A1. Love Is Strong.flac',
        'era': '1994 Rock',
        'expected': 'Pre-loudness wars, moderate levels (-14 to -18 LUFS)'
    },
    {
        'path': '/mnt/Musica/Musica/METALLICA [2008] [5LP] Death Magnetic [VERTIGO 2517-73731-0]',
        'era': '2008 Metal (Loudness Wars)',
        'expected': 'Heavily compressed, very loud (-8 to -10 LUFS)'
    },
    {
        'path': '/mnt/Musica/Musica/Meshuggah/2012 - Koloss',
        'era': '2012 Modern Metal',
        'expected': 'Modern mastering, streaming-optimized (-10 to -12 LUFS)'
    },
]

PRESETS = ['gentle', 'adaptive', 'warm', 'bright', 'punchy']


def analyze_audio(file_path: str):
    """Load and analyze audio file"""
    try:
        audio, sr = load_audio(file_path)

        # Calculate metrics
        lufs = calculate_loudness_units(audio, sr)
        rms_level = rms(audio)
        peak = np.max(np.abs(audio))

        # Calculate dynamic range estimate
        rms_db = 20 * np.log10(rms_level + 1e-10)
        peak_db = 20 * np.log10(peak + 1e-10)
        dynamic_range_estimate = peak_db - rms_db

        return {
            'lufs': lufs,
            'rms': rms_level,
            'peak': peak,
            'dr_estimate': dynamic_range_estimate,
            'sample_rate': sr,
            'duration': len(audio) / sr
        }
    except Exception as e:
        return {'error': str(e)}


def test_preset_on_file(file_path: str, preset: str, original_metrics: dict):
    """Test a single preset on a file"""
    try:
        # Load audio
        audio, sr = load_audio(file_path)

        # Process with preset
        config = UnifiedConfig()
        config.set_mastering_preset(preset)
        processor = HybridProcessor(config)

        processed = processor.process(audio)

        # Analyze processed output
        output_lufs = calculate_loudness_units(processed, sr)
        output_rms = rms(processed)
        output_peak = np.max(np.abs(processed))

        return {
            'preset': preset,
            'output_lufs': output_lufs,
            'output_rms': output_rms,
            'output_peak': output_peak,
            'lufs_change': output_lufs - original_metrics['lufs'],
            'clipped': output_peak >= 1.0
        }
    except Exception as e:
        return {'preset': preset, 'error': str(e)}


def main():
    print("=" * 80)
    print("PRESET SYSTEM TEST - DIVERSE MATERIAL")
    print("=" * 80)
    print()

    results = []

    for test_file in TEST_FILES:
        file_path = test_file['path']

        # Find first audio file in path
        path = Path(file_path)
        if path.is_dir():
            audio_files = list(path.glob('*.flac')) + list(path.glob('*.mp3'))
            if audio_files:
                file_path = str(audio_files[0])
            else:
                print(f"⚠️  No audio files found in {path}")
                continue

        if not Path(file_path).exists():
            print(f"⚠️  File not found: {file_path}")
            continue

        print(f"\n{'=' * 80}")
        print(f"Testing: {test_file['era']}")
        print(f"File: {Path(file_path).name}")
        print(f"Expected: {test_file['expected']}")
        print(f"{'=' * 80}\n")

        # Analyze original
        print("📊 Original Audio Analysis:")
        original = analyze_audio(file_path)

        if 'error' in original:
            print(f"   ❌ Error: {original['error']}")
            continue

        print(f"   LUFS: {original['lufs']:.2f}")
        print(f"   RMS: {original['rms']:.4f}")
        print(f"   Peak: {original['peak']:.4f}")
        print(f"   DR Estimate: {original['dr_estimate']:.2f} dB")
        print(f"   Duration: {original['duration']:.1f}s")
        print()

        # Test each preset
        print("🎛️  Testing Presets:")
        print(f"   {'Preset':<12} {'Output LUFS':<15} {'LUFS Change':<15} {'Peak':<10} {'Clipped'}")
        print(f"   {'-' * 70}")

        preset_results = []
        for preset in PRESETS:
            result = test_preset_on_file(file_path, preset, original)
            preset_results.append(result)

            if 'error' in result:
                print(f"   {preset:<12} ❌ Error: {result['error']}")
            else:
                clipped_icon = "⚠️ " if result['clipped'] else "✅"
                print(f"   {preset:<12} {result['output_lufs']:>8.2f} LUFS   {result['lufs_change']:>+8.2f} dB     "
                      f"{result['output_peak']:>6.4f}  {clipped_icon}")

        # Verify presets produce different outputs
        if preset_results and 'error' not in preset_results[0]:
            lufs_values = [r['output_lufs'] for r in preset_results if 'output_lufs' in r]
            lufs_range = max(lufs_values) - min(lufs_values)

            print()
            print(f"   📈 LUFS Range across presets: {lufs_range:.2f} dB")

            if lufs_range > 1.0:
                print(f"   ✅ Presets produce distinct outputs (range > 1.0 dB)")
            else:
                print(f"   ⚠️  Warning: Presets produce similar outputs (range < 1.0 dB)")

        results.append({
            'file': test_file,
            'original': original,
            'preset_results': preset_results
        })

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}\n")

    total_files = len(results)
    total_successful = sum(1 for r in results if 'error' not in r['original'])

    print(f"Files Tested: {total_files}")
    print(f"Successful: {total_successful}")
    print()

    # Check for clipping across all tests
    all_clipped = []
    for r in results:
        if 'preset_results' in r:
            clipped_presets = [pr for pr in r['preset_results'] if pr.get('clipped', False)]
            if clipped_presets:
                all_clipped.append((r['file']['era'], clipped_presets))

    if all_clipped:
        print("⚠️  WARNING: Clipping detected in:")
        for era, presets in all_clipped:
            preset_names = [p['preset'] for p in presets]
            print(f"   {era}: {', '.join(preset_names)}")
    else:
        print("✅ No clipping detected in any preset/file combination")

    print()


if __name__ == '__main__':
    main()
