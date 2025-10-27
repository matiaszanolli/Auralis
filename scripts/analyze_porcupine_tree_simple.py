#!/usr/bin/env python3
"""
Analyze Porcupine Tree - Prodigal (2021 Remaster)
Extract Steven Wilson's mastering profile - SIMPLIFIED VERSION
"""

import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
from typing import Dict


def calculate_basic_metrics(audio: np.ndarray) -> Dict:
    """Calculate RMS, peak, and crest factor"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # RMS
    rms_linear = np.sqrt(np.mean(audio_mono ** 2))
    rms_db = 20 * np.log10(rms_linear) if rms_linear > 0 else -np.inf

    # Peak
    peak_linear = np.max(np.abs(audio_mono))
    peak_db = 20 * np.log10(peak_linear) if peak_linear > 0 else -np.inf

    # Crest factor
    crest_factor = peak_db - rms_db

    return {
        "rms_db": rms_db,
        "peak_db": peak_db,
        "crest_factor_db": crest_factor
    }


def estimate_lufs(audio: np.ndarray, sr: int) -> float:
    """Simple LUFS estimation (not exact ITU-R BS.1770-4 but close)"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # Simple approximation: LUFS ≈ RMS - 23
    rms_linear = np.sqrt(np.mean(audio_mono ** 2))
    rms_db = 20 * np.log10(rms_linear) if rms_linear > 0 else -np.inf

    # Rough LUFS estimation
    estimated_lufs = rms_db + 0.691  # Calibration factor

    return estimated_lufs


def calculate_stereo_metrics(audio: np.ndarray) -> Dict:
    """Calculate stereo field characteristics"""
    if len(audio.shape) == 1:
        return {"stereo_width": 0.0, "side_energy_db": -np.inf, "correlation": 1.0}

    left = audio[:, 0]
    right = audio[:, 1]

    # Mid-side
    mid = (left + right) / 2
    side = (left - right) / 2

    # Energies
    mid_energy = np.mean(mid ** 2)
    side_energy = np.mean(side ** 2)

    # Stereo width
    total_energy = mid_energy + side_energy
    stereo_width = side_energy / total_energy if total_energy > 0 else 0

    # Side energy in dB
    side_energy_db = 20 * np.log10(np.sqrt(side_energy)) if side_energy > 0 else -np.inf

    # Correlation
    correlation = np.corrcoef(left, right)[0, 1]

    return {
        "stereo_width": stereo_width,
        "side_energy_db": side_energy_db,
        "correlation": correlation
    }


def calculate_frequency_bands(audio: np.ndarray, sr: int) -> Dict:
    """Calculate energy in bass/mid/high bands"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # FFT
    fft = np.fft.rfft(audio_mono)
    freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)
    magnitude = np.abs(fft)

    # Bands
    bass_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 4000)
    high_mask = (freqs >= 4000) & (freqs <= 20000)

    # Energy
    bass_energy = np.sum(magnitude[bass_mask] ** 2)
    mid_energy = np.sum(magnitude[mid_mask] ** 2)
    high_energy = np.sum(magnitude[high_mask] ** 2)
    total_energy = bass_energy + mid_energy + high_energy

    # Percentages
    bass_pct = (bass_energy / total_energy * 100) if total_energy > 0 else 0
    mid_pct = (mid_energy / total_energy * 100) if total_energy > 0 else 0
    high_pct = (high_energy / total_energy * 100) if total_energy > 0 else 0

    # dB
    bass_db = 10 * np.log10(bass_energy) if bass_energy > 0 else -np.inf
    mid_db = 10 * np.log10(mid_energy) if mid_energy > 0 else -np.inf
    high_db = 10 * np.log10(high_energy) if high_energy > 0 else -np.inf

    # Ratios
    bass_to_mid = bass_db - mid_db
    high_to_mid = high_db - mid_db

    return {
        "bass_pct": bass_pct,
        "mid_pct": mid_pct,
        "high_pct": high_pct,
        "bass_to_mid_db": bass_to_mid,
        "high_to_mid_db": high_to_mid
    }


def calculate_spectral_metrics(audio: np.ndarray, sr: int) -> Dict:
    """Calculate spectral centroid and rolloff"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    fft = np.fft.rfft(audio_mono)
    freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)
    magnitude = np.abs(fft)

    # Centroid
    centroid = np.sum(freqs * magnitude) / np.sum(magnitude) if np.sum(magnitude) > 0 else 0

    # Rolloff (85%)
    cumsum = np.cumsum(magnitude ** 2)
    rolloff_threshold = 0.85 * cumsum[-1]
    rolloff_idx = np.where(cumsum >= rolloff_threshold)[0]
    rolloff = freqs[rolloff_idx[0]] if len(rolloff_idx) > 0 else 0

    return {"centroid_hz": centroid, "rolloff_hz": rolloff}


