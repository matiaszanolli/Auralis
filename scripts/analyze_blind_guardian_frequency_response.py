#!/usr/bin/env python3
"""
Analyze Blind Guardian Frequency Response Changes
Compare original vs remastered spectral balance to understand professional EQ decisions
"""

import sys
from pathlib import Path
import numpy as np
import soundfile as sf
from typing import Dict, List
import json

def analyze_frequency_response(audio: np.ndarray, sr: int) -> Dict:
    """Analyze frequency response of audio"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # FFT
    fft = np.fft.rfft(audio_mono)
    freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)
    magnitude = np.abs(fft)

    # Define frequency bands
    bass_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 4000)
    high_mask = (freqs >= 4000) & (freqs <= 20000)

    # Calculate energy
    bass_energy = np.sum(magnitude[bass_mask] ** 2)
    mid_energy = np.sum(magnitude[mid_mask] ** 2)
    high_energy = np.sum(magnitude[high_mask] ** 2)
    total_energy = bass_energy + mid_energy + high_energy

    # Percentages
    bass_pct = (bass_energy / total_energy * 100) if total_energy > 0 else 0
    mid_pct = (mid_energy / total_energy * 100) if total_energy > 0 else 0
    high_pct = (high_energy / total_energy * 100) if total_energy > 0 else 0

    # dB levels
    bass_db = 10 * np.log10(bass_energy) if bass_energy > 0 else -np.inf
    mid_db = 10 * np.log10(mid_energy) if mid_energy > 0 else -np.inf
    high_db = 10 * np.log10(high_energy) if high_energy > 0 else -np.inf

    # Ratios
    bass_to_mid = bass_db - mid_db
    high_to_mid = high_db - mid_db

    # Spectral metrics
    centroid = np.sum(freqs * magnitude) / np.sum(magnitude) if np.sum(magnitude) > 0 else 0

    cumsum = np.cumsum(magnitude ** 2)
    rolloff_threshold = 0.85 * cumsum[-1]
    rolloff_idx = np.where(cumsum >= rolloff_threshold)[0]
    rolloff = freqs[rolloff_idx[0]] if len(rolloff_idx) > 0 else 0

    return {
        'bass_pct': bass_pct,
        'mid_pct': mid_pct,
        'high_pct': high_pct,
        'bass_to_mid_db': bass_to_mid,
        'high_to_mid_db': high_to_mid,
        'centroid_hz': centroid,
        'rolloff_hz': rolloff
    }

def calculate_third_octave_simple(audio: np.ndarray, sr: int) -> Dict:
    """Calculate simplified 1/3 octave bands"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # Key center frequencies
    center_freqs = [
        31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000
    ]

    fft = np.fft.rfft(audio_mono)
    freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)
    magnitude = np.abs(fft)

    third_octave = {}
    for fc in center_freqs:
        f_lower = fc / (2 ** (1/6))
        f_upper = fc * (2 ** (1/6))
        mask = (freqs >= f_lower) & (freqs < f_upper)
        band_energy = np.sum(magnitude[mask] ** 2)
        band_level = 10 * np.log10(band_energy) if band_energy > 0 else -np.inf
        third_octave[fc] = band_level

    return third_octave

def analyze_track_pair(orig_path: Path, remaster_path: Path) -> Dict:
    """Analyze original vs remaster frequency response"""
    try:
        # Load both versions
        orig_audio, orig_sr = sf.read(str(orig_path))
        remaster_audio, remaster_sr = sf.read(str(remaster_path))

        # Analyze frequency response
        orig_freq = analyze_frequency_response(orig_audio, orig_sr)
        remaster_freq = analyze_frequency_response(remaster_audio, remaster_sr)

        # Calculate changes
        bass_change = remaster_freq['bass_pct'] - orig_freq['bass_pct']
        mid_change = remaster_freq['mid_pct'] - orig_freq['mid_pct']
        high_change = remaster_freq['high_pct'] - orig_freq['high_pct']

        bass_to_mid_change = remaster_freq['bass_to_mid_db'] - orig_freq['bass_to_mid_db']
        high_to_mid_change = remaster_freq['high_to_mid_db'] - orig_freq['high_to_mid_db']

        # Third octave
        orig_third = calculate_third_octave_simple(orig_audio, orig_sr)
        remaster_third = calculate_third_octave_simple(remaster_audio, remaster_sr)

        third_octave_changes = {}
        for fc in orig_third.keys():
            third_octave_changes[fc] = remaster_third[fc] - orig_third[fc]

        return {
            'track': orig_path.name,
            'original': orig_freq,
            'remaster': remaster_freq,
            'changes': {
                'bass_pct': bass_change,
                'mid_pct': mid_change,
                'high_pct': high_change,
                'bass_to_mid_db': bass_to_mid_change,
                'high_to_mid_db': high_to_mid_change
            },
            'third_octave_changes': third_octave_changes
        }
    except Exception as e:
        print(f"Error analyzing {orig_path.name}: {e}")
        return None

