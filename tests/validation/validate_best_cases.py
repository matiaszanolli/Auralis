#!/usr/bin/env python3
"""
Test Matchering's best-case albums
These albums represent Matchering working at its best
"""

import sys

import numpy as np

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.dsp.basic import rms
from auralis.io.unified_loader import load_audio

# Best-case test tracks
BEST_CASES = [
    # The Damned - Machine Gun Etiquette (Punk/New Wave)
    ("The Damned - Love Song",
     "/mnt/Musica/Musica/The Damned/Studio Albums/1979 - Machine Gun Etiquette (320-366)/01. Love Song.mp3",
     "/mnt/audio/Audio/Remasters/The Damned - Machine Gun Etiquette/01. Love Song.flac",
     "punk"),

    ("The Damned - Machine Gun Etiquette",
     "/mnt/Musica/Musica/The Damned/Studio Albums/1979 - Machine Gun Etiquette (320-366)/02. Machine Gun Etiquette.mp3",
     "/mnt/audio/Audio/Remasters/The Damned - Machine Gun Etiquette/02. Machine Gun Etiquette.flac",
     "punk"),

    # Pantera - Far Beyond Driven (Groove Metal)
    ("Pantera - Strength Beyond Strength",
     "/mnt/Musica/Musica/Pantera/(1994) Pantera - Far Beyond Driven  (20th Anniversary Deluxe Edition) [16Bit-44.1kHz]/Disc 1/01. Strength Beyond Strength.flac",
     "/mnt/audio/Audio/Remasters/Pantera - Far Beyond Driven/A1. Strength Beyond Strength.flac",
     "groove_metal"),

    ("Pantera - 5 Minutes Alone",
     "/mnt/Musica/Musica/Pantera/(1994) Pantera - Far Beyond Driven  (20th Anniversary Deluxe Edition) [16Bit-44.1kHz]/Disc 1/03. 5 Minutes Alone.flac",
     "/mnt/audio/Audio/Remasters/Pantera - Far Beyond Driven/A3. 5 Minutes Alone.flac",
     "groove_metal"),

    # Motörhead - Inferno (Hard Rock/Heavy Metal)
    ("Motörhead - Terminal Show",
     "/mnt/Musica/Musica/Motörhead/2004  Inferno/(01) [Motorhead] Terminal Show.flac",
     "/mnt/audio/Audio/Remasters/Motörhead - Inferno/(01) [Motorhead] Terminal Show.flac",
     "heavy_metal"),

    ("Motörhead - Killers",
     "/mnt/Musica/Musica/Motörhead/2004  Inferno/(02) [Motorhead] Killers.flac",
     "/mnt/audio/Audio/Remasters/Motörhead - Inferno/(02) [Motorhead] Killers.flac",
     "heavy_metal"),
]

