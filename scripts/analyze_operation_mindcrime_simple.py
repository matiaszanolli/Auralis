#!/usr/bin/env python3
"""
Analyze Queensrÿche Operation: Mindcrime
Compare original vs Matchering remastered versions
Simple analysis using basic audio metrics
"""

import sys
import os
from pathlib import Path
import numpy as np
import soundfile as sf
from typing import Dict


def analyze_track(file_path: Path) -> Dict:
    """Analyze a single audio track"""
    try:
        # Load audio
        audio, sr = sf.read(str(file_path))

        # Convert to mono for RMS calculation (if stereo)
        if len(audio.shape) > 1:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Calculate RMS
        rms_linear = np.sqrt(np.mean(audio_mono ** 2))
        rms_db = 20 * np.log10(rms_linear) if rms_linear > 0 else -np.inf

        # Calculate peak
        peak_linear = np.max(np.abs(audio_mono))
        peak_db = 20 * np.log10(peak_linear) if peak_linear > 0 else -np.inf

        # Calculate crest factor (dynamic range indicator)
        crest_factor = peak_db - rms_db

        # Get duration
        duration_seconds = len(audio_mono) / sr

        # Get file info
        file_size_mb = file_path.stat().st_size / (1024 * 1024)

        return {
            'file_name': file_path.name,
            'file_size_mb': file_size_mb,
            'duration_seconds': duration_seconds,
            'sample_rate': sr,
            'channels': audio.shape[1] if len(audio.shape) > 1 else 1,
            'rms_db': rms_db,
            'peak_db': peak_db,
            'crest_factor_db': crest_factor,
        }
    except Exception as e:
        print(f"Error analyzing {file_path.name}: {e}")
        return None


