#!/usr/bin/env python3
"""
Analyze Blind Guardian 2018 Remasters
Compare original vs remastered versions to understand professional remastering
"""

import sys
from pathlib import Path
import numpy as np
import soundfile as sf
from typing import Dict, List, Tuple

def analyze_track(file_path: Path) -> Dict:
    """Quick analysis of a single track"""
    try:
        audio, sr = sf.read(str(file_path))

        # Convert to mono
        if len(audio.shape) > 1:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Basic metrics
        rms_linear = np.sqrt(np.mean(audio_mono ** 2))
        rms_db = 20 * np.log10(rms_linear) if rms_linear > 0 else -np.inf

        peak_linear = np.max(np.abs(audio_mono))
        peak_db = 20 * np.log10(peak_linear) if peak_linear > 0 else -np.inf

        crest_factor = peak_db - rms_db

        return {
            'rms_db': rms_db,
            'peak_db': peak_db,
            'crest_factor_db': crest_factor,
            'duration': len(audio_mono) / sr
        }
    except Exception as e:
        print(f"Error analyzing {file_path.name}: {e}")
        return None


def analyze_album(original_dir: Path, remaster_dir: Path) -> Dict:
    """Analyze all matching tracks in an album"""
    print(f"\nAnalyzing: {original_dir.name}")
    print(f"Remaster:  {remaster_dir.name}")
    print()

    # Find all FLAC files in original
    original_tracks = sorted(list(original_dir.glob("*.flac")))

    if not original_tracks:
        print("  No FLAC files found in original directory")
        return None

    results = []

    for orig_path in original_tracks[:5]:  # Analyze first 5 tracks for speed
        # Find matching remaster
        track_name = orig_path.name
        remaster_path = remaster_dir / track_name

        if not remaster_path.exists():
            # Try without track number prefix
            base_name = track_name.split(' ', 1)[-1] if ' ' in track_name else track_name
            remaster_path = list(remaster_dir.glob(f"*{base_name}"))
            if remaster_path:
                remaster_path = remaster_path[0]
            else:
                print(f"  Skipping {track_name} (no remaster match)")
                continue

        print(f"  Analyzing: {track_name[:50]}...")

        # Analyze both versions
        orig = analyze_track(orig_path)
        remaster = analyze_track(remaster_path)

        if orig and remaster:
            rms_change = remaster['rms_db'] - orig['rms_db']
            crest_change = remaster['crest_factor_db'] - orig['crest_factor_db']

            results.append({
                'track': track_name,
                'orig_rms': orig['rms_db'],
                'remaster_rms': remaster['rms_db'],
                'rms_change': rms_change,
                'orig_crest': orig['crest_factor_db'],
                'remaster_crest': remaster['crest_factor_db'],
                'crest_change': crest_change
            })

    return results


