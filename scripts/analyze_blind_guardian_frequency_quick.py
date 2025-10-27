#!/usr/bin/env python3
"""
Quick Blind Guardian Frequency Analysis - One track per album
"""

import sys
from pathlib import Path
import numpy as np
import soundfile as sf
import json

def quick_frequency_analysis(audio: np.ndarray, sr: int) -> dict:
    """Quick frequency analysis"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # Subsample if too long (analyze first minute only)
    if len(audio_mono) > sr * 60:
        audio_mono = audio_mono[:sr * 60]

    fft = np.fft.rfft(audio_mono)
    freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)
    magnitude = np.abs(fft)

    # Bands
    bass_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 4000)
    high_mask = (freqs >= 4000) & (freqs <= 20000)

    bass_energy = np.sum(magnitude[bass_mask] ** 2)
    mid_energy = np.sum(magnitude[mid_mask] ** 2)
    high_energy = np.sum(magnitude[high_mask] ** 2)
    total = bass_energy + mid_energy + high_energy

    return {
        'bass_pct': (bass_energy / total * 100) if total > 0 else 0,
        'mid_pct': (mid_energy / total * 100) if total > 0 else 0,
        'high_pct': (high_energy / total * 100) if total > 0 else 0,
        'bass_db': 10 * np.log10(bass_energy) if bass_energy > 0 else -np.inf,
        'mid_db': 10 * np.log10(mid_energy) if mid_energy > 0 else -np.inf,
        'high_db': 10 * np.log10(high_energy) if high_energy > 0 else -np.inf,
    }

def main():
    base_dir = Path("/mnt/Musica/Musica/Blind Guardian")

    albums = [
        ("1995 - Imaginations From The Other Side", "1995 - Imaginations From The Other Side (2018)", "well_mastered"),
        ("2002 - A Night At The Opera", "2002 - A Night At The Opera (2018)", "well_mastered"),
    ]

    print("BLIND GUARDIAN FREQUENCY ANALYSIS (Quick)")
    print("=" * 80)

    results = []

    for orig_name, remaster_name, category in albums:
        print(f"\n{orig_name}...")

        orig_dir = base_dir / orig_name
        remaster_dir = base_dir / remaster_name

        # Get first track
        orig_tracks = sorted(list(orig_dir.glob("*.flac")))
        if not orig_tracks:
            continue

        orig_path = orig_tracks[0]
        remaster_path = remaster_dir / orig_path.name

        if not remaster_path.exists():
            continue

        print(f"  Analyzing: {orig_path.name}")

        # Load and analyze
        orig_audio, orig_sr = sf.read(str(orig_path))
        remaster_audio, remaster_sr = sf.read(str(remaster_path))

        orig_freq = quick_frequency_analysis(orig_audio, orig_sr)
        remaster_freq = quick_frequency_analysis(remaster_audio, remaster_sr)

        bass_to_mid_orig = orig_freq['bass_db'] - orig_freq['mid_db']
        high_to_mid_orig = orig_freq['high_db'] - orig_freq['mid_db']
        bass_to_mid_rem = remaster_freq['bass_db'] - remaster_freq['mid_db']
        high_to_mid_rem = remaster_freq['high_db'] - remaster_freq['mid_db']

        results.append({
            'album': orig_name,
            'original': {**orig_freq, 'bass_to_mid_db': bass_to_mid_orig, 'high_to_mid_db': high_to_mid_orig},
            'remaster': {**remaster_freq, 'bass_to_mid_db': bass_to_mid_rem, 'high_to_mid_db': high_to_mid_rem}
        })

        print(f"    Original:  Bass {orig_freq['bass_pct']:.1f}%  Mid {orig_freq['mid_pct']:.1f}%  High {orig_freq['high_pct']:.1f}%")
        print(f"    Remaster:  Bass {remaster_freq['bass_pct']:.1f}%  Mid {remaster_freq['mid_pct']:.1f}%  High {remaster_freq['high_pct']:.1f}%")
        print(f"    B/M: {bass_to_mid_orig:+.1f} → {bass_to_mid_rem:+.1f} dB  |  H/M: {high_to_mid_orig:+.1f} → {high_to_mid_rem:+.1f} dB")

    # Average
    print("\n" + "=" * 80)
    print("POWER METAL PROFILE (2018 Remasters)")
    print("=" * 80)

    avg_bass = np.mean([r['remaster']['bass_pct'] for r in results])
    avg_mid = np.mean([r['remaster']['mid_pct'] for r in results])
    avg_high = np.mean([r['remaster']['high_pct'] for r in results])
    avg_bass_to_mid = np.mean([r['remaster']['bass_to_mid_db'] for r in results])
    avg_high_to_mid = np.mean([r['remaster']['high_to_mid_db'] for r in results])

    print(f"\nBass:      {avg_bass:.1f}%")
    print(f"Mid:       {avg_mid:.1f}%")
    print(f"High:      {avg_high:.1f}%")
    print(f"Bass/Mid:  {avg_bass_to_mid:+.1f} dB")
    print(f"High/Mid:  {avg_high_to_mid:+.1f} dB")

    # Save
    profile = {
        'genre': 'Power Metal',
        'source': 'Blind Guardian 2018 Remasters',
        'frequency_balance': {
            'bass_pct': float(avg_bass),
            'mid_pct': float(avg_mid),
            'high_pct': float(avg_high),
            'bass_to_mid_db': float(avg_bass_to_mid),
            'high_to_mid_db': float(avg_high_to_mid),
        }
    }

    Path("profiles").mkdir(exist_ok=True)
    with open("profiles/power_metal_blind_guardian.json", 'w') as f:
        json.dump(profile, f, indent=2)

    print("\nProfile saved to: profiles/power_metal_blind_guardian.json")
    print("=" * 80)

if __name__ == '__main__':
    main()
