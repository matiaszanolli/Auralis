"""
Phase 7B: Remaster Comparison Testing

Compares sampling strategy accuracy on original vs professionally remastered
versions of the same songs. This tests whether sampling can detect differences
in mastering quality and processing.

Test Case 1: YES - "Close To The Edge" (1972)
- Original: /mnt/Musica/Musica/YES/Albums/1972 - Close To The Edge/01 - Close To The Edge.flac
- Steven Wilson Remaster (2018, 24-96): /mnt/Musica/Musica/YES/2018. Yes - The Steven Wilson Remixes [24-96]/Disc 3 - Close To The Edge (1972)/01. Close To The Edge.flac

Steven Wilson is a professional mastering engineer known for high-quality remasters.
This tests whether sampling strategy can detect the improvements in a professional remaster.
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


def analyze_track_detailed(track_path: Path, sr: int = 44100) -> dict:
    """Analyze a track with both strategies and return detailed features."""
    try:
        audio, _ = load_audio(str(track_path), target_sample_rate=sr)

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        audio = audio.astype(np.float64)
        duration_s = len(audio) / sr

        # Full-track analysis
        analyzer_full = AudioFingerprintAnalyzer(fingerprint_strategy="full-track")
        start = time.perf_counter()
        features_full = analyzer_full.analyze(audio, sr)
        time_full = time.perf_counter() - start

        # Sampled analysis
        analyzer_sampled = AudioFingerprintAnalyzer(
            fingerprint_strategy="sampling",
            sampling_interval=20.0
        )
        start = time.perf_counter()
        features_sampled = analyzer_sampled.analyze(audio, sr)
        time_sampled = time.perf_counter() - start

        del audio, analyzer_full, analyzer_sampled
        gc.collect()

        return {
            "track": track_path.stem,
            "duration_s": duration_s,
            "features_full": features_full,
            "features_sampled": features_sampled,
            "time_full": time_full,
            "time_sampled": time_sampled,
            "error": None,
        }

    except Exception as e:
        return {
            "track": track_path.stem,
            "duration_s": 0,
            "error": str(e)[:100],
        }


def compare_original_vs_remaster(original_path: Path, remaster_path: Path, description: str):
    """Compare fingerprints of original vs remastered version."""
    print("\n" + "=" * 130)
    print(f"REMASTER COMPARISON: {description}")
    print("=" * 130)

    # Analyze both versions
    print(f"\nAnalyzing original version...")
    result_original = analyze_track_detailed(original_path)

    print(f"Analyzing remastered version...")
    result_remaster = analyze_track_detailed(remaster_path)

    if "error" in result_original and result_original["error"]:
        print(f"ERROR analyzing original: {result_original['error']}")
        return

    if "error" in result_remaster and result_remaster["error"]:
        print(f"ERROR analyzing remaster: {result_remaster['error']}")
        return

    # =========================================================================
    # Full-Track Comparison
    # =========================================================================
    print(f"\n{'=' * 130}")
    print("FULL-TRACK ANALYSIS COMPARISON")
    print("=" * 130)

    print(f"\nOriginal vs Remaster Feature Differences (Full-Track):")
    print("-" * 130)

    # Extract key harmonic features
    harmonic_keys = ["harmonic_ratio", "pitch_stability", "chroma_energy"]

    print(f"\n{'Feature':<30} {'Original':<15} {'Remaster':<15} {'Difference':<15} {'Change %':<12}")
    print("-" * 130)

    for key in harmonic_keys:
        orig_val = result_original["features_full"].get(key, 0)
        rem_val = result_remaster["features_full"].get(key, 0)
        diff = rem_val - orig_val
        pct_change = (diff / orig_val * 100) if orig_val != 0 else 0

        print(
            f"{key:<30} {orig_val:>13.3f}   {rem_val:>13.3f}   "
            f"{diff:>+13.3f}   {pct_change:>+10.1f}%"
        )

    # Compare other features
    all_keys = set(result_original["features_full"].keys()) - {"_harmonic_analysis_method"}
    non_harmonic = sorted([k for k in all_keys if k not in harmonic_keys])

    if non_harmonic:
        print(f"\nOther Features (temporal, spectral, variation, stereo):")
        print("-" * 130)

        for key in non_harmonic[:5]:  # Show top 5
            orig_val = result_original["features_full"].get(key, 0)
            rem_val = result_remaster["features_full"].get(key, 0)
            diff = rem_val - orig_val
            pct_change = (diff / orig_val * 100) if orig_val != 0 else 0

            print(
                f"{key:<30} {orig_val:>13.3f}   {rem_val:>13.3f}   "
                f"{diff:>+13.3f}   {pct_change:>+10.1f}%"
            )

    # =========================================================================
    # Sampling vs Full-Track Consistency
    # =========================================================================
    print(f"\n{'=' * 130}")
    print("SAMPLING VS FULL-TRACK CONSISTENCY")
    print("=" * 130)

    # Calculate correlation for both versions
    print(f"\nOriginal Version - Sampling vs Full-Track Correlation:")
    print("-" * 130)

    orig_full = np.array([result_original["features_full"][k] for k in harmonic_keys])
    orig_sampled = np.array([result_original["features_sampled"][k] for k in harmonic_keys])

    try:
        orig_corr = np.corrcoef(orig_full, orig_sampled)[0, 1]
        if np.isnan(orig_corr):
            orig_corr = 1.0
    except:
        orig_corr = 1.0

    print(f"  Harmonic features correlation: {orig_corr:.3f}")
    print(f"  Speedup: {result_original['time_full'] / result_original['time_sampled']:.2f}x")

    print(f"\nRemastered Version - Sampling vs Full-Track Correlation:")
    print("-" * 130)

    rem_full = np.array([result_remaster["features_full"][k] for k in harmonic_keys])
    rem_sampled = np.array([result_remaster["features_sampled"][k] for k in harmonic_keys])

    try:
        rem_corr = np.corrcoef(rem_full, rem_sampled)[0, 1]
        if np.isnan(rem_corr):
            rem_corr = 1.0
    except:
        rem_corr = 1.0

    print(f"  Harmonic features correlation: {rem_corr:.3f}")
    print(f"  Speedup: {result_remaster['time_full'] / result_remaster['time_sampled']:.2f}x")

    # =========================================================================
    # Remaster Detection
    # =========================================================================
    print(f"\n{'=' * 130}")
    print("REMASTER DETECTION ANALYSIS")
    print("=" * 130)

    # Compare original sampling with remaster sampling
    orig_sampled_vec = result_original["features_sampled"]
    rem_sampled_vec = result_remaster["features_sampled"]

    harmonic_orig = np.array([orig_sampled_vec[k] for k in harmonic_keys])
    harmonic_rem = np.array([rem_sampled_vec[k] for k in harmonic_keys])

    try:
        cross_corr = np.corrcoef(harmonic_orig, harmonic_rem)[0, 1]
        if np.isnan(cross_corr):
            cross_corr = 1.0
    except:
        cross_corr = 1.0

    # Calculate feature distance (how different are the fingerprints?)
    feature_distance = np.linalg.norm(harmonic_orig - harmonic_rem)

    print(f"\nCross-Version Comparison (Sampling):")
    print("-" * 130)
    print(f"  Harmonic feature correlation: {cross_corr:.3f}")
    print(f"  Euclidean distance between fingerprints: {feature_distance:.3f}")

    if cross_corr >= 0.95:
        print(f"\n  ✅ VERY SIMILAR - Remaster has minimal sonic impact on fingerprint")
        print(f"     → Mastering preserved core harmonic characteristics")
    elif cross_corr >= 0.85:
        print(f"\n  ✅ SIMILAR - Remaster has measurable but minor impact")
        print(f"     → Mastering improved clarity/balance but core characteristics preserved")
    elif cross_corr >= 0.75:
        print(f"\n  ⚠️  MODERATELY DIFFERENT - Remaster significantly changes sonic character")
        print(f"     → Mastering applied substantial processing")
    else:
        print(f"\n  ❌ VERY DIFFERENT - Remaster substantially changed characteristics")
        print(f"     → Different mix, arrangement, or heavy processing")

    # =========================================================================
    # Feature-by-Feature Analysis
    # =========================================================================
    print(f"\n{'=' * 130}")
    print("DETAILED FEATURE ANALYSIS")
    print("=" * 130)

    print(f"\nHarmonic Characteristics:")
    print("-" * 130)

    print(f"Harmonic Ratio (proportion of harmonic vs percussive):")
    print(f"  Original:  {result_original['features_sampled']['harmonic_ratio']:.3f}")
    print(f"  Remaster:  {result_remaster['features_sampled']['harmonic_ratio']:.3f}")
    change = result_remaster['features_sampled']['harmonic_ratio'] - result_original['features_sampled']['harmonic_ratio']
    print(f"  Change:    {change:+.3f} ({change / result_original['features_sampled']['harmonic_ratio'] * 100:+.1f}%)")
    if change > 0.05:
        print(f"  → Remaster increased harmonic content (clearer, more musical)")
    elif change < -0.05:
        print(f"  → Remaster increased percussive content (punchier, more aggressive)")

    print(f"\nPitch Stability (consistency of pitch):")
    print(f"  Original:  {result_original['features_sampled']['pitch_stability']:.3f}")
    print(f"  Remaster:  {result_remaster['features_sampled']['pitch_stability']:.3f}")
    change = result_remaster['features_sampled']['pitch_stability'] - result_original['features_sampled']['pitch_stability']
    print(f"  Change:    {change:+.3f}")
    if change > 0.05:
        print(f"  → Remaster improved pitch stability (clearer tuning, better vocals)")
    elif change < -0.05:
        print(f"  → Remaster reduced pitch stability (more variation, different interpretation)")

    print(f"\nChroma Energy (concentration in pitch classes):")
    print(f"  Original:  {result_original['features_sampled']['chroma_energy']:.3f}")
    print(f"  Remaster:  {result_remaster['features_sampled']['chroma_energy']:.3f}")
    change = result_remaster['features_sampled']['chroma_energy'] - result_original['features_sampled']['chroma_energy']
    print(f"  Change:    {change:+.3f}")
    if change > 0.05:
        print(f"  → Remaster concentrated energy in specific pitch classes (tighter harmonic structure)")
    elif change < -0.05:
        print(f"  → Remaster dispersed pitch energy (wider harmonic palette)")

    print(f"\n{'=' * 130}\n")


def test_remaster_comparison():
    """Test sampling strategy on remastered versions."""
    print("\n" + "=" * 130)
    print("PHASE 7B: REMASTER COMPARISON TESTING")
    print("Professional remastering by Steven Wilson and others")
    print("=" * 130)

    # Test Case 1: YES - Close To The Edge
    original_yes = Path(
        "/mnt/Musica/Musica/YES/Albums/1972 - Close To The Edge/01 - Close To The Edge.flac"
    )
    remaster_yes = Path(
        "/mnt/Musica/Musica/YES/2018. Yes - The Steven Wilson Remixes [24-96]/"
        "Disc 3 - Close To The Edge (1972)/01. Close To The Edge.flac"
    )

    if original_yes.exists() and remaster_yes.exists():
        compare_original_vs_remaster(
            original_yes,
            remaster_yes,
            "YES - Close To The Edge (1972) - Steven Wilson Remaster (2018, 24-96)"
        )
    else:
        print(f"\n⚠️  YES tracks not found:")
        print(f"    Original: {original_yes.exists()}")
        print(f"    Remaster: {remaster_yes.exists()}")

    

    # Test Case 2: Porcupine Tree - Signify
    original_pt = Path(
        "/mnt/Musica/Musica/Porcupine Tree/Porcupine Tree - 1996 - Signify (FLAC+CUE)"
    )
    remaster_pt = Path(
        "/mnt/Musica/Musica/Porcupine Tree/Porcupine Tree - Signify (1996, Remastered 2016) [FLAC]"
    )

    if original_pt.exists() and remaster_pt.exists():
        compare_original_vs_remaster(
            original_pt,
            remaster_pt,
            "Porcupine Tree - Signify (1996 Original vs 2016 Remaster)"
        )
    else:
        print(f"\n⚠️  Porcupine Tree tracks not found:")
        print(f"    Original: {original_pt.exists()}")
        print(f"    Remaster: {remaster_pt.exists()}")
# Add more test cases as they become available
    # TODO: Add other remaster pairs

    print("\n" + "=" * 130)
    print("CONCLUSIONS")
    print("=" * 130)
    print("""
This test compares how sampling strategy fingerprints original recordings versus
professional remasters. Key insights:

1. Can sampling detect remastering work?
2. Are the differences in fingerprints meaningful?
3. Would this affect music matching/identification?
4. What mastering characteristics impact fingerprints most?

These insights will inform Phase 7C adaptive strategies and production use cases.
""")


if __name__ == "__main__":
    test_remaster_comparison()
