#!/usr/bin/env python3
"""
Analyze Motörhead 1916 remaster against Joe Satriani reference.

This script analyzes the Motörhead 1916 (1991) album remastered with
Joe Satriani - Can't Go Back (2014) as reference to extract rock/metal
mastering profile.

Source: /mnt/Musica/Musica/Motörhead/Motörhead - 1916 (1991)(Netherlands)[LP][24-96][FLAC]
Result: /mnt/audio/Audio/Remasters/Motörhead - 1916
Reference: /mnt/Musica/Musica/Joe Satriani/Joe Satriani - Unstoppable Momentum (2014)/02 - Can't Go Back.flac
"""

import os
import json
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Dict, Tuple

def calculate_basic_metrics(audio: np.ndarray, sr: int) -> Dict:
    """Calculate basic loudness metrics."""
    # Convert to mono for analysis
    if audio.ndim > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # RMS calculation
    rms_linear = np.sqrt(np.mean(audio_mono ** 2))
    rms_db = 20 * np.log10(rms_linear) if rms_linear > 0 else -np.inf

    # Peak calculation
    peak_linear = np.max(np.abs(audio_mono))
    peak_db = 20 * np.log10(peak_linear) if peak_linear > 0 else -np.inf

    # Crest factor
    crest_factor = peak_db - rms_db

    # Estimate LUFS (ITU-R BS.1770 simplified)
    estimated_lufs = rms_db + 0.691

    return {
        'rms_db': float(rms_db),
        'peak_db': float(peak_db),
        'crest_factor_db': float(crest_factor),
        'estimated_lufs': float(estimated_lufs)
    }

def calculate_frequency_bands(audio: np.ndarray, sr: int) -> Dict:
    """Calculate frequency band energy distribution."""
    # Convert to mono
    if audio.ndim > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # Subsample if too long (analyze first minute only for speed)
    if len(audio_mono) > sr * 60:
        audio_mono = audio_mono[:sr * 60]

    # FFT analysis
    fft = np.fft.rfft(audio_mono)
    magnitude = np.abs(fft)
    freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)

    # Define bands
    bass_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 4000)
    high_mask = (freqs >= 4000) & (freqs <= 20000)

    # Calculate energy in each band
    bass_energy = np.sum(magnitude[bass_mask] ** 2)
    mid_energy = np.sum(magnitude[mid_mask] ** 2)
    high_energy = np.sum(magnitude[high_mask] ** 2)
    total_energy = bass_energy + mid_energy + high_energy

    # Calculate percentages
    bass_pct = (bass_energy / total_energy * 100) if total_energy > 0 else 0
    mid_pct = (mid_energy / total_energy * 100) if total_energy > 0 else 0
    high_pct = (high_energy / total_energy * 100) if total_energy > 0 else 0

    # Calculate ratios in dB
    bass_to_mid_db = 10 * np.log10(bass_energy / mid_energy) if mid_energy > 0 else 0
    high_to_mid_db = 10 * np.log10(high_energy / mid_energy) if mid_energy > 0 else 0

    # Spectral centroid and rolloff
    centroid = np.sum(freqs * magnitude) / np.sum(magnitude) if np.sum(magnitude) > 0 else 0

    cumsum = np.cumsum(magnitude)
    rolloff_idx = np.where(cumsum >= 0.85 * cumsum[-1])[0]
    rolloff = freqs[rolloff_idx[0]] if len(rolloff_idx) > 0 else 0

    return {
        'bass_pct': float(bass_pct),
        'mid_pct': float(mid_pct),
        'high_pct': float(high_pct),
        'bass_to_mid_db': float(bass_to_mid_db),
        'high_to_mid_db': float(high_to_mid_db),
        'centroid_hz': float(centroid),
        'rolloff_hz': float(rolloff)
    }

def analyze_reference(reference_path: str) -> Tuple[Dict, Dict]:
    """Analyze Joe Satriani reference track."""
    print(f"\n{'='*80}")
    print("ANALYZING REFERENCE TRACK")
    print(f"{'='*80}\n")

    print(f"Reference: {reference_path}")

    # Load audio
    audio, sr = sf.read(reference_path)
    duration = len(audio) / sr

    print(f"Sample rate: {sr} Hz")
    print(f"Duration: {duration:.1f} seconds")
    print(f"Channels: {audio.shape[1] if audio.ndim > 1 else 1}")

    # Calculate metrics
    print("\nCalculating loudness metrics...")
    loudness = calculate_basic_metrics(audio, sr)

    print("\nCalculating frequency response...")
    frequency = calculate_frequency_bands(audio, sr)

    # Print results
    print(f"\n{'='*80}")
    print("JOE SATRIANI - CAN'T GO BACK (2014) ANALYSIS")
    print(f"{'='*80}\n")

    print("LOUDNESS:")
    print(f"  LUFS (estimated):  {loudness['estimated_lufs']:>6.2f} dB")
    print(f"  RMS:               {loudness['rms_db']:>6.2f} dB")
    print(f"  Peak:              {loudness['peak_db']:>6.2f} dB")
    print(f"  Crest Factor:      {loudness['crest_factor_db']:>6.2f} dB")

    print("\nFREQUENCY RESPONSE:")
    print(f"  Bass (20-250 Hz):    {frequency['bass_pct']:>5.1f}%")
    print(f"  Mid (250-4k Hz):     {frequency['mid_pct']:>5.1f}%")
    print(f"  High (4k-20k Hz):    {frequency['high_pct']:>5.1f}%")
    print(f"  Bass/Mid Ratio:      {frequency['bass_to_mid_db']:>+5.1f} dB")
    print(f"  High/Mid Ratio:      {frequency['high_to_mid_db']:>+5.1f} dB")
    print(f"  Spectral Centroid:   {frequency['centroid_hz']:>7.0f} Hz")
    print(f"  Spectral Rolloff:    {frequency['rolloff_hz']:>7.0f} Hz")

    return loudness, frequency

