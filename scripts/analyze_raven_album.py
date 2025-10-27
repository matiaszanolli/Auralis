#!/usr/bin/env python3
"""
Complete Album Analysis - Steven Wilson: The Raven That Refused to Sing (2013)
Mastered by: Alan Parsons

This is critical - comparing Steven Wilson's self-mastering (Hand. Cannot. Erase.)
vs Alan Parsons mastering (The Raven) to understand audiophile mastering philosophy.
"""

import numpy as np
import soundfile as sf
from pathlib import Path
import json
from typing import Dict, List

def load_audio(filepath, max_duration=60):
    """Load audio (first 60 seconds for analysis speed)."""
    audio, sr = sf.read(filepath)
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    max_samples = sr * max_duration
    if len(audio) > max_samples:
        audio = audio[:max_samples]

    return audio, sr

def calculate_rms_db(audio):
    """Calculate RMS level in dB."""
    rms = np.sqrt(np.mean(audio**2))
    return 20 * np.log10(rms) if rms > 0 else -100

def calculate_peak_db(audio):
    """Calculate peak level in dB."""
    peak = np.max(np.abs(audio))
    return 20 * np.log10(peak) if peak > 0 else -100

def calculate_crest_factor(audio):
    """Calculate crest factor (peak-to-RMS ratio) in dB."""
    peak_db = calculate_peak_db(audio)
    rms_db = calculate_rms_db(audio)
    return peak_db - rms_db

def estimate_lufs(rms_db):
    """Rough LUFS estimation from RMS."""
    return rms_db + 3.0

def analyze_frequency_response(audio, sr):
    """Analyze frequency response in three bands."""
    fft = np.fft.rfft(audio)
    freqs = np.fft.rfftfreq(len(audio), 1/sr)
    magnitude = np.abs(fft)

    # Frequency bands
    bass_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 4000)
    high_mask = (freqs >= 4000) & (freqs <= 20000)

    # Energy in each band
    bass_energy = np.sum(magnitude[bass_mask]**2)
    mid_energy = np.sum(magnitude[mid_mask]**2)
    high_energy = np.sum(magnitude[high_mask]**2)
    total_energy = bass_energy + mid_energy + high_energy

    # Percentages
    bass_pct = (bass_energy / total_energy) * 100 if total_energy > 0 else 0
    mid_pct = (mid_energy / total_energy) * 100 if total_energy > 0 else 0
    high_pct = (high_energy / total_energy) * 100 if total_energy > 0 else 0

    # Ratios in dB
    bass_to_mid_db = 10 * np.log10(bass_energy / mid_energy) if mid_energy > 0 else 0
    high_to_mid_db = 10 * np.log10(high_energy / mid_energy) if mid_energy > 0 else 0

    return {
        'bass_pct': bass_pct,
        'mid_pct': mid_pct,
        'high_pct': high_pct,
        'bass_to_mid_db': bass_to_mid_db,
        'high_to_mid_db': high_to_mid_db
    }

def analyze_track(filepath: Path, track_num: int) -> Dict:
    """Complete analysis of one track."""
    print(f"\n{track_num}. {filepath.name}")

    audio, sr = load_audio(filepath)

    # Dynamics
    rms_db = calculate_rms_db(audio)
    peak_db = calculate_peak_db(audio)
    crest_db = calculate_crest_factor(audio)
    lufs = estimate_lufs(rms_db)

    # Frequency
    freq = analyze_frequency_response(audio, sr)

    # Duration
    info = sf.info(filepath)
    duration = info.duration

    print(f"   Duration: {duration//60:.0f}:{duration%60:02.0f}")
    print(f"   LUFS: {lufs:>6.1f} dB  |  Crest: {crest_db:>5.1f} dB  |  Peak: {peak_db:>6.2f} dB")
    print(f"   Bass: {freq['bass_pct']:>5.1f}%  |  Mid: {freq['mid_pct']:>5.1f}%  |  High: {freq['high_pct']:>5.1f}%")
    print(f"   B/M: {freq['bass_to_mid_db']:>+5.1f} dB  |  H/M: {freq['high_to_mid_db']:>+5.1f} dB")

    return {
        'track_num': track_num,
        'filename': filepath.name,
        'duration': duration,
        'lufs': lufs,
        'rms_db': rms_db,
        'peak_db': peak_db,
        'crest_db': crest_db,
        'bass_pct': freq['bass_pct'],
        'mid_pct': freq['mid_pct'],
        'high_pct': freq['high_pct'],
        'bass_to_mid_db': freq['bass_to_mid_db'],
        'high_to_mid_db': freq['high_to_mid_db']
    }

