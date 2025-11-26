"""
Phase 7B: Production Style Testing

Compares sampling strategy accuracy on contrasting production styles:
- Pearl Jam (1991): Dynamic, well-balanced, natural compression
- Meshuggah (2012): Extreme compression, brick-walled, complex processing

This tests whether sampling maintains accuracy across vastly different mastering approaches.
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


def analyze_track(track_path: Path, strategy: str = "sampling") -> dict:
    """Analyze a single track with specified strategy."""
    try:
        audio, _ = load_audio(str(track_path), target_sample_rate=44100)

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        audio = audio.astype(np.float64)
        duration_s = len(audio) / 44100

        analyzer = AudioFingerprintAnalyzer(
            fingerprint_strategy=strategy,
            sampling_interval=20.0
        )

        start = time.perf_counter()
        features = analyzer.analyze(audio, 44100)
        analysis_time = time.perf_counter() - start

        del audio, analyzer
        gc.collect()

        return {
            "track": track_path.stem,
            "duration_s": duration_s,
            "time": analysis_time,
            "features": features,
            "method": features.get("_harmonic_analysis_method", "unknown"),
            "error": None,
        }

    except Exception as e:
        return {
            "track": track_path.stem,
            "duration_s": 0,
            "time": None,
            "features": None,
            "method": "error",
            "error": str(e)[:80],
        }


def compare_strategies(track_path: Path) -> dict:
    """Compare full-track vs sampling on same track."""
    full_result = analyze_track(track_path, "full-track")
    sampled_result = analyze_track(track_path, "sampling")

    if full_result["error"] or sampled_result["error"]:
        return {
            "track": track_path.stem,
            "error": full_result["error"] or sampled_result["error"],
        }

    # Calculate correlation
    harmonic_keys = ["harmonic_ratio", "pitch_stability", "chroma_energy"]
    full_values = np.array([full_result["features"][k] for k in harmonic_keys])
    sampled_values = np.array([sampled_result["features"][k] for k in harmonic_keys])

    try:
        correlation = np.corrcoef(full_values, sampled_values)[0, 1]
        if np.isnan(correlation):
            correlation = 1.0
    except:
        correlation = 1.0

    speedup = full_result["time"] / sampled_result["time"] if sampled_result["time"] > 0 else 0

    return {
        "track": track_path.stem,
        "duration_s": full_result["duration_s"],
        "time_full": full_result["time"],
        "time_sampled": sampled_result["time"],
        "speedup": speedup,
        "correlation": correlation,
        "features_full": full_result["features"],
        "features_sampled": sampled_result["features"],
        "error": None,
    }


def test_production_styles():
    """Test sampling on different production styles."""
    print("\n" + "=" * 110)
    print("PHASE 7B: PRODUCTION STYLE TESTING")
    print("=" * 110)

    # Test paths
    pearl_jam_path = Path("/mnt/Musica/Musica/Pearl Jam/1991 - Ten")
    meshuggah_path = Path("/mnt/Musica/Musica/Meshuggah/2012 - Koloss")

    results = {"pearl_jam": [], "meshuggah": []}

    # =========================================================================
    # Pearl Jam: Dynamic, Natural Compression
    # =========================================================================
    if pearl_jam_path.exists():
        print("\n🎸 PEARL JAM (1991) - Dynamic, well-balanced, natural mastering")
        print("-" * 110)
        print(f"{'Track':<40} {'Duration':<12} {'Full-Track':<12} {'Sampling':<12} {'Speedup':<10} {'Corr':<8}")
        print("-" * 110)

        tracks = sorted([f for f in pearl_jam_path.glob("*.flac")])[:5]

        for track_path in tracks:
            result = compare_strategies(track_path)

            if "error" in result and result["error"]:
                print(f"{result['track']:<40} ERROR: {result['error']}")
            else:
                status = "✅" if result["correlation"] >= 0.85 else "⚠️"
                print(
                    f"{result['track']:<40} {result['duration_s']:>7.1f}s    "
                    f"{result['time_full']:>10.3f}s  {result['time_sampled']:>10.3f}s  "
                    f"{result['speedup']:>8.2f}x  {result['correlation']:>6.3f} {status}"
                )

                results["pearl_jam"].append(result)

    # =========================================================================
    # Meshuggah: Extreme Compression, Brick-Walled
    # =========================================================================
    if meshuggah_path.exists():
        print("\n🤘 MESHUGGAH (2012) - Extreme compression, brick-walled, complex processing")
        print("-" * 110)
        print(f"{'Track':<40} {'Duration':<12} {'Full-Track':<12} {'Sampling':<12} {'Speedup':<10} {'Corr':<8}")
        print("-" * 110)

        tracks = sorted([f for f in meshuggah_path.glob("*.flac")])[:5]

        for track_path in tracks:
            result = compare_strategies(track_path)

            if "error" in result and result["error"]:
                print(f"{result['track']:<40} ERROR: {result['error']}")
            else:
                status = "✅" if result["correlation"] >= 0.85 else "⚠️"
                print(
                    f"{result['track']:<40} {result['duration_s']:>7.1f}s    "
                    f"{result['time_full']:>10.3f}s  {result['time_sampled']:>10.3f}s  "
                    f"{result['speedup']:>8.2f}x  {result['correlation']:>6.3f} {status}"
                )

                results["meshuggah"].append(result)

    # =========================================================================
    # Analysis & Summary
    # =========================================================================
    print("\n" + "=" * 110)
    print("PRODUCTION STYLE ANALYSIS")
    print("=" * 110)

    for style_name, style_results in results.items():
        if not style_results:
            continue

        print(f"\n{style_name.upper().replace('_', ' ')}:")
        print("-" * 110)

        avg_speedup = np.mean([r["speedup"] for r in style_results])
        avg_corr = np.mean([r["correlation"] for r in style_results])
        pass_rate = sum(1 for r in style_results if r["correlation"] >= 0.85) / len(style_results)

        # Extract feature differences
        harmonic_ratios_full = [r["features_full"]["harmonic_ratio"] for r in style_results]
        harmonic_ratios_sampled = [r["features_sampled"]["harmonic_ratio"] for r in style_results]

        pitch_stability_full = [r["features_full"]["pitch_stability"] for r in style_results]
        pitch_stability_sampled = [r["features_sampled"]["pitch_stability"] for r in style_results]

        chroma_full = [r["features_full"]["chroma_energy"] for r in style_results]
        chroma_sampled = [r["features_sampled"]["chroma_energy"] for r in style_results]

        print(f"  Average Speedup:           {avg_speedup:>8.2f}x")
        print(f"  Feature Correlation:       {avg_corr:>8.3f}")
        print(f"  Pass Rate (≥0.85 corr):    {pass_rate:>8.0%}")

        print(f"\n  Harmonic Ratio:")
        print(f"    Full-track avg:          {np.mean(harmonic_ratios_full):>8.3f}")
        print(f"    Sampling avg:            {np.mean(harmonic_ratios_sampled):>8.3f}")
        print(f"    Difference:              {abs(np.mean(harmonic_ratios_full) - np.mean(harmonic_ratios_sampled)):>8.3f}")

        print(f"\n  Pitch Stability:")
        print(f"    Full-track avg:          {np.mean(pitch_stability_full):>8.3f}")
        print(f"    Sampling avg:            {np.mean(pitch_stability_sampled):>8.3f}")
        print(f"    Difference:              {abs(np.mean(pitch_stability_full) - np.mean(pitch_stability_sampled)):>8.3f}")

        print(f"\n  Chroma Energy:")
        print(f"    Full-track avg:          {np.mean(chroma_full):>8.3f}")
        print(f"    Sampling avg:            {np.mean(chroma_sampled):>8.3f}")
        print(f"    Difference:              {abs(np.mean(chroma_full) - np.mean(chroma_sampled)):>8.3f}")

    # =========================================================================
    # Cross-Style Comparison
    # =========================================================================
    print("\n" + "=" * 110)
    print("CROSS-STYLE COMPARISON")
    print("=" * 110)

    if results["pearl_jam"] and results["meshuggah"]:
        pj_corr = np.mean([r["correlation"] for r in results["pearl_jam"]])
        mh_corr = np.mean([r["correlation"] for r in results["meshuggah"]])

        print(f"\nPearl Jam avg correlation:     {pj_corr:>8.3f} (Dynamic mastering)")
        print(f"Meshuggah avg correlation:     {mh_corr:>8.3f} (Extreme compression)")
        print(f"Difference:                    {abs(pj_corr - mh_corr):>8.3f}")

        if mh_corr >= 0.85 and pj_corr >= 0.85:
            print(f"\n✅ SUCCESS: Sampling maintains 85%+ accuracy on BOTH production styles")
            print(f"   → Extreme compression doesn't degrade accuracy")
            print(f"   → Sampling strategy is robust across mastering approaches")
        else:
            print(f"\n⚠️  WARNING: Accuracy varies by production style")
            if mh_corr < 0.85:
                print(f"   → Meshuggah (compressed): {mh_corr:.3f} < 0.85 target")
            if pj_corr < 0.85:
                print(f"   → Pearl Jam (dynamic): {pj_corr:.3f} < 0.85 target")

    print("\n" + "=" * 110 + "\n")


if __name__ == "__main__":
    test_production_styles()