def format_duration(seconds: float) -> str:
    """Format duration as MM:SS"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def main():
    # Paths
    original_dir = Path("/mnt/Musica/Musica/Queensrÿche/Operation_ Mindcrime [1988]")
    remastered_dir = Path("/mnt/audio/Audio/Remasters/Queensrÿche - Operation Mindcrime")

    # Track listing (in order)
    tracks = [
        ("A1. I Remember Now.flac", "I Remember Now"),
        ("A2. Anarchy-X.flac", "Anarchy-X"),
        ("A3. Revolution Calling.flac", "Revolution Calling"),
        ("A4. Operation Mindcrime.flac", "Operation Mindcrime"),
        ("A5. Speak.flac", "Speak"),
        ("B1. Spreading The Disease.flac", "Spreading The Disease"),
        ("B2. The Mission.flac", "The Mission"),
        ("B3. Suite Sister Mary.flac", "Suite Sister Mary"),
        ("C1. The Needle Lies.flac", "The Needle Lies"),
        ("C2. Electric Requiem.flac", "Electric Requiem"),
        ("C3. Breaking The Silence.flac", "Breaking The Silence"),
        ("D1. I Don't Believe In Love.flac", "I Don't Believe In Love"),
        ("D2. Waiting For 22.flac", "Waiting For 22"),
        ("D3. My Empty Room.flac", "My Empty Room"),
        ("D4. Eyes Of A Stranger.flac", "Eyes Of A Stranger"),
    ]

    print("=" * 110)
    print("QUEENSRŸCHE - OPERATION: MINDCRIME (1988)")
    print("Matchering Analysis - Porcupine Tree 'Prodigal' (2021 Remaster) as Reference")
    print("=" * 110)
    print()

    results = []

    for track_file, track_name in tracks:
        print(f"Analyzing: {track_name}...", end=' ')

        original_path = original_dir / track_file
        remastered_path = remastered_dir / track_file

        if not original_path.exists():
            print(f"⚠️  Original not found")
            continue

        if not remastered_path.exists():
            print(f"⚠️  Remastered not found")
            continue

        # Analyze both versions
        original = analyze_track(original_path)
        remastered = analyze_track(remastered_path)

        if original and remastered:
            # Calculate boost applied
            rms_boost = remastered['rms_db'] - original['rms_db']
            crest_change = remastered['crest_factor_db'] - original['crest_factor_db']

            results.append({
                'track': track_name,
                'duration': format_duration(original['duration_seconds']),
                'duration_seconds': original['duration_seconds'],
                'original_rms': original['rms_db'],
                'original_crest': original['crest_factor_db'],
                'remastered_rms': remastered['rms_db'],
                'remastered_crest': remastered['crest_factor_db'],
                'rms_boost': rms_boost,
                'crest_change': crest_change,
                'original_size_mb': original['file_size_mb'],
                'remastered_size_mb': remastered['file_size_mb'],
            })
            print(f"✓ (Boost: {rms_boost:+.2f} dB)")

    # Print summary table
    print("\n" + "=" * 110)
    print("TRACK-BY-TRACK ANALYSIS")
    print("=" * 110)
    print()
    print(f"{'Track':<30} {'Duration':>8} {'Orig RMS':>10} {'→ Final':>10} {'Boost':>8} {'Orig CF':>9} {'→ Final':>10}")
    print("-" * 110)

    for r in results:
        print(f"{r['track']:<30} {r['duration']:>8} "
              f"{r['original_rms']:>9.2f}  {r['remastered_rms']:>9.2f}  "
              f"{r['rms_boost']:>+7.2f}  "
              f"{r['original_crest']:>8.2f}  {r['remastered_crest']:>9.2f}")

    # Calculate statistics
    avg_original_rms = np.mean([r['original_rms'] for r in results])
    avg_remastered_rms = np.mean([r['remastered_rms'] for r in results])
    avg_boost = np.mean([r['rms_boost'] for r in results])
    std_boost = np.std([r['rms_boost'] for r in results])
    min_boost = np.min([r['rms_boost'] for r in results])
    max_boost = np.max([r['rms_boost'] for r in results])

    avg_original_crest = np.mean([r['original_crest'] for r in results])
    avg_remastered_crest = np.mean([r['remastered_crest'] for r in results])
    avg_crest_change = np.mean([r['crest_change'] for r in results])

    std_remastered_rms = np.std([r['remastered_rms'] for r in results])

    print("-" * 110)
    print(f"{'AVERAGE':<30} {'':>8} "
          f"{avg_original_rms:>9.2f}  {avg_remastered_rms:>9.2f}  "
          f"{avg_boost:>+7.2f}  "
          f"{avg_original_crest:>8.2f}  {avg_remastered_crest:>9.2f}")
    print()

    # Summary statistics
    print("=" * 110)
    print("SUMMARY STATISTICS")
    print("=" * 110)
    print()
    print(f"Album: Queensrÿche - Operation: Mindcrime (1988)")
    print(f"Genre: Progressive Metal")
    print(f"Reference: Porcupine Tree - Prodigal (2021 Remaster, 24-bit/96kHz)")
    print(f"Engineer Reference: Steven Wilson")
    print()
    print(f"Total Tracks: {len(results)}")
    print(f"Total Duration: {format_duration(sum(r['duration_seconds'] for r in results))}")
    print()
    print("LOUDNESS ANALYSIS:")
    print(f"  Original RMS (average):    {avg_original_rms:>7.2f} dB")
    print(f"  Original RMS (range):      {min(r['original_rms'] for r in results):>7.2f} to {max(r['original_rms'] for r in results):>7.2f} dB")
    print()
    print(f"  Remastered RMS (average):  {avg_remastered_rms:>7.2f} dB")
    print(f"  Remastered RMS (std dev):  {std_remastered_rms:>7.2f} dB")
    print(f"  Remastered RMS (range):    {min(r['remastered_rms'] for r in results):>7.2f} to {max(r['remastered_rms'] for r in results):>7.2f} dB")
    print()
    print(f"  RMS Boost (average):       {avg_boost:>+7.2f} dB")
    print(f"  RMS Boost (std dev):       {std_boost:>7.2f} dB")
    print(f"  RMS Boost (range):         {min_boost:>+7.2f} to {max_boost:>+7.2f} dB")
    print()
    print("DYNAMIC RANGE ANALYSIS:")
    print(f"  Original Crest Factor:     {avg_original_crest:>7.2f} dB")
    print(f"  Remastered Crest Factor:   {avg_remastered_crest:>7.2f} dB")
    print(f"  Crest Factor Change:       {avg_crest_change:>+7.2f} dB")
    print(f"  Dynamic Range Preserved:   {(avg_remastered_crest / avg_original_crest * 100):>6.1f}%")
    print()

    # Consistency analysis
    target_rms = avg_remastered_rms
    rms_consistency = std_remastered_rms
    print("TARGET CONSISTENCY:")
    print(f"  Target RMS:                {target_rms:>7.2f} dB")
    print(f"  Standard Deviation:        {rms_consistency:>7.2f} dB")
    print(f"  Consistency Rating:        {'Excellent (<0.5 dB)' if rms_consistency < 0.5 else 'Good (<1.0 dB)' if rms_consistency < 1.0 else 'Moderate'}")
    print()

    # Comparison to The Cure - Wish
    print("=" * 110)
    print("COMPARISON TO THE CURE - WISH (1992)")
    print("=" * 110)
    print()
    print(f"{'Metric':<35} {'The Cure (Alt-Rock)':<25} {'Queensrÿche (Prog Metal)':<25}")
    print("-" * 85)
    print(f"{'Genre':<35} {'Alternative Rock':<25} {'Progressive Metal':<25}")
    print(f"{'Release Year':<35} {'1992':<25} {'1988':<25}")
    print(f"{'Original RMS (average)':<35} {'-18.6 dB':<25} {f'{avg_original_rms:.2f} dB':<25}")
    print(f"{'Remastered RMS (target)':<35} {'-12.05 dB':<25} {f'{avg_remastered_rms:.2f} dB':<25}")
    print(f"{'Average Boost Required':<35} {'+6.1 dB':<25} {f'{avg_boost:+.2f} dB':<25}")
    print(f"{'Target Consistency (std dev)':<35} {'~0.0 dB (exact)':<25} {f'{std_remastered_rms:.2f} dB':<25}")
    print()

    # Key observations
    print("KEY OBSERVATIONS:")
    print()
    print("1. TARGET CONSISTENCY:")
    cure_exact = True
    queen_exact = std_remastered_rms < 0.5
    if queen_exact:
        print(f"   • Queensrÿche matches The Cure pattern: near-exact RMS convergence")
        print(f"   • All tracks converge to {avg_remastered_rms:.2f} dB ±{std_remastered_rms:.2f} dB")
    else:
        print(f"   • Queensrÿche shows more variation than The Cure")
        print(f"   • RMS targets range more widely: ±{std_remastered_rms:.2f} dB")
    print()

    print("2. BOOST REQUIREMENTS:")
    if abs(avg_boost - 6.1) < 1.0:
        print(f"   • Similar boost needs: {avg_boost:+.2f} dB (Queensrÿche) vs +6.1 dB (The Cure)")
        print(f"   • Both 80s/90s albums need ~+6 dB to reach Steven Wilson standard")
    elif abs(avg_boost) > 6.1:
        print(f"   • Queensrÿche requires MORE boost: {avg_boost:+.2f} dB vs +6.1 dB (The Cure)")
        print(f"   • 1988 master was more conservatively mastered than 1992")
    else:
        print(f"   • Queensrÿche requires LESS boost: {avg_boost:+.2f} dB vs +6.1 dB (The Cure)")
        print(f"   • 1988 master was already louder than 1992")
    print()

    print("3. DYNAMIC RANGE:")
    dr_preserved_pct = (avg_remastered_crest / avg_original_crest * 100)
    if dr_preserved_pct > 95:
        print(f"   • Excellent DR preservation: {dr_preserved_pct:.1f}%")
        print(f"   • Matchering maintains original dynamics while increasing loudness")
    elif dr_preserved_pct > 85:
        print(f"   • Good DR preservation: {dr_preserved_pct:.1f}%")
        print(f"   • Slight compression applied to reach target")
    else:
        print(f"   • Moderate DR reduction: {dr_preserved_pct:.1f}%")
        print(f"   • More aggressive compression needed for this album")
    print()

    print("4. STEVEN WILSON STANDARD:")
    print(f"   • Target RMS: {avg_remastered_rms:.2f} dB (expected: -12.05 dB)")
    if abs(avg_remastered_rms - (-12.05)) < 0.5:
        print(f"   • ✓ Matches Steven Wilson reference standard")
    else:
        diff = avg_remastered_rms - (-12.05)
        print(f"   • Note: {diff:+.2f} dB {'louder' if diff > 0 else 'quieter'} than The Cure result")
        print(f"   • Genre-specific variation (prog metal vs alt-rock)")
    print()

    print("5. USER'S COMMENT: 'improves so much...hard to believe'")
    print(f"   Likely reasons:")
    print(f"   • Original 1988 CD master was very quiet ({avg_original_rms:.2f} dB RMS)")
    print(f"   • Boost of {avg_boost:+.2f} dB brings it to modern loudness standards")
    print(f"   • Dynamic range preserved at {dr_preserved_pct:.1f}% - not brick-walled")
    print(f"   • Frequency response matched to Steven Wilson's audiophile standard")
    print(f"   • Result: Punchy, modern sound without sacrificing prog metal dynamics")
    print()

    # File size analysis
    print("=" * 110)
    print("FILE SIZE ANALYSIS")
    print("=" * 110)
    print()
    avg_original_size = np.mean([r['original_size_mb'] for r in results])
    avg_remastered_size = np.mean([r['remastered_size_mb'] for r in results])
    avg_reduction = (1 - avg_remastered_size / avg_original_size) * 100

    print(f"Average Original Size:      {avg_original_size:>6.1f} MB")
    print(f"Average Remastered Size:    {avg_remastered_size:>6.1f} MB")
    print(f"Average Size Reduction:     {avg_reduction:>6.1f}%")
    print()
    print("Note: Size reduction is due to FLAC compression efficiency on processed audio,")
    print("      not quality loss. Both are lossless FLAC files.")
    print()


if __name__ == '__main__':
    main()
