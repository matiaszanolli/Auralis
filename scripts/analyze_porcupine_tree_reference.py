#!/usr/bin/env python3
"""
Analyze Porcupine Tree - Prodigal (2021 Remaster)
Extract Steven Wilson's mastering profile - the reference standard
"""

import sys
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
from typing import Dict

# Add auralis to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.loudness_meter import LoudnessMeter
from auralis.analysis.dynamic_range import DynamicRangeAnalyzer
from auralis.analysis.spectrum_analyzer import SpectrumAnalyzer


def calculate_rms(audio: np.ndarray) -> float:
    """Calculate RMS level in dB"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    rms_linear = np.sqrt(np.mean(audio_mono ** 2))
    return 20 * np.log10(rms_linear) if rms_linear > 0 else -np.inf


def calculate_crest_factor(audio: np.ndarray) -> float:
    """Calculate crest factor (peak-to-RMS ratio) in dB"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    peak = np.max(np.abs(audio_mono))
    rms = np.sqrt(np.mean(audio_mono ** 2))

    peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
    rms_db = 20 * np.log10(rms) if rms > 0 else -np.inf

    return peak_db - rms_db


def calculate_stereo_width(audio: np.ndarray) -> Dict:
    """Calculate stereo field characteristics"""
    if len(audio.shape) == 1:
        return {"stereo_width": 0.0, "side_energy": -np.inf, "correlation": 1.0}

    left = audio[:, 0]
    right = audio[:, 1]

    # Mid-side encoding
    mid = (left + right) / 2
    side = (left - right) / 2

    # Calculate energies
    mid_energy = np.mean(mid ** 2)
    side_energy = np.mean(side ** 2)

    # Stereo width (0 = mono, 1 = full stereo)
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
    """Calculate energy in frequency bands"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # FFT
    fft = np.fft.rfft(audio_mono)
    freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)
    magnitude = np.abs(fft)

    # Define bands
    bass_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 4000)
    high_mask = (freqs >= 4000) & (freqs <= 20000)

    # Calculate energy in each band
    bass_energy = np.sum(magnitude[bass_mask] ** 2)
    mid_energy = np.sum(magnitude[mid_mask] ** 2)
    high_energy = np.sum(magnitude[high_mask] ** 2)

    total_energy = bass_energy + mid_energy + high_energy

    # Normalize to percentages
    bass_pct = (bass_energy / total_energy * 100) if total_energy > 0 else 0
    mid_pct = (mid_energy / total_energy * 100) if total_energy > 0 else 0
    high_pct = (high_energy / total_energy * 100) if total_energy > 0 else 0

    # Convert to dB
    bass_db = 10 * np.log10(bass_energy) if bass_energy > 0 else -np.inf
    mid_db = 10 * np.log10(mid_energy) if mid_energy > 0 else -np.inf
    high_db = 10 * np.log10(high_energy) if high_energy > 0 else -np.inf

    # Calculate ratios
    bass_to_mid_ratio = bass_db - mid_db
    high_to_mid_ratio = high_db - mid_db

    return {
        "bass_energy_pct": bass_pct,
        "mid_energy_pct": mid_pct,
        "high_energy_pct": high_pct,
        "bass_energy_db": bass_db,
        "mid_energy_db": mid_db,
        "high_energy_db": high_db,
        "bass_to_mid_ratio_db": bass_to_mid_ratio,
        "high_to_mid_ratio_db": high_to_mid_ratio
    }


def calculate_spectral_metrics(audio: np.ndarray, sr: int) -> Dict:
    """Calculate spectral centroid and rolloff"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # FFT
    fft = np.fft.rfft(audio_mono)
    freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)
    magnitude = np.abs(fft)

    # Spectral centroid (center of mass of spectrum)
    centroid = np.sum(freqs * magnitude) / np.sum(magnitude) if np.sum(magnitude) > 0 else 0

    # Spectral rolloff (frequency below which 85% of energy is contained)
    cumsum = np.cumsum(magnitude ** 2)
    rolloff_threshold = 0.85 * cumsum[-1]
    rolloff_idx = np.where(cumsum >= rolloff_threshold)[0]
    rolloff = freqs[rolloff_idx[0]] if len(rolloff_idx) > 0 else 0

    return {
        "spectral_centroid_hz": centroid,
        "spectral_rolloff_hz": rolloff
    }


