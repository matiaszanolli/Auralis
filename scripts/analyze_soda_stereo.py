#!/usr/bin/env python3
"""
Analyze Soda Stereo - El Ultimo Concierto remaster.

Source: /mnt/Musica/Musica/Soda Stereo/FLAC/El Ultimo Concierto A [Remasterizado 2007]
Reference: /mnt/Musica/Musica/Porcupine Tree/(2024) Porcupine Tree - Fear of a Blank Planet (Remastered Deluxe Edition) [FLAC]/CD2/02-Normal (Nil Recurring 2024 Remaster).flac
Result: /mnt/audio/Audio/Remasters/Soda Stereo - El Ultimo Concierto/A

This is Latin rock/pop using Steven Wilson's 2024 remaster as reference.
"""

import os
import json
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Dict, Tuple

def calculate_basic_metrics(audio: np.ndarray, sr: int) -> Dict:
    """Calculate basic loudness metrics."""
    if audio.ndim > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    rms_linear = np.sqrt(np.mean(audio_mono ** 2))
    rms_db = 20 * np.log10(rms_linear) if rms_linear > 0 else -np.inf
    peak_linear = np.max(np.abs(audio_mono))
    peak_db = 20 * np.log10(peak_linear) if peak_linear > 0 else -np.inf
    crest_factor = peak_db - rms_db
    estimated_lufs = rms_db + 0.691

    return {
        'rms_db': float(rms_db),
        'peak_db': float(peak_db),
        'crest_factor_db': float(crest_factor),
        'estimated_lufs': float(estimated_lufs)
    }

def calculate_frequency_bands(audio: np.ndarray, sr: int) -> Dict:
    """Calculate frequency band energy distribution."""
    if audio.ndim > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # Subsample if too long
    if len(audio_mono) > sr * 60:
        audio_mono = audio_mono[:sr * 60]

    fft = np.fft.rfft(audio_mono)
    magnitude = np.abs(fft)
    freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)

    bass_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 4000)
    high_mask = (freqs >= 4000) & (freqs <= 20000)

    bass_energy = np.sum(magnitude[bass_mask] ** 2)
    mid_energy = np.sum(magnitude[mid_mask] ** 2)
    high_energy = np.sum(magnitude[high_mask] ** 2)
    total_energy = bass_energy + mid_energy + high_energy

    bass_pct = (bass_energy / total_energy * 100) if total_energy > 0 else 0
    mid_pct = (mid_energy / total_energy * 100) if total_energy > 0 else 0
    high_pct = (high_energy / total_energy * 100) if total_energy > 0 else 0

    bass_to_mid_db = 10 * np.log10(bass_energy / mid_energy) if mid_energy > 0 else 0
    high_to_mid_db = 10 * np.log10(high_energy / mid_energy) if mid_energy > 0 else 0

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
    """Analyze Steven Wilson 2024 reference track."""
    print(f"\n{'='*80}")
    print("ANALYZING REFERENCE TRACK")
    print(f"{'='*80}\n")

    print(f"Reference: {reference_path}")

    audio, sr = sf.read(reference_path)
    duration = len(audio) / sr

    print(f"Sample rate: {sr} Hz")
    print(f"Duration: {duration:.1f} seconds")
    print(f"Channels: {audio.shape[1] if audio.ndim > 1 else 1}")

    print("\nCalculating loudness metrics...")
    loudness = calculate_basic_metrics(audio, sr)

    print("\nCalculating frequency response...")
    frequency = calculate_frequency_bands(audio, sr)

    print(f"\n{'='*80}")
    print("PORCUPINE TREE - NORMAL (2024 REMASTER) ANALYSIS")
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