def analyze_track(name, orig_path, ref_path, genre):
    """Analyze a single track and return detailed stats"""
    print(f"\n{'='*80}")
    print(f"{name} ({genre})")
    print('='*80)

    try:
        # Load audio
        orig_audio, _ = load_audio(orig_path)
        orig_mono = np.mean(orig_audio, axis=1) if orig_audio.ndim == 2 else orig_audio

        ref_audio, _ = load_audio(ref_path)
        ref_mono = np.mean(ref_audio, axis=1) if ref_audio.ndim == 2 else ref_audio

        # Analyze original
        orig_peak = np.max(np.abs(orig_mono))
        orig_peak_db = 20 * np.log10(orig_peak)
        orig_rms_val = rms(orig_mono)
        orig_rms_db = 20 * np.log10(orig_rms_val)
        orig_crest = orig_peak_db - orig_rms_db

        # Analyze reference
        ref_peak = np.max(np.abs(ref_mono))
        ref_peak_db = 20 * np.log10(ref_peak)
        ref_rms_val = rms(ref_mono)
        ref_rms_db = 20 * np.log10(ref_rms_val)
        ref_crest = ref_peak_db - ref_rms_db

        # Matchering changes
        expected_rms_change = ref_rms_db - orig_rms_db
        expected_crest_change = ref_crest - orig_crest

        print(f"\nORIGINAL:")
        print(f"  Peak: {orig_peak_db:6.2f} dB")
        print(f"  RMS:  {orig_rms_db:6.2f} dB")
        print(f"  Crest: {orig_crest:5.2f} dB")

        print(f"\nMATCHERING TARGET:")
        print(f"  Peak: {ref_peak_db:6.2f} dB")
        print(f"  RMS:  {ref_rms_db:6.2f} dB")
        print(f"  Crest: {ref_crest:5.2f} dB")

        print(f"\nMATCHERING CHANGES:")
        print(f"  RMS Δ:   {expected_rms_change:+6.2f} dB")
        print(f"  Crest Δ: {expected_crest_change:+6.2f} dB")

        # Process with Auralis
        print(f"\nProcessing with Auralis...")
        config = UnifiedConfig()
        config.set_mastering_preset('adaptive')
        processor = HybridProcessor(config)

        processed = processor.process(orig_audio)

        proc_mono = np.mean(processed, axis=1) if processed.ndim == 2 else processed
        proc_peak = np.max(np.abs(proc_mono))
        proc_peak_db = 20 * np.log10(proc_peak)
        proc_rms_val = rms(proc_mono)
        proc_rms_db = 20 * np.log10(proc_rms_val)
        proc_crest = proc_peak_db - proc_rms_db

        result_rms_change = proc_rms_db - orig_rms_db
        result_crest_change = proc_crest - orig_crest

        print(f"\nAURALIS RESULT:")
        print(f"  Peak: {proc_peak_db:6.2f} dB")
        print(f"  RMS:  {proc_rms_db:6.2f} dB")
        print(f"  Crest: {proc_crest:5.2f} dB")

        print(f"\nAURALIS CHANGES:")
        print(f"  RMS Δ:   {result_rms_change:+6.2f} dB")
        print(f"  Crest Δ: {result_crest_change:+6.2f} dB")

        rms_error = abs(result_rms_change - expected_rms_change)
        crest_error = abs(result_crest_change - expected_crest_change)

        print(f"\nACCURACY:")
        print(f"  RMS error:   {rms_error:.2f} dB")
        print(f"  Crest error: {crest_error:.2f} dB")

        if rms_error < 1.0 and crest_error < 1.5:
            status = "✅ EXCELLENT"
        elif rms_error < 2.0 and crest_error < 2.5:
            status = "✅ GOOD"
        else:
            status = "⚠️  ACCEPTABLE"

        print(f"  Status: {status}")

        return {
            'name': name,
            'genre': genre,
            'orig_rms': orig_rms_db,
            'orig_crest': orig_crest,
            'expected_rms_change': expected_rms_change,
            'expected_crest_change': expected_crest_change,
            'result_rms_change': result_rms_change,
            'result_crest_change': result_crest_change,
            'rms_error': rms_error,
            'crest_error': crest_error,
            'status': status
        }

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("="*80)
    print("BEST-CASE ALBUMS TESTING")
    print("Albums where Matchering excels")
    print("="*80)

    results = []
    for name, orig_path, ref_path, genre in BEST_CASES:
        result = analyze_track(name, orig_path, ref_path, genre)
        if result:
            results.append(result)

    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY - MATCHERING BEST CASES")
    print('='*80)

    if results:
        excellent = [r for r in results if '✅ EXCELLENT' in r['status']]
        good = [r for r in results if '✅ GOOD' in r['status']]
        acceptable = [r for r in results if '⚠️' in r['status']]

        print(f"\nResults:")
        print(f"  ✅ EXCELLENT:  {len(excellent)}/{len(results)}")
        print(f"  ✅ GOOD:       {len(good)}/{len(results)}")
        print(f"  ⚠️  ACCEPTABLE: {len(acceptable)}/{len(results)}")

        avg_rms_error = np.mean([r['rms_error'] for r in results])
        avg_crest_error = np.mean([r['crest_error'] for r in results])

        print(f"\nAverage Errors:")
        print(f"  RMS:   {avg_rms_error:.2f} dB")
        print(f"  Crest: {avg_crest_error:.2f} dB")

        # Group by genre
        print(f"\nBy Genre:")
        genres = {}
        for r in results:
            if r['genre'] not in genres:
                genres[r['genre']] = []
            genres[r['genre']].append(r)

        for genre, tracks in genres.items():
            avg_error = np.mean([t['rms_error'] for t in tracks])
            print(f"  {genre:20s}: {len(tracks)} tracks, avg {avg_error:.2f} dB RMS error")

        # Analyze Matchering patterns
        print(f"\n{'='*80}")
        print("MATCHERING PATTERNS IN BEST CASES")
        print('='*80)

        print(f"\nOriginal Characteristics:")
        avg_orig_rms = np.mean([r['orig_rms'] for r in results])
        avg_orig_crest = np.mean([r['orig_crest'] for r in results])
        print(f"  Average original RMS:   {avg_orig_rms:.2f} dB")
        print(f"  Average original crest: {avg_orig_crest:.2f} dB")

        print(f"\nMatchering Strategy:")
        avg_rms_delta = np.mean([r['expected_rms_change'] for r in results])
        avg_crest_delta = np.mean([r['expected_crest_change'] for r in results])
        print(f"  Average RMS change:   {avg_rms_delta:+.2f} dB")
        print(f"  Average crest change: {avg_crest_delta:+.2f} dB")

        # Identify patterns
        rms_increases = [r for r in results if r['expected_rms_change'] > 0.5]
        rms_decreases = [r for r in results if r['expected_rms_change'] < -0.5]
        rms_stable = [r for r in results if abs(r['expected_rms_change']) <= 0.5]

        print(f"\nRMS Change Distribution:")
        print(f"  Increases (>+0.5 dB): {len(rms_increases)}")
        print(f"  Stable (±0.5 dB):     {len(rms_stable)}")
        print(f"  Decreases (<-0.5 dB): {len(rms_decreases)}")

        crest_increases = [r for r in results if r['expected_crest_change'] > 0.5]
        crest_decreases = [r for r in results if r['expected_crest_change'] < -0.5]
        crest_stable = [r for r in results if abs(r['expected_crest_change']) <= 0.5]

        print(f"\nCrest Change Distribution:")
        print(f"  Increases (>+0.5 dB): {len(crest_increases)}")
        print(f"  Stable (±0.5 dB):     {len(crest_stable)}")
        print(f"  Decreases (<-0.5 dB): {len(crest_decreases)}")

if __name__ == "__main__":
    main()