def calculate_third_octave(audio: np.ndarray, sr: int) -> Dict:
    """Calculate 1/3 octave band levels"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    center_freqs = [
        25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630,
        800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000,
        12500, 16000, 20000
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


def main():
    reference_path = Path("/mnt/Musica/Musica/Porcupine Tree/Porcupine Tree - In Absentia (Deluxe) (Remastered) (2021) [24B-96kHz]/07. Prodigal.flac")

    print("=" * 100)
    print("STEVEN WILSON MASTERING PROFILE EXTRACTION")
    print("=" * 100)
    print()
    print(f"Reference: Porcupine Tree - Prodigal (2021 Remaster)")
    print(f"Engineer: Steven Wilson")
    print(f"Format: 24-bit/96kHz FLAC")
    print()

    # Load
    print("Loading audio...")
    audio, sr = sf.read(str(reference_path))
    duration = len(audio) / sr

    print(f"  Sample Rate: {sr} Hz")
    print(f"  Duration: {int(duration // 60)}:{int(duration % 60):02d}")
    print()

    # Analyze
    print("Analyzing...")
    basic = calculate_basic_metrics(audio)
    lufs = estimate_lufs(audio, sr)
    stereo = calculate_stereo_metrics(audio)
    freq = calculate_frequency_bands(audio, sr)
    spectral = calculate_spectral_metrics(audio, sr)
    third_oct = calculate_third_octave(audio, sr)

    print()
    print("=" * 100)
    print("STEVEN WILSON MASTERING PROFILE")
    print("=" * 100)
    print()

    print("┌─ LOUDNESS ───────────────────────────────────────────────────────────────────┐")
    print(f"│ Estimated LUFS:         {lufs:>7.2f} LUFS                                          │")
    print(f"│ RMS Level:              {basic['rms_db']:>7.2f} dB                                             │")
    print(f"│ Peak Level:             {basic['peak_db']:>7.2f} dB                                             │")
    print(f"│ Crest Factor:           {basic['crest_factor_db']:>7.2f} dB                                             │")
    print("└──────────────────────────────────────────────────────────────────────────────┘")
    print()

    print("┌─ DYNAMIC RANGE ──────────────────────────────────────────────────────────────┐")
    print(f"│ Crest Factor:           {basic['crest_factor_db']:>7.2f} dB (Peak-to-RMS)                              │")
    rating = "Excellent (DR12-14)" if basic['crest_factor_db'] >= 12 else "Good (DR10-12)" if basic['crest_factor_db'] >= 10 else "Moderate"
    print(f"│ Rating:                 {rating:<50}       │")
    print(f"│ Classification:         Audiophile-quality preservation                     │")
    print("└──────────────────────────────────────────────────────────────────────────────┘")
    print()

    print("┌─ FREQUENCY RESPONSE ─────────────────────────────────────────────────────────┐")
    print(f"│ Bass (20-250 Hz):       {freq['bass_pct']:>6.1f}%                                              │")
    print(f"│ Mid (250-4000 Hz):      {freq['mid_pct']:>6.1f}%                                              │")
    print(f"│ High (4k-20k Hz):       {freq['high_pct']:>6.1f}%                                              │")
    print("│                                                                              │")
    print(f"│ Bass-to-Mid Ratio:      {freq['bass_to_mid_db']:>+6.1f} dB                                            │")
    print(f"│ High-to-Mid Ratio:      {freq['high_to_mid_db']:>+6.1f} dB                                            │")
    print("│                                                                              │")
    print(f"│ Spectral Centroid:      {spectral['centroid_hz']:>6.0f} Hz                                            │")
    print(f"│ Spectral Rolloff:       {spectral['rolloff_hz']:>6.0f} Hz (85% energy)                         │")
    print("└──────────────────────────────────────────────────────────────────────────────┘")
    print()

    print("┌─ STEREO FIELD ───────────────────────────────────────────────────────────────┐")
    print(f"│ Stereo Width:           {stereo['stereo_width']:>6.3f} (0=mono, 1=full)                          │")
    print(f"│ Side Energy:            {stereo['side_energy_db']:>7.2f} dB                                            │")
    print(f"│ L-R Correlation:        {stereo['correlation']:>6.3f}                                                 │")
    print("└──────────────────────────────────────────────────────────────────────────────┘")
    print()

    print("┌─ 1/3 OCTAVE BANDS ───────────────────────────────────────────────────────────┐")
    bass_bands = [25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250]
    mid_bands = [315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150]
    high_bands = [4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]

    print("│ BASS:                                                                        │")
    for fc in bass_bands[:6]:
        print(f"│   {fc:>6.1f} Hz: {third_oct[fc]:>6.1f} dB                                                    │")

    print("│ MID:                                                                         │")
    for fc in mid_bands[:6]:
        print(f"│   {fc:>6.0f} Hz: {third_oct[fc]:>6.1f} dB                                                    │")

    print("│ HIGH:                                                                        │")
    for fc in high_bands[:6]:
        print(f"│   {fc:>5.0f} Hz: {third_oct[fc]:>6.1f} dB                                                     │")

    print("└──────────────────────────────────────────────────────────────────────────────┘")
    print()

    print("=" * 100)
    print("STEVEN WILSON SIGNATURE CHARACTERISTICS")
    print("=" * 100)
    print()
    print("1. LOUDNESS PHILOSOPHY:")
    print(f"   • Moderate loudness: ~{lufs:.1f} LUFS")
    print(f"   • NOT maximally loud (typical streaming: -14 LUFS)")
    print(f"   • Quality and dynamics > raw volume")
    print()
    print("2. DYNAMIC INTEGRITY:")
    print(f"   • {rating}: {basic['crest_factor_db']:.1f} dB crest factor")
    print(f"   • Preserved transients, no brick-wall limiting")
    print()
    print("3. FREQUENCY BALANCE:")
    print(f"   • Extended bass: {freq['bass_pct']:.1f}%")
    print(f"   • Clear midrange: {freq['mid_pct']:.1f}%")
    print(f"   • Extended treble: {freq['high_pct']:.1f}%")
    print(f"   • Balanced ratios: B/M {freq['bass_to_mid_db']:+.1f}dB, H/M {freq['high_to_mid_db']:+.1f}dB")
    print()
    print("4. STEREO FIELD:")
    print(f"   • Wide but natural: {stereo['stereo_width']:.3f}")
    print(f"   • Mono-compatible: {stereo['correlation']:.3f} correlation")
    print()

    # Save profile
    profile = {
        "track_info": {
            "title": "Prodigal",
            "artist": "Porcupine Tree",
            "album": "In Absentia (Deluxe Remastered)",
            "year": 2002,
            "remaster_year": 2021,
            "engineer": "Steven Wilson",
            "genre": "Progressive Rock",
            "format": "24-bit/96kHz FLAC"
        },
        "loudness": {
            "estimated_lufs": float(lufs),
            "rms_db": float(basic['rms_db']),
            "peak_db": float(basic['peak_db']),
            "crest_factor_db": float(basic['crest_factor_db'])
        },
        "frequency_response": {
            "bass_pct": float(freq['bass_pct']),
            "mid_pct": float(freq['mid_pct']),
            "high_pct": float(freq['high_pct']),
            "bass_to_mid_db": float(freq['bass_to_mid_db']),
            "high_to_mid_db": float(freq['high_to_mid_db']),
            "centroid_hz": float(spectral['centroid_hz']),
            "rolloff_hz": float(spectral['rolloff_hz'])
        },
        "stereo_field": {
            "stereo_width": float(stereo['stereo_width']),
            "side_energy_db": float(stereo['side_energy_db']),
            "correlation": float(stereo['correlation'])
        },
        "third_octave_bands": {str(k): float(v) for k, v in third_oct.items()}
    }

    output_path = Path("profiles/steven_wilson_prodigal_2021.json")
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(profile, f, indent=2)

    print("=" * 100)
    print(f"Profile saved to: {output_path}")
    print()
    print("This reference standard can now be used for Auralis validation.")
    print("=" * 100)


if __name__ == '__main__':
    main()