def parse_matchering_log_data() -> list:
    """Parse Matchering processing log from provided data."""
    # Data extracted from the processing log
    tracks = [
        {
            'name': '01 En La Ciudad De La Furia',
            'original_rms': -12.04,
            'rms_coefficient': -7.54,
            'target_duration': '0:06:37'
        },
        {
            'name': '02 El Rito',
            'original_rms': -12.27,
            'rms_coefficient': -7.31,
            'target_duration': '0:07:04'
        },
        {
            'name': '03 Hombre Al Agua',
            'original_rms': -11.12,
            'rms_coefficient': -8.46,
            'target_duration': '0:06:29'
        },
        {
            'name': '04 (En) El Séptimo Día',
            'original_rms': -10.50,
            'rms_coefficient': -9.08,
            'target_duration': '0:04:57'
        },
        {
            'name': '05 Canción Animal',
            'original_rms': -11.20,
            'rms_coefficient': -8.38,
            'target_duration': '0:04:17'
        },
        {
            'name': '06 Trátame Suavemente',
            'original_rms': -12.39,
            'rms_coefficient': -7.18,
            'target_duration': '0:04:04'
        },
        {
            'name': '07 Paseando Por Roma',
            'original_rms': -11.08,
            'rms_coefficient': -8.50,
            'target_duration': '0:03:43'
        },
        {
            'name': '08 Lo Que Sangra (La Cúpula)',
            'original_rms': -10.48,
            'rms_coefficient': -9.10,
            'target_duration': '0:05:16'
        }
    ]

    return tracks

def analyze_soda_stereo_comparison(original_dir: str, remaster_dir: str) -> None:
    """Compare original and remastered Soda Stereo tracks."""
    print(f"\n{'='*80}")
    print("ANALYZING SODA STEREO - EL ULTIMO CONCIERTO REMASTER")
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

    # Analyze first 3 tracks
    num_analyze = min(3, len(original_files), len(remaster_files))

    changes = []

    for i in range(num_analyze):
        orig_file = original_files[i]
        rema_file = remaster_files[i]

        print(f"\n--- Track {i+1}: {orig_file.stem[:40]} ---")

        orig_audio, orig_sr = sf.read(orig_file)
        rema_audio, rema_sr = sf.read(rema_file)

        orig_metrics = calculate_basic_metrics(orig_audio, orig_sr)
        rema_metrics = calculate_basic_metrics(rema_audio, rema_sr)

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

    # Matchering log analysis
    print(f"\n{'='*80}")
    print("MATCHERING PROCESSING ANALYSIS (8 tracks)")
    print(f"{'='*80}\n")

    log_data = parse_matchering_log_data()

    print("RMS Coefficients Applied:")
    for track in log_data:
        print(f"  {track['name'][:30]:30s}: {track['rms_coefficient']:>+6.2f} dB")

    avg_rms_coeff = np.mean([t['rms_coefficient'] for t in log_data])
    print(f"\n  Average RMS Coefficient: {avg_rms_coeff:>+6.2f} dB")

    print("\nInterpretation:")
    if avg_rms_coeff < -6:
        print("  ✅ Significant RMS reduction applied (de-mastering)")
    elif avg_rms_coeff < -3:
        print("  ✅ Moderate RMS reduction")
    else:
        print("  ⚠️ Minimal RMS change")

def main():
    """Main analysis function."""
    print(f"\n{'='*80}")
    print("SODA STEREO & PORCUPINE TREE 2024 MASTERING ANALYSIS")
    print(f"{'='*80}\n")

    # Paths
    reference_path = "/mnt/Musica/Musica/Porcupine Tree/(2024) Porcupine Tree - Fear of a Blank Planet (Remastered Deluxe Edition) [FLAC]/CD2/02-Normal (Nil Recurring 2024 Remaster).flac"
    original_dir = "/mnt/Musica/Musica/Soda Stereo/FLAC/El Ultimo Concierto A [Remasterizado 2007]"
    remaster_dir = "/mnt/audio/Audio/Remasters/Soda Stereo - El Ultimo Concierto/A"

    # Check paths
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

    # Analyze Soda Stereo comparison
    analyze_soda_stereo_comparison(original_dir, remaster_dir)

    # Save profile
    profile = {
        "track_info": {
            "title": "Normal",
            "artist": "Porcupine Tree",
            "album": "Fear of a Blank Planet (Nil Recurring 2024 Remaster)",
            "year": 2024,
            "genre": "Progressive Rock",
            "engineer": "Steven Wilson",
            "notes": "Latest Steven Wilson remaster (2024)"
        },
        "loudness": ref_loudness,
        "frequency_response": ref_frequency
    }

    output_path = "profiles/steven_wilson_normal_2024.json"
    os.makedirs("profiles", exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(profile, f, indent=2)

    print(f"\n✅ Profile saved to: {output_path}")

if __name__ == "__main__":
    main()