def main():
    base_dir = Path("/mnt/Musica/Musica/Blind Guardian")

    albums = [
        ("1988 - Battalions Of Fear", "1988 - Battalions Of Fear (2018)", "early"),
        ("1989 - Follow The Blind", "1989 - Follow The Blind (2018)", "early"),
        ("1990 - Tales From The Twilight World", "1990 - Tales From The Twilight World (2018)", "early"),
        ("1992 - Somewhere Far Beyond", "1992 - Somewhere Far Beyond (2018)", "transition"),
        ("1995 - Imaginations From The Other Side", "1995 - Imaginations From The Other Side (2018)", "well_mastered"),
        ("1998 - Nightfall In Middle-Earth", "1998 - Nightfall In Middle-Earth (2018)", "early"),
        ("2002 - A Night At The Opera", "2002 - A Night At The Opera (2018)", "well_mastered"),
    ]

    print("=" * 100)
    print("BLIND GUARDIAN - FREQUENCY RESPONSE ANALYSIS")
    print("Understanding Professional EQ Decisions in 2018 Remasters")
    print("=" * 100)
    print()

    all_results = {}

    for orig_name, remaster_name, category in albums:
        print(f"\nAnalyzing: {orig_name}")

        orig_dir = base_dir / orig_name
        remaster_dir = base_dir / remaster_name

        if not orig_dir.exists() or not remaster_dir.exists():
            print("  Directory not found, skipping")
            continue

        # Analyze first 3 tracks
        orig_tracks = sorted(list(orig_dir.glob("*.flac")))[:3]

        album_results = []
        for orig_path in orig_tracks:
            # Find matching remaster
            remaster_path = remaster_dir / orig_path.name
            if not remaster_path.exists():
                base_name = orig_path.name.split(' ', 1)[-1] if ' ' in orig_path.name else orig_path.name
                remaster_matches = list(remaster_dir.glob(f"*{base_name}"))
                if remaster_matches:
                    remaster_path = remaster_matches[0]
                else:
                    continue

            print(f"  {orig_path.name[:60]}")
            result = analyze_track_pair(orig_path, remaster_path)
            if result:
                album_results.append(result)

        if album_results:
            all_results[orig_name] = {'category': category, 'results': album_results}

    # Calculate averages per category
    print("\n" + "=" * 100)
    print("FREQUENCY RESPONSE CHANGES BY CATEGORY")
    print("=" * 100)

    categories = {
        'early': [],
        'transition': [],
        'well_mastered': []
    }

    for album_name, data in all_results.items():
        category = data['category']
        categories[category].extend(data['results'])

    # Analyze each category
    for category_name, results in categories.items():
        if not results:
            continue

        print(f"\n{'=' * 100}")
        print(f"{category_name.upper().replace('_', ' ')} ALBUMS")
        print('=' * 100)

        # Average changes
        avg_bass_change = np.mean([r['changes']['bass_pct'] for r in results])
        avg_mid_change = np.mean([r['changes']['mid_pct'] for r in results])
        avg_high_change = np.mean([r['changes']['high_pct'] for r in results])
        avg_bass_to_mid_change = np.mean([r['changes']['bass_to_mid_db'] for r in results])
        avg_high_to_mid_change = np.mean([r['changes']['high_to_mid_db'] for r in results])

        # Original averages
        avg_orig_bass = np.mean([r['original']['bass_pct'] for r in results])
        avg_orig_mid = np.mean([r['original']['mid_pct'] for r in results])
        avg_orig_high = np.mean([r['original']['high_pct'] for r in results])
        avg_orig_bass_to_mid = np.mean([r['original']['bass_to_mid_db'] for r in results])
        avg_orig_high_to_mid = np.mean([r['original']['high_to_mid_db'] for r in results])

        # Remaster averages
        avg_rem_bass = np.mean([r['remaster']['bass_pct'] for r in results])
        avg_rem_mid = np.mean([r['remaster']['mid_pct'] for r in results])
        avg_rem_high = np.mean([r['remaster']['high_pct'] for r in results])
        avg_rem_bass_to_mid = np.mean([r['remaster']['bass_to_mid_db'] for r in results])
        avg_rem_high_to_mid = np.mean([r['remaster']['high_to_mid_db'] for r in results])

        print(f"\nTracks analyzed: {len(results)}")
        print()
        print("FREQUENCY BALANCE:")
        print(f"  Bass (20-250 Hz):")
        print(f"    Original:    {avg_orig_bass:>6.1f}%")
        print(f"    Remastered:  {avg_rem_bass:>6.1f}%")
        print(f"    Change:      {avg_bass_change:>+6.1f}%")
        print()
        print(f"  Mid (250-4k Hz):")
        print(f"    Original:    {avg_orig_mid:>6.1f}%")
        print(f"    Remastered:  {avg_rem_mid:>6.1f}%")
        print(f"    Change:      {avg_mid_change:>+6.1f}%")
        print()
        print(f"  High (4k-20k Hz):")
        print(f"    Original:    {avg_orig_high:>6.1f}%")
        print(f"    Remastered:  {avg_rem_high:>6.1f}%")
        print(f"    Change:      {avg_high_change:>+6.1f}%")
        print()
        print("FREQUENCY RATIOS:")
        print(f"  Bass-to-Mid:")
        print(f"    Original:    {avg_orig_bass_to_mid:>+6.1f} dB")
        print(f"    Remastered:  {avg_rem_bass_to_mid:>+6.1f} dB")
        print(f"    Change:      {avg_bass_to_mid_change:>+6.1f} dB")
        print()
        print(f"  High-to-Mid:")
        print(f"    Original:    {avg_orig_high_to_mid:>+6.1f} dB")
        print(f"    Remastered:  {avg_rem_high_to_mid:>+6.1f} dB")
        print(f"    Change:      {avg_high_to_mid_change:>+6.1f} dB")
        print()

        # Third octave averages
        print("1/3 OCTAVE CHANGES:")
        all_third_octave = {}
        for r in results:
            for fc, change in r['third_octave_changes'].items():
                if fc not in all_third_octave:
                    all_third_octave[fc] = []
                all_third_octave[fc].append(change)

        for fc in sorted(all_third_octave.keys()):
            avg_change = np.mean(all_third_octave[fc])
            print(f"  {fc:>6.0f} Hz: {avg_change:>+6.2f} dB")

        print()

    # Save power metal profile
    print("\n" + "=" * 100)
    print("CREATING POWER METAL FREQUENCY PROFILE")
    print("=" * 100)
    print()

    # Use well-mastered albums as reference (2018 remaster targets)
    well_mastered = categories['well_mastered']

    if well_mastered:
        profile = {
            'genre': 'Power Metal',
            'source': 'Blind Guardian 2018 Remasters (1995, 2002 albums)',
            'tracks_analyzed': len(well_mastered),
            'frequency_balance': {
                'bass_pct': float(np.mean([r['remaster']['bass_pct'] for r in well_mastered])),
                'mid_pct': float(np.mean([r['remaster']['mid_pct'] for r in well_mastered])),
                'high_pct': float(np.mean([r['remaster']['high_pct'] for r in well_mastered])),
                'bass_to_mid_db': float(np.mean([r['remaster']['bass_to_mid_db'] for r in well_mastered])),
                'high_to_mid_db': float(np.mean([r['remaster']['high_to_mid_db'] for r in well_mastered])),
            },
            'spectral_characteristics': {
                'centroid_hz': float(np.mean([r['remaster']['centroid_hz'] for r in well_mastered])),
                'rolloff_hz': float(np.mean([r['remaster']['rolloff_hz'] for r in well_mastered])),
            }
        }

        output_path = Path("profiles/power_metal_blind_guardian_2018.json")
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(profile, f, indent=2)

        print(f"Power Metal profile saved to: {output_path}")
        print()
        print("Profile characteristics:")
        print(f"  Bass:        {profile['frequency_balance']['bass_pct']:.1f}%")
        print(f"  Mid:         {profile['frequency_balance']['mid_pct']:.1f}%")
        print(f"  High:        {profile['frequency_balance']['high_pct']:.1f}%")
        print(f"  Bass/Mid:    {profile['frequency_balance']['bass_to_mid_db']:+.1f} dB")
        print(f"  High/Mid:    {profile['frequency_balance']['high_to_mid_db']:+.1f} dB")
        print()

    print("=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)


if __name__ == '__main__':
    main()
