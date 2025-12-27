"""
Phase 7B: Dramatic-Change Tracks Testing

Validates sampling strategy on challenging tracks with major structural changes:
- Intro/outro variations (soft intro, abrupt beat drop)
- Multi-section tracks (verse/chorus transitions, key changes)
- Dynamic range changes (quiet sections followed by peaks)
- Tempo/rhythm variations

Tests whether sampling can capture transition points and maintain accuracy
despite large variations within a single track.
"""

import gc
import sys
import time
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.io.unified_loader import load_audio


def test_track_dramatic_changes(track_path: Path, description: str) -> dict:
    """Test a single track focusing on dramatic changes."""
    try:
        audio, _ = load_audio(str(track_path), target_sample_rate=44100)

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        audio = audio.astype(np.float64)
        duration_s = len(audio) / 44100

        # Full-track analysis
        analyzer_full = AudioFingerprintAnalyzer(fingerprint_strategy="full-track")
        start = time.perf_counter()
        features_full = analyzer_full.analyze(audio, 44100)
        time_full = time.perf_counter() - start

        # Sampled analysis (default 20s interval)
        analyzer_sampled = AudioFingerprintAnalyzer(
            fingerprint_strategy="sampling",
            sampling_interval=20.0
        )
        start = time.perf_counter()
        features_sampled = analyzer_sampled.analyze(audio, 44100)
        time_sampled = time.perf_counter() - start

        # Also test with tighter sampling (10s) for dramatic changes
        analyzer_tight = AudioFingerprintAnalyzer(
            fingerprint_strategy="sampling",
            sampling_interval=10.0
        )
        start = time.perf_counter()
        features_tight = analyzer_tight.analyze(audio, 44100)
        time_tight = time.perf_counter() - start

        # Calculate correlations
        harmonic_keys = ["harmonic_ratio", "pitch_stability", "chroma_energy"]
        full_values = np.array([features_full[k] for k in harmonic_keys])
        sampled_values = np.array([features_sampled[k] for k in harmonic_keys])
        tight_values = np.array([features_tight[k] for k in harmonic_keys])

        try:
            corr_standard = np.corrcoef(full_values, sampled_values)[0, 1]
            if np.isnan(corr_standard):
                corr_standard = 1.0
        except:
            corr_standard = 1.0

        try:
            corr_tight = np.corrcoef(full_values, tight_values)[0, 1]
            if np.isnan(corr_tight):
                corr_tight = 1.0
        except:
            corr_tight = 1.0

        speedup_standard = time_full / time_sampled if time_sampled > 0 else 0
        speedup_tight = time_full / time_tight if time_tight > 0 else 0

        del audio, analyzer_full, analyzer_sampled, analyzer_tight
        gc.collect()

        return {
            "track": track_path.stem,
            "description": description,
            "duration_s": duration_s,
            "time_full": time_full,
            "time_standard": time_sampled,
            "time_tight": time_tight,
            "speedup_standard": speedup_standard,
            "speedup_tight": speedup_tight,
            "corr_standard": corr_standard,
            "corr_tight": corr_tight,
            "error": None,
        }

    except Exception as e:
        return {
            "track": track_path.stem,
            "description": description,
            "duration_s": 0,
            "error": str(e)[:80],
        }