def calculate_statistics(results: List[Dict]) -> Dict:
    """Calculate statistics across all tracks."""
    metrics = ['lufs', 'crest_db', 'bass_pct', 'mid_pct', 'high_pct',
               'bass_to_mid_db', 'high_to_mid_db']

    stats = {}
    for metric in metrics:
        values = [r[metric] for r in results]
        stats[metric] = {
            'mean': np.mean(values),
            'std': np.std(values),
            'min': np.min(values),
            'max': np.max(values),
            'range': np.max(values) - np.min(values)
        }

    return stats

def analyze_correlations(results: List[Dict]) -> Dict:
    """Analyze correlations between parameters."""
    lufs = np.array([r['lufs'] for r in results])
    crest = np.array([r['crest_db'] for r in results])
    bass_mid = np.array([r['bass_to_mid_db'] for r in results])
    bass_pct = np.array([r['bass_pct'] for r in results])

    correlations = {
        'lufs_crest': np.corrcoef(lufs, crest)[0, 1],
        'lufs_bass_mid': np.corrcoef(lufs, bass_mid)[0, 1],
        'crest_bass_mid': np.corrcoef(crest, bass_mid)[0, 1],
        'bass_pct_bass_mid': np.corrcoef(bass_pct, bass_mid)[0, 1]
    }

    return correlations

