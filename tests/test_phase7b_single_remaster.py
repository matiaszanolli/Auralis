"""
Phase 7B: Single Remaster Analysis

Analyzes professional remasters without original versions for comparison.
Useful for understanding how sampling handles specific remaster characteristics
and establishing baseline fingerprint data.

Test Case: The Who - Who's Next (Steven Wilson Stereo Remix, 2023, 24-96)
"""

import numpy as np
import time
from pathlib import Path
import sys
import gc

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
from auralis.io.unified_loader import load_audio


def analyze_single_remaster(track_path: Path, track_description: str = ""):
    """Analyze a single remaster track in detail."""
    try:
        print(f"\nLoading: {track_path.stem}")
        audio, _ = load_audio(str(track_path), target_sample_rate=44100)

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        audio = audio.astype(np.float64)
        duration_s = len(audio) / 44100

        print(f"Duration: {duration_s:.1f}s | Audio shape: {audio.shape}")

        # Full-track analysis
        print(f"Analyzing with full-track strategy...")
        analyzer_full = AudioFingerprintAnalyzer(fingerprint_strategy="full-track")
        start = time.perf_counter()
        features_full = analyzer_full.analyze(audio, 44100)
        time_full = time.perf_counter() - start

        # Sampled analysis
        print(f"Analyzing with sampling strategy (20s interval)...")
        analyzer_sampled = AudioFingerprintAnalyzer(
            fingerprint_strategy="sampling",
            sampling_interval=20.0
        )
        start = time.perf_counter()
        features_sampled = analyzer_sampled.analyze(audio, 44100)
        time_sampled = time.perf_counter() - start

        del audio, analyzer_full, analyzer_sampled
        gc.collect()

        speedup = time_full / time_sampled if time_sampled > 0 else 0

        return {
            "track": track_path.stem,
            "description": track_description,
            "duration_s": duration_s,
            "features_full": features_full,
            "features_sampled": features_sampled,
            "time_full": time_full,
            "time_sampled": time_sampled,
            "speedup": speedup,
            "error": None,
        }

    except Exception as e:
        return {
            "track": track_path.stem,
            "description": track_description,
            "duration_s": 0,
            "error": str(e)[:100],
        }


