"""
Mastering Diagnostics
~~~~~~~~~~~~~~~~~~~~~

Verbose/development-only console output for SimpleMasteringPipeline:
fingerprint summaries and per-step timing breakdowns.

Extracted from simple_mastering.py (#4072) — pure stdout printing, no audio
or state involved.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

from .utils.fingerprint_unpacker import FingerprintUnpacker


def print_fingerprint(fp: dict[str, Any]) -> None:
    """Print key fingerprint metrics organized by measurement group."""
    print("\n📊 Fingerprint (25D):")
    u = FingerprintUnpacker.from_dict(fp)

    # Dynamics (3D) - Critical for loudness/compression decisions
    lufs = u.lufs
    crest_db = u.crest_db
    bass_mid_ratio = u.bass_mid_ratio

    print("   🔊 Dynamics:")
    print(f"      LUFS: {lufs:.1f} dB  │  Crest: {crest_db:.1f} dB  │  Bass/Mid: {bass_mid_ratio:.2f}")

    # Frequency (7D) - Spectral balance
    sub_bass_pct = u.sub_bass_pct
    bass_pct = u.bass_pct
    low_mid_pct = u.low_mid_pct
    mid_pct = u.mid_pct
    upper_mid_pct = u.upper_mid_pct
    presence_pct = u.presence_pct
    air_pct = u.air_pct

    print("   🎚️  Frequency Balance:")
    print(f"      Sub: {sub_bass_pct:.0%}  │  Bass: {bass_pct:.0%}  │  Lo-Mid: {low_mid_pct:.0%}  │  Mid: {mid_pct:.0%}")
    print(f"      Up-Mid: {upper_mid_pct:.0%}  │  Presence: {presence_pct:.0%}  │  Air: {air_pct:.0%}")

    # Temporal (4D) - Rhythm and dynamics
    tempo_bpm = u.tempo_bpm
    rhythm_stability = u.rhythm_stability
    transient_density = u.transient_density
    silence_ratio = u.silence_ratio

    print("   🥁 Temporal:")
    print(f"      Tempo: {tempo_bpm:.0f} BPM  │  Rhythm: {rhythm_stability:.0%}  │  Transients: {transient_density:.0%}  │  Silence: {silence_ratio:.0%}")

    # Spectral (3D) - Brightness and noise characteristics
    spectral_centroid = u.spectral_centroid
    spectral_rolloff = u.spectral_rolloff
    spectral_flatness = u.spectral_flatness

    print("   ✨ Spectral:")
    print(f"      Centroid: {spectral_centroid:.0%}  │  Rolloff: {spectral_rolloff:.0%}  │  Flatness: {spectral_flatness:.0%}")

    # Harmonic (3D) - Tonality
    harmonic_ratio = u.harmonic_ratio
    pitch_stability = u.pitch_stability
    chroma_energy = u.chroma_energy

    print("   🎼 Harmonic:")
    print(f"      Harmonic: {harmonic_ratio:.0%}  │  Pitch: {pitch_stability:.0%}  │  Chroma: {chroma_energy:.0%}")

    # Stereo (2D)
    stereo_width = u.stereo_width
    phase_correlation = u.phase_correlation

    print("   🎧 Stereo:")
    print(f"      Width: {stereo_width:.0%}  │  Phase Corr: {phase_correlation:.2f}")

    # Variation (3D) - Consistency metrics
    dynamic_range_variation = u.dynamic_range_variation
    loudness_variation_std = u.loudness_variation_std
    peak_consistency = u.peak_consistency

    print("   📊 Variation:")
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


def print_quality_evaluation(evaluation: dict[str, Any]) -> None:
    """Print continuous before/after measurements without a verdict."""
    before = evaluation.get('overall_score_before', 0.0)
    after = evaluation.get('overall_score_after', 0.0)
    print("\n📈 Before/after measurements (advisory only)")
    print(f"   Overall score: {before:.1f} → {after:.1f} ({after - before:+.1f})")

    for name, dimension in evaluation.get('dimensions', {}).items():
        print(
            f"   {name}: {dimension.get('before_score', 0.0):.1f} → "
            f"{dimension.get('after_score', 0.0):.1f} "
            f"({dimension.get('score_change', 0.0):+.1f})"
        )

    true_peak = evaluation.get('max_true_peak_after_dbfs')
    if true_peak is not None:
        print(f"   Maximum measured output True Peak: {true_peak:.2f} dBFS")
    print(
        "   Sample-count change: "
        f"{int(evaluation.get('sample_count_change', 0)):+d}"
    )