def main():
    """Main analysis."""
    print("=" * 80)
    print("STEVEN WILSON - THE RAVEN THAT REFUSED TO SING (2013)")
    print("Mastered by: ALAN PARSONS")
    print("=" * 80)
    print("\nAnalyzing legendary mastering across 6 tracks...")

    album_path = Path("/mnt/Musica/Musica/Steven Wilson/2013 - The Raven that Refused to Sing {24-96}")

    # Get all FLAC files
    tracks = sorted(album_path.glob("*.flac"))

    print(f"\nFound {len(tracks)} tracks")
    print("=" * 80)

    # Analyze each track
    results = []
    for i, track_path in enumerate(tracks, 1):
        try:
            result = analyze_track(track_path, i)
            results.append(result)
        except Exception as e:
            print(f"   ❌ Error: {e}")

    if not results:
        print("\n❌ No tracks could be analyzed")
        return

    # Statistics
    print("\n" + "=" * 80)
    print("ALBUM STATISTICS - ALAN PARSONS MASTERING")
    print("=" * 80)

    stats = calculate_statistics(results)

    print("\n📊 LOUDNESS & DYNAMICS:")
    print(f"  LUFS:        {stats['lufs']['mean']:>6.1f} ± {stats['lufs']['std']:>4.1f} dB  "
          f"[{stats['lufs']['min']:>6.1f} to {stats['lufs']['max']:>6.1f}]  "
          f"Range: {stats['lufs']['range']:>4.1f} dB")
    print(f"  Crest Factor:{stats['crest_db']['mean']:>6.1f} ± {stats['crest_db']['std']:>4.1f} dB  "
          f"[{stats['crest_db']['min']:>6.1f} to {stats['crest_db']['max']:>6.1f}]  "
          f"Range: {stats['crest_db']['range']:>4.1f} dB")

    print("\n📊 FREQUENCY DISTRIBUTION:")
    print(f"  Bass %:      {stats['bass_pct']['mean']:>6.1f} ± {stats['bass_pct']['std']:>4.1f} %   "
          f"[{stats['bass_pct']['min']:>6.1f} to {stats['bass_pct']['max']:>6.1f}]  "
          f"Range: {stats['bass_pct']['range']:>4.1f} %")
    print(f"  Mid %:       {stats['mid_pct']['mean']:>6.1f} ± {stats['mid_pct']['std']:>4.1f} %   "
          f"[{stats['mid_pct']['min']:>6.1f} to {stats['mid_pct']['max']:>6.1f}]  "
          f"Range: {stats['mid_pct']['range']:>4.1f} %")
    print(f"  High %:      {stats['high_pct']['mean']:>6.1f} ± {stats['high_pct']['std']:>4.1f} %   "
          f"[{stats['high_pct']['min']:>6.1f} to {stats['high_pct']['max']:>6.1f}]  "
          f"Range: {stats['high_pct']['range']:>4.1f} %")

    print("\n📊 FREQUENCY RATIOS:")
    print(f"  Bass/Mid:    {stats['bass_to_mid_db']['mean']:>+6.1f} ± {stats['bass_to_mid_db']['std']:>4.1f} dB  "
          f"[{stats['bass_to_mid_db']['min']:>+6.1f} to {stats['bass_to_mid_db']['max']:>+6.1f}]  "
          f"Range: {stats['bass_to_mid_db']['range']:>4.1f} dB")

    # Correlations
    print("\n" + "=" * 80)
    print("PARAMETER CORRELATIONS")
    print("=" * 80)

    corr = analyze_correlations(results)

    print("\n🔗 CORRELATION COEFFICIENTS:")
    print(f"  LUFS ↔ Crest Factor:    {corr['lufs_crest']:>+6.3f}  "
          f"({'Strong inverse' if corr['lufs_crest'] < -0.7 else 'Weak' if abs(corr['lufs_crest']) < 0.3 else 'Moderate'})")
    print(f"  LUFS ↔ Bass/Mid Ratio:  {corr['lufs_bass_mid']:>+6.3f}")
    print(f"  Crest ↔ Bass/Mid Ratio: {corr['crest_bass_mid']:>+6.3f}")

    # Key insights
    print("\n" + "=" * 80)
    print("KEY INSIGHTS - ALAN PARSONS APPROACH")
    print("=" * 80)

    print("\n🎯 MASTERING CONSISTENCY:")
    if stats['lufs']['range'] < 3:
        print(f"  ✅ Very consistent loudness (±{stats['lufs']['std']:.1f} dB) - LOUDER than Hand. Cannot. Erase.?")
    elif stats['lufs']['range'] < 5:
        print(f"  ✅ Good loudness consistency (±{stats['lufs']['std']:.1f} dB)")
    else:
        print(f"  ⚠️  Variable loudness (±{stats['lufs']['std']:.1f} dB) - intentional dynamics")

    if stats['crest_db']['range'] < 3:
        print(f"  ✅ Very consistent dynamics (±{stats['crest_db']['std']:.1f} dB) - TIGHTER than Hand. Cannot. Erase.?")
    elif stats['crest_db']['range'] < 5:
        print(f"  ✅ Good dynamics consistency (±{stats['crest_db']['std']:.1f} dB)")
    else:
        print(f"  ⚠️  Variable dynamics (±{stats['crest_db']['std']:.1f} dB)")

    print("\n🎯 FREQUENCY BALANCE:")
    if stats['bass_to_mid_db']['range'] < 2:
        print(f"  ✅ Very consistent tonal balance (±{stats['bass_to_mid_db']['std']:.1f} dB)")
    elif stats['bass_to_mid_db']['range'] < 4:
        print(f"  ✅ Good tonal consistency (±{stats['bass_to_mid_db']['std']:.1f} dB)")
    else:
        print(f"  ⚠️  Variable tonal balance (±{stats['bass_to_mid_db']['std']:.1f} dB)")

    # Save results
    output_path = Path('analysis_steven_wilson_the_raven.json')
    output_data = {
        'album': 'The Raven That Refused to Sing',
        'artist': 'Steven Wilson',
        'year': 2013,
        'mastered_by': 'Alan Parsons',
        'tracks': results,
        'statistics': {k: {k2: float(v2) for k2, v2 in v.items()}
                      for k, v in stats.items()},
        'correlations': {k: float(v) for k, v in corr.items()}
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n💾 Complete analysis saved to: {output_path}")
    print("=" * 80)

if __name__ == '__main__':
    main()