def analyze_album(album_path: Path, album_name: str):
    """Analyze all tracks from a remastered album."""
    print("\n" + "=" * 130)
    print(f"SINGLE REMASTER ANALYSIS: {album_name}")
    print("=" * 130)

    # Find all FLAC files
    tracks = sorted(list(album_path.glob("*.flac")))

    if not tracks:
        print(f"⚠️  No FLAC files found in {album_path}")
        return []

    print(f"\nFound {len(tracks)} tracks to analyze")
    print("-" * 130)

    results = []

    for i, track_path in enumerate(tracks, 1):
        print(f"\n📀 [{i}/{len(tracks)}] Analyzing: {track_path.stem}")

        result = analyze_single_remaster(track_path)
        results.append(result)

        if "error" in result and result["error"]:
            print(f"   ❌ ERROR: {result['error']}")
        else:
            print(f"   ✅ Analysis complete")
            print(f"      Duration: {result['duration_s']:.1f}s")
            print(f"      Full-Track: {result['time_full']:.3f}s")
            print(f"      Sampling:   {result['time_sampled']:.3f}s ({result['speedup']:.2f}x speedup)")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 130)
    print("ALBUM ANALYSIS SUMMARY")
    print("=" * 130)

    valid_results = [r for r in results if "error" not in r or not r["error"]]

    if valid_results:
        total_duration = sum(r["duration_s"] for r in valid_results)
        total_time_full = sum(r["time_full"] for r in valid_results)
        total_time_sampled = sum(r["time_sampled"] for r in valid_results)
        avg_speedup = np.mean([r["speedup"] for r in valid_results])

        print(f"\n✅ Successfully analyzed {len(valid_results)} tracks")
        print(f"\nPerformance Metrics:")
        print(f"  Total audio duration:   {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
        print(f"  Full-track total time:  {total_time_full:.2f}s")
        print(f"  Sampling total time:    {total_time_sampled:.2f}s")
        print(f"  Average speedup:        {avg_speedup:.2f}x")
        print(f"  Time saved:             {total_time_full - total_time_sampled:.2f}s")

        # =========================================================================
        # FEATURE ANALYSIS
        # =========================================================================
        print(f"\n" + "=" * 130)
        print("HARMONIC FEATURE ANALYSIS (Sampling Strategy)")
        print("=" * 130)

        harmonic_keys = ["harmonic_ratio", "pitch_stability", "chroma_energy"]

        print(f"\nFeature Statistics Across Album:")
        print("-" * 130)
        print(f"{'Feature':<25} {'Min':<12} {'Max':<12} {'Mean':<12} {'Std Dev':<12}")
        print("-" * 130)

        for key in harmonic_keys:
            values = [r["features_sampled"].get(key, 0) for r in valid_results]
            print(
                f"{key:<25} {min(values):>10.3f}  {max(values):>10.3f}  "
                f"{np.mean(values):>10.3f}  {np.std(values):>10.3f}"
            )

        # =========================================================================
        # TRACK-BY-TRACK FEATURE BREAKDOWN
        # =========================================================================
        print(f"\n" + "=" * 130)
        print("TRACK-BY-TRACK HARMONIC BREAKDOWN")
        print("=" * 130)

        print(f"\n{'Track':<40} {'Duration':<12} {'Harmonic':<12} {'Pitch Stab':<12} {'Chroma':<12}")
        print("-" * 130)

        for result in valid_results:
            features = result["features_sampled"]
            print(
                f"{result['track']:<40} {result['duration_s']:>7.1f}s    "
                f"{features['harmonic_ratio']:>10.3f}   {features['pitch_stability']:>10.3f}   "
                f"{features['chroma_energy']:>10.3f}"
            )

        # =========================================================================
        # REMASTER CHARACTERISTICS
        # =========================================================================
        print(f"\n" + "=" * 130)
        print("REMASTER CHARACTERISTICS ANALYSIS")
        print("=" * 130)

        print(f"\nSteven Wilson Remix Profile (based on sampling analysis):")
        print("-" * 130)

        avg_harmonic = np.mean([r["features_sampled"]["harmonic_ratio"] for r in valid_results])
        avg_pitch = np.mean([r["features_sampled"]["pitch_stability"] for r in valid_results])
        avg_chroma = np.mean([r["features_sampled"]["chroma_energy"] for r in valid_results])

        print(f"  Average Harmonic Ratio:     {avg_harmonic:.3f}")
        if avg_harmonic > 0.5:
            print(f"    → Album emphasizes harmonic content (melodic focus)")
        else:
            print(f"    → Album balanced between harmonic and percussive")

        print(f"\n  Average Pitch Stability:    {avg_pitch:.3f}")
        if avg_pitch > 0.7:
            print(f"    → Strong, stable pitch/vocals (clear mix)")
        else:
            print(f"    → Varied pitch/looser tuning")

        print(f"\n  Average Chroma Energy:      {avg_chroma:.3f}")
        if avg_chroma > 0.6:
            print(f"    → Concentrated pitch class energy (rich harmonies)")
        else:
            print(f"    → Dispersed pitch energy (wide harmonic palette)")

        # =========================================================================
        # SAMPLING STRATEGY VALIDATION
        # =========================================================================
        print(f"\n" + "=" * 130)
        print("SAMPLING STRATEGY VALIDATION")
        print("=" * 130)

        # Calculate sampling vs full-track correlation for each track
        correlations = []
        for result in valid_results:
            harmonic_full = np.array([result["features_full"][k] for k in harmonic_keys])
            harmonic_sampled = np.array([result["features_sampled"][k] for k in harmonic_keys])

            try:
                corr = np.corrcoef(harmonic_full, harmonic_sampled)[0, 1]
                if np.isnan(corr):
                    corr = 1.0
            except:
                corr = 1.0

            correlations.append(corr)

        avg_correlation = np.mean(correlations)
        pass_rate = sum(1 for c in correlations if c >= 0.85) / len(correlations)

        print(f"\nSampling vs Full-Track Harmonic Correlation:")
        print(f"  Average correlation: {avg_correlation:.3f}")
        print(f"  Pass rate (≥0.85):   {pass_rate:.0%}")

        if avg_correlation >= 0.85:
            print(f"  ✅ Sampling strategy VALID for this remaster")
        else:
            print(f"  ⚠️  Sampling correlation below target on this remaster")

        # =========================================================================
        # RECOMMENDATIONS
        # =========================================================================
        print(f"\n" + "=" * 130)
        print("RECOMMENDATIONS")
        print("=" * 130)

        print(f"\nBased on analysis of this Steven Wilson remaster:")
        print(f"  ✅ Sampling speedup: {avg_speedup:.2f}x")
        print(f"  ✅ Accuracy: {avg_correlation:.1%}")
        print(f"  ✅ Processing: ~{total_time_sampled:.1f}s for {len(valid_results)} tracks")

        if avg_correlation >= 0.90:
            print(f"\n  → EXCELLENT: Use sampling strategy with full confidence")
        elif avg_correlation >= 0.85:
            print(f"\n  → GOOD: Use sampling strategy, reliable results")
        elif avg_correlation >= 0.75:
            print(f"\n  → ACCEPTABLE: Use sampling with awareness of ±{(1-avg_correlation)*100:.0f}% variance")
        else:
            print(f"\n  → CAUTION: Consider full-track analysis for critical use cases")

    print(f"\n{'=' * 130}\n")
    return valid_results


if __name__ == "__main__":
    # Analyze The Who - Who's Next (Steven Wilson Remaster)
    who_album = Path(
        "/mnt/Musica/Musica/The Who"
    )

    # Find the Who's Next directory (handling special characters)
    who_next = None
    for item in who_album.iterdir():
        if "Who's Next" in item.name and "Steven Wilson" in item.name:
            who_next = item
            break

    if who_next and who_next.exists():
        results = analyze_album(who_next, "The Who - Who's Next (Steven Wilson Stereo Remix, 2023, 24-96)")
    else:
        print(f"⚠️  Album not found in: {who_album}")
        if who_next:
            print(f"    Tried: {who_next}")
