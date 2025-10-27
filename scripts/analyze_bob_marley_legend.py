#!/usr/bin/env python3
"""
Bob Marley - Legend Analysis
Extract Reggae profile from compilation remaster

Album: Legend (1984, 2002 Remaster)
Genre: Reggae
Era: 1970s-1980s recordings
Compilation: Greatest Hits
Remaster: 2002 (Island Records/Tuff Gong)

Why this matters:
- Completely different from rock/metal profiles
- Bass-fundamental focused (not just bass-heavy)
- Spacious, minimal compression
- Groove and dynamics critical
- Will validate content-aware processing on non-rock music
"""

import numpy as np
import soundfile as sf
from pathlib import Path
import json

def load_audio(filepath):
    """Load audio file."""
    audio, sr = sf.read(filepath)
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)
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
    # Use FFT for frequency analysis
    fft = np.fft.rfft(audio)
    freqs = np.fft.rfftfreq(len(audio), 1/sr)
    magnitude = np.abs(fft)

    # Define frequency bands (psychoacoustic)
    bass_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 4000)
    high_mask = (freqs >= 4000) & (freqs <= 20000)

    # Calculate energy in each band
    bass_energy = np.sum(magnitude[bass_mask]**2)
    mid_energy = np.sum(magnitude[mid_mask]**2)
    high_energy = np.sum(magnitude[high_mask]**2)

    total_energy = bass_energy + mid_energy + high_energy

    # Convert to percentages
    bass_pct = (bass_energy / total_energy) * 100
    mid_pct = (mid_energy / total_energy) * 100
    high_pct = (high_energy / total_energy) * 100

    # Calculate ratios in dB
    bass_to_mid = 10 * np.log10(bass_energy / mid_energy) if mid_energy > 0 else 0
    high_to_mid = 10 * np.log10(high_energy / mid_energy) if mid_energy > 0 else 0

    return {
        'bass_pct': bass_pct,
        'mid_pct': mid_pct,
        'high_pct': high_pct,
        'bass_to_mid_db': bass_to_mid,
        'high_to_mid_db': high_to_mid
    }

def analyze_track(filepath):
    """Complete track analysis."""
    print(f"\nAnalyzing: {filepath.name}")
    print("=" * 60)

    audio, sr = load_audio(filepath)

    # Basic measurements
    rms_db = calculate_rms_db(audio)
    peak_db = calculate_peak_db(audio)
    crest_db = calculate_crest_factor(audio)
    lufs = estimate_lufs(rms_db)

    # Frequency analysis
    freq_data = analyze_frequency_response(audio, sr)

    print(f"\nLoudness Metrics:")
    print(f"  RMS:          {rms_db:>7.2f} dB")
    print(f"  Peak:         {peak_db:>7.2f} dB")
    print(f"  Crest Factor: {crest_db:>7.2f} dB")
    print(f"  Est. LUFS:    {lufs:>7.2f} dB")

    print(f"\nFrequency Response:")
    print(f"  Bass (20-250 Hz):    {freq_data['bass_pct']:>5.1f}%")
    print(f"  Mid (250-4k Hz):     {freq_data['mid_pct']:>5.1f}%")
    print(f"  High (4k-20k Hz):    {freq_data['high_pct']:>5.1f}%")
    print(f"  Bass/Mid Ratio:      {freq_data['bass_to_mid_db']:>+6.1f} dB")
    print(f"  High/Mid Ratio:      {freq_data['high_to_mid_db']:>+6.1f} dB")

    return {
        'rms_db': rms_db,
        'peak_db': peak_db,
        'crest_factor_db': crest_db,
        'estimated_lufs': lufs,
        **freq_data
    }

