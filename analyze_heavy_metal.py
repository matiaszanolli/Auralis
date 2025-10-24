#!/usr/bin/env python3
"""
Analyze Matchering processing on heavy metal/industrial tracks.
Compares original tracks with their remastered versions.
"""

import numpy as np
from pathlib import Path
from auralis.io.unified_loader import load_audio
from auralis.dsp.utils import calculate_loudness_units
from auralis.dsp.basic import rms

def analyze_audio(file_path):
    """Analyze audio file and return metrics."""
    try:
        audio, sr = load_audio(str(file_path))

        # Convert to mono for analysis
        if audio.ndim == 2:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # Calculate metrics
        peak = np.max(np.abs(audio_mono))
        peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf

        rms_val = rms(audio_mono)
        rms_db = 20 * np.log10(rms_val) if rms_val > 0 else -np.inf

        crest_factor = peak_db - rms_db

        # LUFS measurement
        lufs = calculate_loudness_units(audio, sr)

        # Clipping detection
        clipping_samples = np.sum(np.abs(audio_mono) >= 0.99)

        return {
            'peak': peak,
            'peak_db': peak_db,
            'rms': rms_val,
            'rms_db': rms_db,
            'crest_factor': crest_factor,
            'lufs': lufs,
            'clipping_samples': clipping_samples,
        }
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return None

def find_original_track(remastered_path):
    """Find the original track corresponding to a remastered version."""
    # Extract album and track name from remastered path
    album_name = remastered_path.parent.name
    track_name = remastered_path.stem

    # Define search paths for each album
    search_paths = {
        "Slayer - South Of Heaven": [
            "/mnt/Musica/Musica/VA - 100 Greatest Thrash Metal Songs (2010)",
        ],
        "Testament - Live In London": [
            "/mnt/Musica/Musica/Testament",
        ],
        "Static-X - Wisconsin Death Trip": [
            "/mnt/Musica/Musica/Static-X/Wisconsin Death Trip",
        ],
    }

    # Get search paths for this album
    paths_to_search = search_paths.get(album_name, [])

    # Search for matching track
    for search_path in paths_to_search:
        search_dir = Path(search_path)
        if not search_dir.exists():
            continue

        # Look for files with similar names
        for original_file in search_dir.rglob("*"):
            if not original_file.is_file():
                continue
            if original_file.suffix.lower() not in ['.mp3', '.flac', '.wav']:
                continue

            # Check if track name matches (case insensitive, fuzzy)
            original_name = original_file.stem.lower()
            remastered_name = track_name.lower()

            # Remove track numbers and common prefixes
            original_clean = original_name.replace('_', ' ').replace('-', ' ')
            remastered_clean = remastered_name.replace('_', ' ').replace('-', ' ')

            # Remove leading numbers
            import re
            original_clean = re.sub(r'^\d+\.?\s*', '', original_clean)
            remastered_clean = re.sub(r'^\d+\.?\s*', '', remastered_clean)

            if remastered_clean in original_clean or original_clean in remastered_clean:
                return original_file

    return None

def analyze_album(album_name, remastered_dir, max_tracks=3):
    """Analyze original vs remastered tracks for an album."""
    print(f"\n{'='*80}")
    print(f"Album: {album_name}")
    print(f"{'='*80}\n")

    remastered_path = Path(remastered_dir)
    if not remastered_path.exists():
        print(f"❌ Remastered directory not found: {remastered_dir}")
        return []

    # Get remastered tracks
    remastered_tracks = sorted(list(remastered_path.glob("*.flac")) + list(remastered_path.glob("*.wav")))

    if not remastered_tracks:
        print(f"❌ No remastered tracks found in {remastered_dir}")
        return []

    results = []
    tracks_analyzed = 0

    for remastered_file in remastered_tracks:
        if tracks_analyzed >= max_tracks:
            break

        # Find corresponding original track
        original_file = find_original_track(remastered_file)

        if not original_file:
            print(f"⚠️  Could not find original for: {remastered_file.name}")
            continue

        print(f"Track: {remastered_file.stem}")
        print(f"Original: {original_file}")
        print(f"Remastered: {remastered_file}")
        print()

        # Analyze both
        original_metrics = analyze_audio(original_file)
        remastered_metrics = analyze_audio(remastered_file)

        if not original_metrics or not remastered_metrics:
            continue

        # Print results
        print("ORIGINAL:")
        print(f"  Peak:         {original_metrics['peak_db']:6.2f} dB")
        print(f"  RMS:          {original_metrics['rms_db']:6.2f} dB")
        print(f"  Crest Factor: {original_metrics['crest_factor']:6.2f} dB")
        print(f"  LUFS:         {original_metrics['lufs']:6.2f}")
        if original_metrics['clipping_samples'] > 0:
            print(f"  ⚠️  Clipping:   {original_metrics['clipping_samples']} samples")
        print()

        print("MATCHERING REMASTERED:")
        print(f"  Peak:         {remastered_metrics['peak_db']:6.2f} dB")
        print(f"  RMS:          {remastered_metrics['rms_db']:6.2f} dB")
        print(f"  Crest Factor: {remastered_metrics['crest_factor']:6.2f} dB")
        print(f"  LUFS:         {remastered_metrics['lufs']:6.2f}")
        if remastered_metrics['clipping_samples'] > 0:
            print(f"  ⚠️  Clipping:   {remastered_metrics['clipping_samples']} samples")
        print()

        # Calculate changes
        peak_change = remastered_metrics['peak_db'] - original_metrics['peak_db']
        rms_change = remastered_metrics['rms_db'] - original_metrics['rms_db']
        crest_change = remastered_metrics['crest_factor'] - original_metrics['crest_factor']
        lufs_change = remastered_metrics['lufs'] - original_metrics['lufs']

        print("CHANGES (Remastered - Original):")
        print(f"  Peak Δ:       {peak_change:+6.2f} dB")
        print(f"  RMS Δ:        {rms_change:+6.2f} dB")
        print(f"  Crest Δ:      {crest_change:+6.2f} dB")
        print(f"  LUFS Δ:       {lufs_change:+6.2f} dB")
        print()

        results.append({
            'album': album_name,
            'track': remastered_file.stem,
            'original': original_metrics,
            'remastered': remastered_metrics,
            'peak_change': peak_change,
            'rms_change': rms_change,
            'crest_change': crest_change,
            'lufs_change': lufs_change,
        })

        tracks_analyzed += 1

    return results