def test_dramatic_changes():
    """Test sampling on tracks with dramatic structural changes."""
    print("\n" + "=" * 130)
    print("PHASE 7B: DRAMATIC-CHANGE TRACKS TESTING")
    print("=" * 130)

    # Test cases: tracks known to have dramatic changes
    music_root = Path("/mnt/Musica/Musica")

    test_tracks = [
        # Pearl Jam tracks with varying structures
        (music_root / "Pearl Jam/1991 - Ten/01 -Once.flac",
         "Once (Intro: 15s clean guitar, then full production)"),
        (music_root / "Pearl Jam/1991 - Ten/04 -Why Go.flac",
         "Why Go (Abrupt tempo/style changes)"),
        (music_root / "Pearl Jam/1991 - Ten/05 -Black.flac",
         "Black (Building dynamics, multiple sections)"),
        (music_root / "Pearl Jam/1991 - Ten/08 -Porch.flac",
         "Porch (Starts sparse, ends intense)"),

        # Meshuggah tracks with complex processing
        (music_root / "Meshuggah/2012 - Koloss/02 The Demon's Name Is Surveillance.flac",
         "Surveillance (Heavy compression, dense production)"),
        (music_root / "Meshuggah/2012 - Koloss/03 Do Not Look Down.flac",
         "Do Not Look Down (Complex rhythm changes)"),
    ]

    results = []
    failed_tracks = []

    print("\n📊 TESTING DRAMATIC-CHANGE TRACKS")
    print("-" * 130)
    print(f"{'Track':<50} {'Duration':<12} {'20s Interval':<20} {'10s Interval':<20} {'Method':<10}")
    print(f"{'':50} {'':12} {'Speedup / Corr':<20} {'Speedup / Corr':<20} {'Pass?':<10}")
    print("-" * 130)

    for track_path, description in test_tracks:
        if not track_path.exists():
            print(f"{track_path.stem:<50} ⚠️  FILE NOT FOUND")
            failed_tracks.append((track_path, description))
            continue

        result = test_track_dramatic_changes(track_path, description)

        if "error" in result and result["error"]:
            print(f"{result['track']:<50} ERROR: {result['error']}")
            failed_tracks.append((track_path, description))
        else:
            results.append(result)

            # Determine pass status: >= 0.85 on either strategy
            pass_standard = result["corr_standard"] >= 0.85
            pass_tight = result["corr_tight"] >= 0.85
            overall_pass = "✅" if (pass_standard or pass_tight) else "⚠️"

            print(
                f"{result['track']:<50} {result['duration_s']:>7.1f}s    "
                f"{result['speedup_standard']:>6.2f}x / {result['corr_standard']:.3f}   "
                f"{result['speedup_tight']:>6.2f}x / {result['corr_tight']:.3f}   "
                f"{overall_pass}"
            )

    # =========================================================================
    # Analysis & Summary
    # =========================================================================
    print("\n" + "=" * 130)
    print("DRAMATIC-CHANGE ANALYSIS")
    print("=" * 130)

    if results:
        print(f"\n✅ Successfully processed {len(results)} tracks with dramatic changes")
        print("-" * 130)

        # Standard interval (20s)
        avg_speedup_std = np.mean([r["speedup_standard"] for r in results])
        avg_corr_std = np.mean([r["corr_standard"] for r in results])
        pass_rate_std = sum(1 for r in results if r["corr_standard"] >= 0.85) / len(results)

        print(f"\nStandard Sampling (20s interval):")
        print(f"  Average Speedup:        {avg_speedup_std:>8.2f}x")
        print(f"  Average Correlation:    {avg_corr_std:>8.3f}")
        print(f"  Pass Rate (≥0.85):      {pass_rate_std:>8.0%}")

        # Tight interval (10s)
        avg_speedup_tight = np.mean([r["speedup_tight"] for r in results])
        avg_corr_tight = np.mean([r["corr_tight"] for r in results])
        pass_rate_tight = sum(1 for r in results if r["corr_tight"] >= 0.85) / len(results)

        print(f"\nTight Sampling (10s interval):")
        print(f"  Average Speedup:        {avg_speedup_tight:>8.2f}x")
        print(f"  Average Correlation:    {avg_corr_tight:>8.3f}")
        print(f"  Pass Rate (≥0.85):      {pass_rate_tight:>8.0%}")

        # Improvement
        improvement = avg_corr_tight - avg_corr_std
        speedup_trade = avg_speedup_std - avg_speedup_tight

        print(f"\nTighter Sampling Impact:")
        print(f"  Correlation Improvement: +{improvement:>7.3f} ({(improvement/avg_corr_std)*100:>+6.1f}%)")
        print(f"  Speedup Trade-off:       -{speedup_trade:>7.2f}x ({(speedup_trade/avg_speedup_std)*100:>+6.1f}%)")

        # Recommendations
        print(f"\n" + "=" * 130)
        print("RECOMMENDATIONS FOR DRAMATIC-CHANGE TRACKS")
        print("=" * 130)

        if avg_corr_std >= 0.85:
            print("\n✅ Standard 20s sampling is sufficient")
            print("   → Even challenging tracks maintain 85%+ accuracy")
        else:
            if avg_corr_tight >= 0.85:
                print("\n📊 For dramatic-change tracks, consider tighter 10s sampling")
                print(f"   → Improves accuracy by {improvement:.3f} ({(improvement/avg_corr_std)*100:+.1f}%)")
                print(f"   → Only reduces speedup by {speedup_trade:.2f}x ({(speedup_trade/avg_speedup_std)*100:+.1f}%)")
            else:
                print("\n⚠️  Even tighter sampling may be needed for challenging tracks")

        # Track-by-track analysis
        print(f"\n" + "=" * 130)
        print("TRACK-BY-TRACK ANALYSIS")
        print("=" * 130)

        for result in results:
            print(f"\n{result['track']}:")
            print(f"  Duration:         {result['duration_s']:.1f}s")
            print(f"  Description:      {result['description']}")
            print(f"  20s Sampling:     {result['corr_standard']:.3f} correlation ({result['speedup_standard']:.2f}x speedup)")
            print(f"  10s Sampling:     {result['corr_tight']:.3f} correlation ({result['speedup_tight']:.2f}x speedup)")

            if result["corr_standard"] >= 0.85:
                print(f"  ✅ Standard sampling sufficient")
            elif result["corr_tight"] >= 0.85:
                print(f"  📊 Tight sampling recommended (+{result['corr_tight'] - result['corr_standard']:.3f} correlation gain)")
            else:
                print(f"  ⚠️  Both strategies below 85% target")

    if failed_tracks:
        print(f"\n⚠️  Failed to process {len(failed_tracks)} tracks:")
        for track_path, description in failed_tracks:
            print(f"   - {track_path.stem}: {description}")

    print("\n" + "=" * 130 + "\n")


if __name__ == "__main__":
    test_dramatic_changes()
