#!/usr/bin/env python3
"""
Analyze Queensrÿche Operation: Mindcrime
Compare original vs Matchering remastered versions
Extract processing statistics for validation framework
"""

import sys
import os
from pathlib import Path
import numpy as np
import soundfile as sf
from typing import Dict, Tuple

# Add auralis to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.loudness_meter import LoudnessMeter
from auralis.analysis.dynamic_range import DynamicRangeAnalyzer


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

        # Calculate crest factor
        crest_factor = peak_db - rms_db

        # Calculate LUFS using loudness meter
        loudness_meter = LoudnessMeter()
        lufs_data = loudness_meter.measure(audio, sr)
        integrated_lufs = lufs_data['integrated_lufs']

        # Calculate dynamic range
        dr_analyzer = DynamicRangeAnalyzer(sr)
        dr_data = dr_analyzer.analyze_dynamic_range(audio)
        dynamic_range = dr_data['crest_factor']  # Use crest factor as DR metric

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
            'integrated_lufs': integrated_lufs,
            'dynamic_range_db': dynamic_range,
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
        "A1. I Remember Now.flac",
        "A2. Anarchy-X.flac",
        "A3. Revolution Calling.flac",
        "A4. Operation Mindcrime.flac",
        "A5. Speak.flac",
        "B1. Spreading The Disease.flac",
        "B2. The Mission.flac",
        "B3. Suite Sister Mary.flac",
        "C1. The Needle Lies.flac",
        "C2. Electric Requiem.flac",
        "C3. Breaking The Silence.flac",
        "D1. I Don't Believe In Love.flac",
        "D2. Waiting For 22.flac",
        "D3. My Empty Room.flac",
        "D4. Eyes Of A Stranger.flac",
    ]

    print("=" * 100)
    print("QUEENSRŸCHE - OPERATION: MINDCRIME (1988)")
    print("Matchering Analysis - Porcupine Tree 'Prodigal' (2021 Remaster) as Reference")
    print("=" * 100)
    print()

    results = []

    for track in tracks:
        print(f"Analyzing: {track}...")

        original_path = original_dir / track
        remastered_path = remastered_dir / track

        if not original_path.exists():
            print(f"  ⚠️  Original not found: {original_path}")
            continue

        if not remastered_path.exists():
            print(f"  ⚠️  Remastered not found: {remastered_path}")
            continue

        # Analyze both versions
        original = analyze_track(original_path)
        remastered = analyze_track(remastered_path)

        if original and remastered:
            # Calculate boost applied
            rms_boost = remastered['rms_db'] - original['rms_db']
            lufs_boost = remastered['integrated_lufs'] - original['integrated_lufs']
            dr_change = remastered['dynamic_range_db'] - original['dynamic_range_db']

            results.append({
                'track': track.replace('.flac', ''),
                'duration': format_duration(original['duration_seconds']),
                'original_rms': original['rms_db'],
                'original_lufs': original['integrated_lufs'],
                'original_dr': original['dynamic_range_db'],
                'remastered_rms': remastered['rms_db'],
                'remastered_lufs': remastered['integrated_lufs'],
                'remastered_dr': remastered['dynamic_range_db'],
                'rms_boost': rms_boost,
                'lufs_boost': lufs_boost,
                'dr_change': dr_change,
                'file_size_reduction': (1 - remastered['file_size_mb'] / original['file_size_mb']) * 100,
            })

    # Print summary table
    print("\n" + "=" * 100)
    print("TRACK-BY-TRACK ANALYSIS")
    print("=" * 100)
    print()
    print(f"{'Track':<35} {'Duration':>8} {'Orig RMS':>10} {'Final RMS':>10} {'Boost':>8} {'Orig LUFS':>11} {'Final LUFS':>11}")
    print("-" * 100)

    for r in results:
        print(f"{r['track']:<35} {r['duration']:>8} "
              f"{r['original_rms']:>9.2f}  {r['remastered_rms']:>9.2f}  "
              f"{r['rms_boost']:>+7.2f}  "
              f"{r['original_lufs']:>10.2f}  {r['remastered_lufs']:>10.2f}")

    # Calculate averages
    avg_original_rms = np.mean([r['original_rms'] for r in results])
    avg_remastered_rms = np.mean([r['remastered_rms'] for r in results])
    avg_boost = np.mean([r['rms_boost'] for r in results])
    avg_original_lufs = np.mean([r['original_lufs'] for r in results])
    avg_remastered_lufs = np.mean([r['remastered_lufs'] for r in results])
    avg_lufs_boost = np.mean([r['lufs_boost'] for r in results])
    avg_original_dr = np.mean([r['original_dr'] for r in results])
    avg_remastered_dr = np.mean([r['remastered_dr'] for r in results])
    avg_dr_change = np.mean([r['dr_change'] for r in results])

    print("-" * 100)
    print(f"{'AVERAGE':<35} {'':>8} "
          f"{avg_original_rms:>9.2f}  {avg_remastered_rms:>9.2f}  "
          f"{avg_boost:>+7.2f}  "
          f"{avg_original_lufs:>10.2f}  {avg_remastered_lufs:>10.2f}")
    print()

    # Dynamic range comparison
    print("=" * 100)
    print("DYNAMIC RANGE ANALYSIS")
    print("=" * 100)
    print()
    print(f"{'Track':<35} {'Original DR':>12} {'Remastered DR':>15} {'Change':>10}")
    print("-" * 100)

    for r in results:
        print(f"{r['track']:<35} {r['original_dr']:>11.2f}  {r['remastered_dr']:>14.2f}  {r['dr_change']:>+9.2f}")

    print("-" * 100)
    print(f"{'AVERAGE':<35} {avg_original_dr:>11.2f}  {avg_remastered_dr:>14.2f}  {avg_dr_change:>+9.2f}")
    print()

    # Summary statistics
    print("=" * 100)
    print("SUMMARY STATISTICS")
    print("=" * 100)
    print()
    print(f"Album: Queensrÿche - Operation: Mindcrime (1988)")
    print(f"Reference: Porcupine Tree - Prodigal (2021 Remaster, 24-bit/96kHz)")
    print(f"Engineer Reference: Steven Wilson")
    print()
    print(f"Total Tracks: {len(results)}")
    print()
    print("LOUDNESS:")
    print(f"  Original RMS:      {avg_original_rms:>7.2f} dB  (range: {min(r['original_rms'] for r in results):.2f} to {max(r['original_rms'] for r in results):.2f} dB)")
    print(f"  Remastered RMS:    {avg_remastered_rms:>7.2f} dB  (range: {min(r['remastered_rms'] for r in results):.2f} to {max(r['remastered_rms'] for r in results):.2f} dB)")
    print(f"  Average Boost:     {avg_boost:>+7.2f} dB")
    print()
    print(f"  Original LUFS:     {avg_original_lufs:>7.2f} LUFS")
    print(f"  Remastered LUFS:   {avg_remastered_lufs:>7.2f} LUFS")
    print(f"  LUFS Boost:        {avg_lufs_boost:>+7.2f} LU")
    print()
    print("DYNAMIC RANGE:")
    print(f"  Original DR:       {avg_original_dr:>7.2f} dB")
    print(f"  Remastered DR:     {avg_remastered_dr:>7.2f} dB")
    print(f"  DR Change:         {avg_dr_change:>+7.2f} dB")
    print(f"  DR Preservation:   {(avg_remastered_dr / avg_original_dr * 100):>6.1f}%")
    print()

    # Comparison to The Cure - Wish
    print("=" * 100)
    print("COMPARISON TO THE CURE - WISH (1992)")
    print("=" * 100)
    print()
    print(f"{'Metric':<30} {'The Cure (1992)':<20} {'Queensrÿche (1988)':<20}")
    print("-" * 70)
    print(f"{'Original RMS':<30} {'-18.6 dB':<20} {f'{avg_original_rms:.2f} dB':<20}")
    print(f"{'Remastered RMS (Target)':<30} {'-12.05 dB':<20} {f'{avg_remastered_rms:.2f} dB':<20}")
    print(f"{'Average Boost Required':<30} {'+6.1 dB':<20} {f'{avg_boost:+.2f} dB':<20}")
    print(f"{'Remastered LUFS':<30} {'~-13 to -14 LUFS':<20} {f'{avg_remastered_lufs:.2f} LUFS':<20}")
    print()
    print("OBSERVATIONS:")
    print(f"  • Both albums converge to Steven Wilson's reference standard (~-12 dB RMS / -14 LUFS)")
    print(f"  • Queensrÿche requires {'more' if abs(avg_boost) > 6.1 else 'less'} boost than The Cure")
    print(f"  • Dynamic range {'preserved' if avg_dr_change > -1 else 'slightly reduced'} in remaster")
    print()


if __name__ == '__main__':
    main()