def main():
    print("="*80)
    print("HEAVY METAL/INDUSTRIAL MATCHERING ANALYSIS")
    print("="*80)

    # Define albums to analyze
    albums = [
        ("Slayer - South Of Heaven", "/mnt/audio/Audio/Remasters/Slayer - South Of Heaven"),
        ("Testament - Live In London", "/mnt/audio/Audio/Remasters/Testament - Live In London"),
        ("Static-X - Wisconsin Death Trip", "/mnt/audio/Audio/Remasters/Static-X - Wisconsin Death Trip"),
    ]

    all_results = []

    for album_name, remastered_dir in albums:
        results = analyze_album(album_name, remastered_dir, max_tracks=3)
        all_results.extend(results)

    # Summary statistics
    if all_results:
        print("\n" + "="*80)
        print("SUMMARY - Heavy Music Matchering Behavior")
        print("="*80)
        print()

        avg_peak_change = np.mean([r['peak_change'] for r in all_results])
        avg_rms_change = np.mean([r['rms_change'] for r in all_results])
        avg_crest_change = np.mean([r['crest_change'] for r in all_results])
        avg_lufs_change = np.mean([r['lufs_change'] for r in all_results])

        print(f"Average Changes ({len(all_results)} tracks analyzed):")
        print(f"  Peak Change:      {avg_peak_change:+6.2f} dB")
        print(f"  RMS Change:       {avg_rms_change:+6.2f} dB")
        print(f"  Crest Factor Δ:   {avg_crest_change:+6.2f} dB")
        print(f"  LUFS Δ:           {avg_lufs_change:+6.2f} dB")
        print()

        avg_final_peak = np.mean([r['remastered']['peak_db'] for r in all_results])
        avg_final_rms = np.mean([r['remastered']['rms_db'] for r in all_results])
        avg_final_crest = np.mean([r['remastered']['crest_factor'] for r in all_results])
        avg_final_lufs = np.mean([r['remastered']['lufs'] for r in all_results])

        print("Typical Final Values:")
        print(f"  Final Peak:       {avg_final_peak:6.2f} dB")
        print(f"  Final RMS:        {avg_final_rms:6.2f} dB")
        print(f"  Final Crest:      {avg_final_crest:6.2f} dB")
        print(f"  Final LUFS:       {avg_final_lufs:6.2f}")
        print()

        print("="*80)
        print("PRESET RECOMMENDATIONS FOR HEAVY MUSIC:")
        print("="*80)
        print(f"✓ Target peak level: {avg_final_peak:.1f} dB")
        print(f"✓ Target RMS: {avg_final_rms:.1f} dB")
        print(f"✓ Target crest factor: {avg_final_crest:.1f} dB")
        print(f"✓ Expected RMS change: {avg_rms_change:+.1f} dB")
        print(f"✓ Expected crest change: {avg_crest_change:+.1f} dB")
        print()

        # Genre-specific insights
        print("Genre-Specific Insights:")
        for album_name in set([r['album'] for r in all_results]):
            album_results = [r for r in all_results if r['album'] == album_name]
            if len(album_results) > 0:
                album_avg_crest = np.mean([r['crest_change'] for r in album_results])
                album_avg_rms = np.mean([r['rms_change'] for r in album_results])
                print(f"  {album_name}:")
                print(f"    RMS Δ: {album_avg_rms:+.2f} dB, Crest Δ: {album_avg_crest:+.2f} dB")

if __name__ == "__main__":
    main()