def main():
    base_dir = Path("/mnt/Musica/Musica/Blind Guardian")

    # Albums to analyze
    albums = [
        ("1988 - Battalions Of Fear", "1988 - Battalions Of Fear (2018)"),
        ("1989 - Follow The Blind", "1989 - Follow The Blind (2018)"),
        ("1990 - Tales From The Twilight World", "1990 - Tales From The Twilight World (2018)"),
        ("1992 - Somewhere Far Beyond", "1992 - Somewhere Far Beyond (2018)"),
        ("1995 - Imaginations From The Other Side", "1995 - Imaginations From The Other Side (2018)"),
        ("1998 - Nightfall In Middle-Earth", "1998 - Nightfall In Middle-Earth (2018)"),
        ("2002 - A Night At The Opera", "2002 - A Night At The Opera (2018)"),
    ]

    print("=" * 100)
    print("BLIND GUARDIAN 2018 REMASTERS ANALYSIS")
    print("Professional Remastering Study - Original vs Remastered")
    print("=" * 100)

    all_results = {}

    for orig_name, remaster_name in albums:
        orig_dir = base_dir / orig_name
        remaster_dir = base_dir / remaster_name

        if not orig_dir.exists():
            print(f"\nSkipping {orig_name} (not found)")
            continue

        if not remaster_dir.exists():
            print(f"\nSkipping {remaster_name} (not found)")
            continue

        results = analyze_album(orig_dir, remaster_dir)
        if results:
            all_results[orig_name] = results

    # Summary statistics
    print("\n" + "=" * 100)
    print("SUMMARY - PROFESSIONAL REMASTERING PATTERNS")
    print("=" * 100)
    print()

    for album_name, results in all_results.items():
        print(f"\n{album_name}")
        print("-" * 80)

        avg_rms_change = np.mean([r['rms_change'] for r in results])
        avg_crest_change = np.mean([r['crest_change'] for r in results])
        avg_orig_rms = np.mean([r['orig_rms'] for r in results])
        avg_remaster_rms = np.mean([r['remaster_rms'] for r in results])
        avg_orig_crest = np.mean([r['orig_crest'] for r in results])
        avg_remaster_crest = np.mean([r['remaster_crest'] for r in results])

        print(f"Original RMS:      {avg_orig_rms:>7.2f} dB")
        print(f"Remastered RMS:    {avg_remaster_rms:>7.2f} dB")
        print(f"RMS Change:        {avg_rms_change:>+7.2f} dB")
        print()
        print(f"Original Crest:    {avg_orig_crest:>7.2f} dB")
        print(f"Remastered Crest:  {avg_remaster_crest:>7.2f} dB")
        print(f"Crest Change:      {avg_crest_change:>+7.2f} dB")
        print()

        if avg_rms_change > 0:
            print(f"Strategy: LOUDNESS INCREASE (+{avg_rms_change:.1f} dB)")
        else:
            print(f"Strategy: CONSERVATIVE ({avg_rms_change:+.1f} dB)")

        if avg_crest_change > 0:
            print(f"Dynamics: EXPANDED (+{avg_crest_change:.1f} dB crest)")
        elif avg_crest_change > -2:
            print(f"Dynamics: PRESERVED ({avg_crest_change:+.1f} dB crest)")
        else:
            print(f"Dynamics: COMPRESSED ({avg_crest_change:+.1f} dB crest)")

    # Overall statistics
    print("\n" + "=" * 100)
    print("OVERALL REMASTERING TRENDS")
    print("=" * 100)
    print()

    all_rms_changes = []
    all_crest_changes = []
    all_orig_rms = []
    all_remaster_rms = []

    for results in all_results.values():
        all_rms_changes.extend([r['rms_change'] for r in results])
        all_crest_changes.extend([r['crest_change'] for r in results])
        all_orig_rms.extend([r['orig_rms'] for r in results])
        all_remaster_rms.extend([r['remaster_rms'] for r in results])

    print(f"Number of albums analyzed:     {len(all_results)}")
    print(f"Number of tracks analyzed:     {len(all_rms_changes)}")
    print()
    print(f"Average Original RMS:          {np.mean(all_orig_rms):>7.2f} dB")
    print(f"Average Remastered RMS:        {np.mean(all_remaster_rms):>7.2f} dB")
    print(f"Average RMS Change:            {np.mean(all_rms_changes):>+7.2f} dB")
    print(f"RMS Change Range:              {np.min(all_rms_changes):>+7.2f} to {np.max(all_rms_changes):>+7.2f} dB")
    print()
    print(f"Average Crest Factor Change:   {np.mean(all_crest_changes):>+7.2f} dB")
    print(f"Crest Change Range:            {np.min(all_crest_changes):>+7.2f} to {np.max(all_crest_changes):>+7.2f} dB")
    print()

    # Interpret results
    avg_rms_change = np.mean(all_rms_changes)
    avg_crest_change = np.mean(all_crest_changes)

    print("INTERPRETATION:")
    print()

    if avg_rms_change > 2:
        print(f"✓ Significant loudness increase: +{avg_rms_change:.1f} dB")
        print(f"  These remasters made the albums LOUDER")
    elif avg_rms_change > 0.5:
        print(f"✓ Moderate loudness increase: +{avg_rms_change:.1f} dB")
        print(f"  These remasters gently increased loudness")
    else:
        print(f"✓ Conservative approach: {avg_rms_change:+.1f} dB")
        print(f"  These remasters did NOT focus on loudness")

    print()

    if avg_crest_change > 1:
        print(f"✓ Dynamic range EXPANDED: +{avg_crest_change:.1f} dB crest factor")
        print(f"  Remasters increased punch and transients")
    elif avg_crest_change > -1:
        print(f"✓ Dynamic range PRESERVED: {avg_crest_change:+.1f} dB crest factor")
        print(f"  Remasters maintained original dynamics")
    else:
        print(f"⚠ Dynamic range COMPRESSED: {avg_crest_change:+.1f} dB crest factor")
        print(f"  Remasters reduced dynamic range (loudness war)")

    print()
    print("CONCLUSION:")
    print()

    if avg_rms_change > 2 and avg_crest_change < -1:
        print("These remasters follow the 'loudness war' approach:")
        print("  - Increased RMS significantly")
        print("  - Compressed dynamic range")
        print("  - Typical of 2000s-2010s remasters")
    elif avg_rms_change > 0 and avg_crest_change > -1:
        print("These remasters follow a BALANCED approach:")
        print("  - Moderate loudness increase")
        print("  - Preserved or enhanced dynamics")
        print("  - Modern audiophile remastering")
    elif avg_crest_change > 0:
        print("These remasters follow the DYNAMIC ENHANCEMENT approach:")
        print("  - Conservative loudness")
        print("  - Expanded dynamic range")
        print("  - Similar to Steven Wilson / Matchering strategy")
    else:
        print("These remasters have MIXED results")

    print()
    print("=" * 100)


if __name__ == '__main__':
    main()