def analyze_motorhead_comparison(original_dir: str, remaster_dir: str) -> None:
    """Compare original and remastered Motörhead tracks."""
    print(f"\n{'='*80}")
    print("ANALYZING MOTÖRHEAD 1916 REMASTER")
    print(f"{'='*80}\n")

    # Find matching files
    original_files = sorted(Path(original_dir).glob("*.flac"))
    remaster_files = sorted(Path(remaster_dir).glob("*.flac"))

    if not original_files:
        print(f"No original files found in {original_dir}")
        return

    if not remaster_files:
        print(f"No remaster files found in {remaster_dir}")
        return

    print(f"Found {len(original_files)} original tracks")
    print(f"Found {len(remaster_files)} remastered tracks")

    # Analyze first 2-3 tracks for comparison
    num_analyze = min(3, len(original_files), len(remaster_files))

    changes = []

    for i in range(num_analyze):
        orig_file = original_files[i]
        rema_file = remaster_files[i]

        print(f"\n--- Track {i+1}: {orig_file.stem[:40]} ---")

        # Load audio
        orig_audio, orig_sr = sf.read(orig_file)
        rema_audio, rema_sr = sf.read(rema_file)

        # Calculate metrics
        orig_metrics = calculate_basic_metrics(orig_audio, orig_sr)
        rema_metrics = calculate_basic_metrics(rema_audio, rema_sr)

        # Calculate changes
        rms_change = rema_metrics['rms_db'] - orig_metrics['rms_db']
        crest_change = rema_metrics['crest_factor_db'] - orig_metrics['crest_factor_db']

        changes.append({
            'rms_change': rms_change,
            'crest_change': crest_change
        })

        print(f"  Original RMS:    {orig_metrics['rms_db']:>6.2f} dB")
        print(f"  Remaster RMS:    {rema_metrics['rms_db']:>6.2f} dB")
        print(f"  RMS Change:      {rms_change:>+6.2f} dB")
        print(f"  Original Crest:  {orig_metrics['crest_factor_db']:>6.2f} dB")
        print(f"  Remaster Crest:  {rema_metrics['crest_factor_db']:>6.2f} dB")
        print(f"  Crest Change:    {crest_change:>+6.2f} dB")

    # Summary
    avg_rms_change = np.mean([c['rms_change'] for c in changes])
    avg_crest_change = np.mean([c['crest_change'] for c in changes])

    print(f"\n{'='*80}")
    print("REMASTER SUMMARY")
    print(f"{'='*80}\n")
    print(f"  Average RMS Change:     {avg_rms_change:>+6.2f} dB")
    print(f"  Average Crest Change:   {avg_crest_change:>+6.2f} dB")

    # Interpret results
    print("\nINTERPRETATION:")
    if avg_rms_change > 1.0:
        print("  ✅ Significant loudness increase (modernization)")
    elif avg_rms_change > 0:
        print("  ✅ Modest loudness increase")
    else:
        print("  ⚡ Loudness reduced (de-mastering)")

    if avg_crest_change > 1.0:
        print("  ✅ Dynamic range expanded (improved)")
    elif avg_crest_change > -1.0:
        print("  ✅ Dynamic range preserved")
    else:
        print("  ⚠️ Dynamic range reduced (compression)")

def main():
    """Main analysis function."""
    print(f"\n{'='*80}")
    print("MOTÖRHEAD 1916 & JOE SATRIANI MASTERING ANALYSIS")
    print(f"{'='*80}\n")

    # Paths
    reference_path = "/mnt/Musica/Musica/Joe Satriani/Joe Satriani - Unstoppable Momentum (2014)/02 - Can't Go Back.flac"
    original_dir = "/mnt/Musica/Musica/Motörhead/Motörhead - 1916 (1991)(Netherlands)[LP][24-96][FLAC]"
    remaster_dir = "/mnt/audio/Audio/Remasters/Motörhead - 1916"

    # Check paths exist
    if not os.path.exists(reference_path):
        print(f"❌ Reference not found: {reference_path}")
        return

    if not os.path.exists(original_dir):
        print(f"❌ Original not found: {original_dir}")
        return

    if not os.path.exists(remaster_dir):
        print(f"❌ Remaster not found: {remaster_dir}")
        return

    # Analyze reference
    ref_loudness, ref_frequency = analyze_reference(reference_path)

    # Analyze Motörhead comparison
    analyze_motorhead_comparison(original_dir, remaster_dir)

    # Save profile
    profile = {
        "track_info": {
            "title": "Can't Go Back",
            "artist": "Joe Satriani",
            "album": "Unstoppable Momentum",
            "year": 2014,
            "genre": "Instrumental Rock/Metal",
            "notes": "Modern professional rock/metal reference"
        },
        "loudness": ref_loudness,
        "frequency_response": ref_frequency
    }

    output_path = "profiles/joe_satriani_cant_go_back_2014.json"
    os.makedirs("profiles", exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(profile, f, indent=2)

    print(f"\n✅ Profile saved to: {output_path}")

if __name__ == "__main__":
    main()