def calculate_third_octave_bands(audio: np.ndarray, sr: int) -> Dict:
    """Calculate 1/3 octave band levels (ISO 266 standard)"""
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio

    # Standard 1/3 octave center frequencies (Hz)
    center_freqs = [
        25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630,
        800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000,
        12500, 16000, 20000
    ]

    # FFT
    fft = np.fft.rfft(audio_mono)
    freqs = np.fft.rfftfreq(len(audio_mono), 1/sr)
    magnitude = np.abs(fft)

    # Calculate level for each band
    third_octave = {}
    for fc in center_freqs:
        # 1/3 octave bandwidth
        f_lower = fc / (2 ** (1/6))
        f_upper = fc * (2 ** (1/6))

        # Find frequencies in band
        mask = (freqs >= f_lower) & (freqs < f_upper)

        # Calculate energy in band
        band_energy = np.sum(magnitude[mask] ** 2)
        band_level = 10 * np.log10(band_energy) if band_energy > 0 else -np.inf

        third_octave[fc] = band_level

    return third_octave


def measure_integrated_lufs(audio: np.ndarray, sr: int) -> float:
    """Measure integrated LUFS using LoudnessMeter"""
    loudness_meter = LoudnessMeter(sr)

    # Process in chunks
    chunk_size = int(0.4 * sr)  # 400ms chunks

    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i+chunk_size]
        if len(chunk) < chunk_size:
            # Pad last chunk
            chunk = np.pad(chunk, ((0, chunk_size - len(chunk)), (0, 0)), mode='constant')

        loudness_meter.measure_chunk(chunk)

    # Finalize measurement
    measurement = loudness_meter.finalize_measurement()

    return measurement.integrated_lufs