def create_profile(track_data, track_info):
    """Create JSON profile."""
    profile = {
        'track_info': track_info,
        'loudness': {
            'rms_db': round(track_data['rms_db'], 2),
            'peak_db': round(track_data['peak_db'], 2),
            'crest_factor_db': round(track_data['crest_factor_db'], 2),
            'estimated_lufs': round(track_data['estimated_lufs'], 2)
        },
        'frequency_response': {
            'bass_pct': round(track_data['bass_pct'], 1),
            'mid_pct': round(track_data['mid_pct'], 1),
            'high_pct': round(track_data['high_pct'], 1),
            'bass_to_mid_db': round(track_data['bass_to_mid_db'], 1),
            'high_to_mid_db': round(track_data['high_to_mid_db'], 1)
        },
        'characteristics': {
            'genre': 'Reggae',
            'era': '1970s-1980s',
            'remaster_year': 2002,
            'sound_profile': 'Deep bass fundamentals, spacious mids, natural dynamics',
            'mastering_philosophy': 'Groove-focused, minimal compression, preserves space and dynamics'
        }
    }
    return profile

def main():
    """Main analysis."""
    print("=" * 80)
    print("BOB MARLEY - LEGEND - REGGAE PROFILE EXTRACTION")
    print("=" * 80)

    # Analyze multiple tracks for better reggae profile
    tracks = [
        ("01 - Get Up, Stand Up.flac", "Get Up, Stand Up"),
        ("03 - Stir It Up.flac", "Stir It Up"),
        ("04 - No Woman, No Cry.flac", "No Woman, No Cry")
    ]

    base_path = Path("/mnt/audio/Audio/Remasters/Bob Marley - Legend")
    results = []

    for filename, title in tracks:
        track_path = base_path / filename
        if track_path.exists():
            track_data = analyze_track(track_path)
            results.append((title, track_data))
        else:
            print(f"WARNING: {filename} not found")

    if not results:
        print("ERROR: No tracks found")
        return

    # Average the results
    avg_data = {
        'rms_db': np.mean([r[1]['rms_db'] for r in results]),
        'peak_db': np.mean([r[1]['peak_db'] for r in results]),
        'crest_factor_db': np.mean([r[1]['crest_factor_db'] for r in results]),
        'estimated_lufs': np.mean([r[1]['estimated_lufs'] for r in results]),
        'bass_pct': np.mean([r[1]['bass_pct'] for r in results]),
        'mid_pct': np.mean([r[1]['mid_pct'] for r in results]),
        'high_pct': np.mean([r[1]['high_pct'] for r in results]),
        'bass_to_mid_db': np.mean([r[1]['bass_to_mid_db'] for r in results]),
        'high_to_mid_db': np.mean([r[1]['high_to_mid_db'] for r in results])
    }

    # Create profile from averaged data
    track_info = {
        'album': 'Legend',
        'artist': 'Bob Marley & The Wailers',
        'year_range': '1971-1980',
        'compilation_year': 1984,
        'remaster_year': 2002,
        'label': 'Island Records / Tuff Gong',
        'genre': 'Reggae',
        'tracks_analyzed': [title for title, _ in results]
    }

    profile = create_profile(avg_data, track_info)

    # Save profile
    profile_path = Path('profiles/bob_marley_legend_2002.json')
    profile_path.parent.mkdir(exist_ok=True)

    with open(profile_path, 'w') as f:
        json.dump(profile, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Profile saved to: {profile_path}")
    print(f"{'=' * 60}")

    # Analysis summary
    print("\n" + "=" * 80)
    print("REGGAE PROFILE SUMMARY")
    print("=" * 80)

    print(f"\nAveraged from {len(results)} tracks:")
    for title, _ in results:
        print(f"  • {title}")

    print(f"\nKey Characteristics:")
    print(f"  • LUFS: {avg_data['estimated_lufs']:.1f} dB")
    print(f"  • Crest Factor: {avg_data['crest_factor_db']:.1f} dB")
    print(f"  • Bass: {avg_data['bass_pct']:.1f}%")
    print(f"  • Mid: {avg_data['mid_pct']:.1f}%")
    print(f"  • Bass/Mid: {avg_data['bass_to_mid_db']:+.1f} dB")

    print(f"\nExpected Reggae Characteristics:")
    print(f"  • Deep bass fundamentals (not just loudness)")
    print(f"  • Spacious, open sound")
    print(f"  • Minimal compression (groove is key)")
    print(f"  • Natural dynamics preserved")

if __name__ == '__main__':
    main()
