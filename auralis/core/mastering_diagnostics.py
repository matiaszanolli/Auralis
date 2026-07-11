"""
Mastering Diagnostics
~~~~~~~~~~~~~~~~~~~~~

Verbose/development-only console output for SimpleMasteringPipeline:
fingerprint summaries and per-step timing breakdowns.

Extracted from simple_mastering.py (#4072) — pure stdout printing, no audio
or state involved.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


def print_fingerprint(fp: dict) -> None:
    """Print key fingerprint metrics organized by category."""
    print(f"\n📊 Fingerprint (25D):")

    # Dynamics (3D) - Critical for loudness/compression decisions
    lufs = fp.get('lufs', -14.0)
    crest_db = fp.get('crest_db', 12.0)
    bass_mid_ratio = fp.get('bass_mid_ratio', 0.0)

    # Classify material type based on LUFS + Crest
    if lufs > -12.0 and crest_db < 13.0:
        if crest_db < 8.0:
            material_type = "Hyper-compressed loud"
        else:
            material_type = "Compressed loud"
    elif lufs > -12.0:
        material_type = "Dynamic loud"
    else:
        material_type = "Quiet"

    print(f"   🔊 Dynamics: {material_type}")
    print(f"      LUFS: {lufs:.1f} dB  │  Crest: {crest_db:.1f} dB  │  Bass/Mid: {bass_mid_ratio:.2f}")

    # Frequency (7D) - Spectral balance
    sub_bass_pct = fp.get('sub_bass_pct', 0.05)
    bass_pct = fp.get('bass_pct', 0.15)
    low_mid_pct = fp.get('low_mid_pct', 0.10)
    mid_pct = fp.get('mid_pct', 0.20)
    upper_mid_pct = fp.get('upper_mid_pct', 0.25)
    presence_pct = fp.get('presence_pct', 0.15)
    air_pct = fp.get('air_pct', 0.10)

    print(f"   🎚️  Frequency Balance:")
    print(f"      Sub: {sub_bass_pct:.0%}  │  Bass: {bass_pct:.0%}  │  Lo-Mid: {low_mid_pct:.0%}  │  Mid: {mid_pct:.0%}")
    print(f"      Up-Mid: {upper_mid_pct:.0%}  │  Presence: {presence_pct:.0%}  │  Air: {air_pct:.0%}")

    # Temporal (4D) - Rhythm and dynamics
    tempo_bpm = fp.get('tempo_bpm', 120.0)
    rhythm_stability = fp.get('rhythm_stability', 0.5)
    transient_density = fp.get('transient_density', 0.5)
    silence_ratio = fp.get('silence_ratio', 0.0)

    print(f"   🥁 Temporal:")
    print(f"      Tempo: {tempo_bpm:.0f} BPM  │  Rhythm: {rhythm_stability:.0%}  │  Transients: {transient_density:.0%}  │  Silence: {silence_ratio:.0%}")

    # Spectral (3D) - Brightness and noise characteristics
    spectral_centroid = fp.get('spectral_centroid', 0.5)
    spectral_rolloff = fp.get('spectral_rolloff', 0.5)
    spectral_flatness = fp.get('spectral_flatness', 0.5)

    # Interpret brightness
    if spectral_centroid > 0.6 and spectral_rolloff > 0.6:
        brightness = "Bright"
    elif spectral_centroid < 0.4 and spectral_rolloff < 0.4:
        brightness = "Dark"
    else:
        brightness = "Neutral"

    print(f"   ✨ Spectral: {brightness}")
    print(f"      Centroid: {spectral_centroid:.0%}  │  Rolloff: {spectral_rolloff:.0%}  │  Flatness: {spectral_flatness:.0%}")

    # Harmonic (3D) - Tonality
    harmonic_ratio = fp.get('harmonic_ratio', 0.5)
    pitch_stability = fp.get('pitch_stability', 0.5)
    chroma_energy = fp.get('chroma_energy', 0.5)

    # Classify harmonic content
    avg_harmonic = (harmonic_ratio + pitch_stability) / 2
    if avg_harmonic > 0.7:
        tonality = "Highly tonal"
    elif avg_harmonic > 0.5:
        tonality = "Tonal"
    elif avg_harmonic > 0.3:
        tonality = "Mixed"
    else:
        tonality = "Percussive/Noisy"

    print(f"   🎼 Harmonic: {tonality}")
    print(f"      Harmonic: {harmonic_ratio:.0%}  │  Pitch: {pitch_stability:.0%}  │  Chroma: {chroma_energy:.0%}")

    # Stereo (2D)
    stereo_width = fp.get('stereo_width', 0.5)
    phase_correlation = fp.get('phase_correlation', 1.0)

    # Classify stereo field
    if stereo_width < 0.3:
        stereo_type = "Narrow"
    elif stereo_width < 0.6:
        stereo_type = "Normal"
    else:
        stereo_type = "Wide"

    print(f"   🎧 Stereo: {stereo_type}")
    print(f"      Width: {stereo_width:.0%}  │  Phase Corr: {phase_correlation:.2f}")

    # Variation (3D) - Consistency metrics
    dynamic_range_variation = fp.get('dynamic_range_variation', 0.5)
    loudness_variation_std = fp.get('loudness_variation_std', 0.0)
    peak_consistency = fp.get('peak_consistency', 0.5)

    print(f"   📊 Variation:")
    print(f"      DR Var: {dynamic_range_variation:.0%}  │  Loudness σ: {loudness_variation_std:.1f}  │  Peak Cons: {peak_consistency:.0%}")


def print_time_metrics(timings: dict[str, float], duration_sec: float) -> None:
    """Print detailed timing breakdown (development only)."""
    print("\n⏱️  Time Metrics:")
    print("   ─────────────────────────────────────")

    # Individual steps
    for step, elapsed in timings.items():
        if step == 'total':
            continue
        pct = (elapsed / timings['total']) * 100
        print(f"   {step:<15} {elapsed:>7.2f}s  ({pct:>5.1f}%)")

    print("   ─────────────────────────────────────")
    print(f"   {'TOTAL':<15} {timings['total']:>7.2f}s  (100.0%)")

    # Real-time ratio
    realtime_ratio = duration_sec / timings['total']
    print(f"\n   Audio duration: {duration_sec:.1f}s")
    print(f"   Real-time ratio: {realtime_ratio:.1f}x")