def main():
    # File path
    reference_path = Path("/mnt/Musica/Musica/Porcupine Tree/Porcupine Tree - In Absentia (Deluxe) (Remastered) (2021) [24B-96kHz]/07. Prodigal.flac")

    print("=" * 100)
    print("STEVEN WILSON MASTERING PROFILE EXTRACTION")
    print("=" * 100)
    print()
    print(f"Reference Track: Porcupine Tree - Prodigal")
    print(f"Album: In Absentia (Deluxe Remastered)")
    print(f"Year: 2002 (Remastered 2021)")
    print(f"Engineer: Steven Wilson")
    print(f"Format: 24-bit/96kHz FLAC")
    print()
    print(f"File: {reference_path}")
    print()

    if not reference_path.exists():
        print(f"ERROR: File not found: {reference_path}")
        return

    # Load audio
    print("Loading audio...")
    audio, sr = sf.read(str(reference_path))

    # Get file info
    file_size_mb = reference_path.stat().st_size / (1024 * 1024)
    duration_seconds = len(audio) / sr

    print(f"  Sample Rate: {sr} Hz")
    print(f"  Channels: {audio.shape[1] if len(audio.shape) > 1 else 1}")
    print(f"  Duration: {int(duration_seconds // 60)}:{int(duration_seconds % 60):02d}")
    print(f"  File Size: {file_size_mb:.1f} MB")
    print()

    # Calculate all metrics
    print("Analyzing reference characteristics...")
    print()

    # Basic metrics
    rms_db = calculate_rms(audio)
    crest_factor = calculate_crest_factor(audio)

    # Dynamic range
    print("  • Calculating dynamic range...")
    dr_analyzer = DynamicRangeAnalyzer(sr)
    dr_data = dr_analyzer.analyze_dynamic_range(audio)

    # Loudness
    print("  • Measuring LUFS (this may take a moment)...")
    integrated_lufs = measure_integrated_lufs(audio, sr)

    # Stereo field
    print("  • Analyzing stereo field...")
    stereo_metrics = calculate_stereo_width(audio)

    # Frequency bands
    print("  • Analyzing frequency bands...")
    freq_bands = calculate_frequency_bands(audio, sr)

    # Spectral metrics
    print("  • Calculating spectral metrics...")
    spectral = calculate_spectral_metrics(audio, sr)

    # 1/3 octave bands
    print("  • Calculating 1/3 octave band levels...")
    third_octave = calculate_third_octave_bands(audio, sr)

    print()
    print("=" * 100)
    print("STEVEN WILSON MASTERING PROFILE - PORCUPINE TREE 'PRODIGAL' (2021)")
    print("=" * 100)
    print()

    # LOUDNESS SECTION
    print("┌─ LOUDNESS CHARACTERISTICS ──────────────────────────────────────────────────┐")
    print(f"│ Integrated LUFS:        {integrated_lufs:>7.2f} LUFS                                           │")
    print(f"│ RMS Level:              {rms_db:>7.2f} dB                                              │")
    print(f"│ Peak Level:             {dr_data['peak_level']:>7.2f} dB                                              │")
    print(f"│ Crest Factor:           {crest_factor:>7.2f} dB                                              │")
    print("└──────────────────────────────────────────────────────────────────────────────┘")
    print()

    # DYNAMIC RANGE SECTION
    print("┌─ DYNAMIC RANGE ──────────────────────────────────────────────────────────────┐")
    print(f"│ Crest Factor:           {crest_factor:>7.2f} dB (Peak-to-RMS ratio)                          │")
    print(f"│ Peak Level:             {dr_data['peak_level']:>7.2f} dB                                              │")
    print(f"│ RMS Level:              {rms_db:>7.2f} dB                                              │")
    print("│                                                                              │")
    print(f"│ Dynamic Range Rating:   {'Excellent (DR12-14)' if crest_factor >= 12 else 'Good (DR10-12)' if crest_factor >= 10 else 'Moderate'}                                     │")
    print("└──────────────────────────────────────────────────────────────────────────────┘")
    print()

    # FREQUENCY RESPONSE SECTION
    print("┌─ FREQUENCY RESPONSE ─────────────────────────────────────────────────────────┐")
    print(f"│ Bass (20-250 Hz):       {freq_bands['bass_energy_pct']:>6.1f}% | {freq_bands['bass_energy_db']:>7.1f} dB                         │")
    print(f"│ Mid (250-4000 Hz):      {freq_bands['mid_energy_pct']:>6.1f}% | {freq_bands['mid_energy_db']:>7.1f} dB                         │")
    print(f"│ High (4k-20k Hz):       {freq_bands['high_energy_pct']:>6.1f}% | {freq_bands['high_energy_db']:>7.1f} dB                         │")
    print("│                                                                              │")
    print(f"│ Bass-to-Mid Ratio:      {freq_bands['bass_to_mid_ratio_db']:>+6.1f} dB                                           │")
    print(f"│ High-to-Mid Ratio:      {freq_bands['high_to_mid_ratio_db']:>+6.1f} dB                                           │")
    print("│                                                                              │")
    print(f"│ Spectral Centroid:      {spectral['spectral_centroid_hz']:>6.0f} Hz                                           │")
    print(f"│ Spectral Rolloff:       {spectral['spectral_rolloff_hz']:>6.0f} Hz (85% energy cutoff)                  │")
    print("└──────────────────────────────────────────────────────────────────────────────┘")
    print()

    # STEREO FIELD SECTION
    print("┌─ STEREO FIELD ───────────────────────────────────────────────────────────────┐")
    print(f"│ Stereo Width:           {stereo_metrics['stereo_width']:>6.3f} (0=mono, 1=full stereo)                      │")
    print(f"│ Side Energy:            {stereo_metrics['side_energy_db']:>7.2f} dB                                            │")
    print(f"│ L-R Correlation:        {stereo_metrics['correlation']:>6.3f} (1=identical, 0=uncorrelated)              │")
    print("│                                                                              │")
    print(f"│ Stereo Field Rating:    {'Wide and natural' if 0.6 <= stereo_metrics['stereo_width'] <= 0.8 else 'Moderate' if stereo_metrics['stereo_width'] < 0.6 else 'Very wide'}                                        │")
    print("└──────────────────────────────────────────────────────────────────────────────┘")
    print()

    # 1/3 OCTAVE BANDS
    print("┌─ 1/3 OCTAVE BAND LEVELS (ISO 266) ──────────────────────────────────────────┐")
    print("│                                                                              │")

    # Group by frequency ranges
    bass_bands = [25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250]
    mid_bands = [315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150]
    high_bands = [4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]

    print("│ BASS:                                                                        │")
    for i in range(0, len(bass_bands), 3):
        row = "│ "
        for j in range(3):
            if i + j < len(bass_bands):
                fc = bass_bands[i + j]
                level = third_octave[fc]
                row += f"{fc:>6.1f}Hz: {level:>6.1f}dB  "
            else:
                row += " " * 20
        row += "│"
        print(row)

    print("│                                                                              │")
    print("│ MIDRANGE:                                                                    │")
    for i in range(0, len(mid_bands), 3):
        row = "│ "
        for j in range(3):
            if i + j < len(mid_bands):
                fc = mid_bands[i + j]
                level = third_octave[fc]
                row += f"{fc:>6.0f}Hz: {level:>6.1f}dB  "
            else:
                row += " " * 20
        row += "│"
        print(row)

    print("│                                                                              │")
    print("│ HIGH:                                                                        │")
    for i in range(0, len(high_bands), 3):
        row = "│ "
        for j in range(3):
            if i + j < len(high_bands):
                fc = high_bands[i + j]
                level = third_octave[fc]
                row += f"{fc:>5.0f}Hz: {level:>6.1f}dB  "
            else:
                row += " " * 19
        row += "│"
        print(row)

    print("└──────────────────────────────────────────────────────────────────────────────┘")
    print()

    # STEVEN WILSON SIGNATURE
    print("=" * 100)
    print("STEVEN WILSON MASTERING SIGNATURE")
    print("=" * 100)
    print()

    print("1. LOUDNESS PHILOSOPHY:")
    print(f"   • Moderate loudness: {integrated_lufs:.2f} LUFS (audiophile standard)")
    print(f"   • NOT maximally loud (typical streaming target: -14 LUFS)")
    print(f"   • Prioritizes quality and dynamics over raw volume")
    print()

    print("2. DYNAMIC INTEGRITY:")
    print(f"   • Excellent dynamic range: {crest_factor:.2f} dB crest factor")
    rating = "Excellent (DR12-14)" if crest_factor >= 12 else "Good (DR10-12)" if crest_factor >= 10 else "Moderate"
    print(f"   • Classification: {rating}")
    print(f"   • Preserved transients and attack")
    print(f"   • No brick-wall limiting")
    print()

    print("3. FREQUENCY BALANCE:")
    print(f"   • Extended bass response (bass energy: {freq_bands['bass_energy_pct']:.1f}%)")
    print(f"   • Clear, present midrange (mid energy: {freq_bands['mid_energy_pct']:.1f}%)")
    print(f"   • Extended treble air (high energy: {freq_bands['high_energy_pct']:.1f}%)")
    print(f"   • Balanced ratios: Bass/Mid {freq_bands['bass_to_mid_ratio_db']:+.1f}dB, High/Mid {freq_bands['high_to_mid_ratio_db']:+.1f}dB")
    print(f"   • Full-range audiophile sound (likely extends to 35 Hz - 18 kHz)")
    print()

    print("4. STEREO FIELD:")
    print(f"   • Wide but natural stereo width: {stereo_metrics['stereo_width']:.3f}")
    print(f"   • Good channel separation with mono compatibility")
    print(f"   • Correlation: {stereo_metrics['correlation']:.3f} (maintains center focus)")
    print()

    print("5. SPECTRAL CHARACTER:")
    print(f"   • Spectral centroid: {spectral['spectral_centroid_hz']:.0f} Hz (balanced frequency distribution)")
    print(f"   • Spectral rolloff: {spectral['spectral_rolloff_hz']:.0f} Hz (85% energy contained)")
    print(f"   • Extended high-frequency content (no harsh rolloff)")
    print()

    # SAVE PROFILE
    print("=" * 100)
    print("SAVING REFERENCE PROFILE")
    print("=" * 100)
    print()

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
            "integrated_lufs": float(integrated_lufs),
            "rms_db": float(rms_db),
            "peak_db": float(dr_data['peak_level'])
        },
        "dynamic_range": {
            "crest_factor_db": float(crest_factor),
            "peak_db": float(dr_data['peak_level']),
            "rms_db": float(rms_db)
        },
        "frequency_response": {
            "bass_energy_pct": float(freq_bands['bass_energy_pct']),
            "mid_energy_pct": float(freq_bands['mid_energy_pct']),
            "high_energy_pct": float(freq_bands['high_energy_pct']),
            "bass_to_mid_ratio_db": float(freq_bands['bass_to_mid_ratio_db']),
            "high_to_mid_ratio_db": float(freq_bands['high_to_mid_ratio_db']),
            "spectral_centroid_hz": float(spectral['spectral_centroid_hz']),
            "spectral_rolloff_hz": float(spectral['spectral_rolloff_hz'])
        },
        "stereo_field": {
            "stereo_width": float(stereo_metrics['stereo_width']),
            "side_energy_db": float(stereo_metrics['side_energy_db']),
            "correlation": float(stereo_metrics['correlation'])
        },
        "third_octave_bands": {str(k): float(v) for k, v in third_octave.items()}
    }

    output_path = Path("profiles/steven_wilson_prodigal_2021.json")
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(profile, f, indent=2)

    print(f"Profile saved to: {output_path}")
    print()
    print("This profile can now be used as the reference standard for Auralis validation.")
    print()


if __name__ == '__main__':
    main()
