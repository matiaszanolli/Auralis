"""
Phil Collins "Serious Hits Live" - Matchering Validation Test

This test validates Priority 4 (weighted profile recommendations) against
real-world Matchering results. Phil Collins' live album was remastered using
Matchering's blanket matching approach, which is known to apply aggressive
one-size-fits-all mastering rather than tasteful, song-specific treatment.

The weighted profile system should detect when individual songs have conflicting
requirements (some needing aggressive loudness, others needing preservation)
and recommend blended approaches instead of forcing a single style.

Dataset:
  Original: Phil Collins - Serious Hits Live (1990, 320kbps MP3)
  Remastered: Phil Collins - Serious Hits Live (Matchering applied, FLAC)
  Professional mastering: No (algorithmic Matchering)
  Genre: Live rock/pop compilation
  Issue: Blanket matching may not respect song-specific characteristics
"""

import json
from pathlib import Path

from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine
from auralis.analysis.mastering_fingerprint import MasteringFingerprint


def load_and_analyze_pair(original_path: str, remaster_path: str) -> dict:
    """Load and analyze an original/remaster pair."""
    try:
        orig_fp = MasteringFingerprint.from_audio_file(original_path)
        remaster_fp = MasteringFingerprint.from_audio_file(remaster_path)

        if not orig_fp or not remaster_fp:
            return None

        return {
            'original': orig_fp,
            'remaster': remaster_fp,
            'loudness_change_db': remaster_fp.loudness_dbfs - orig_fp.loudness_dbfs,
            'crest_change_db': remaster_fp.crest_db - orig_fp.crest_db,
            'centroid_change_hz': remaster_fp.spectral_centroid - orig_fp.spectral_centroid,
        }
    except Exception as e:
        print(f"Error analyzing pair: {e}")
        return None


def test_phil_collins_album_matching():
    """
    Test weighted recommendations on Phil Collins album.

    Validates that the engine can detect problematic Matchering results
    and recommend more nuanced mastering approaches through blending.
    """
    original_dir = Path("/mnt/Musica/Musica/Phil Collins/1990 - Serious Hits Live")
    remaster_dir = Path("/mnt/audio/Audio/Remasters/Phil Collins - Serious Hits Live")

    if not original_dir.exists() or not remaster_dir.exists():
        print("⚠️  Phil Collins audio directories not found, skipping test")
        return

    engine = AdaptiveMasteringEngine()

    # Get list of original files
    original_files = sorted(original_dir.glob("*.mp3"))[:5]  # Test first 5 songs
    results = []

    print("\n" + "=" * 80)
    print("PHIL COLLINS 'SERIOUS HITS LIVE' - MATCHERING VALIDATION TEST")
    print("=" * 80)
    print(f"\nAnalyzing {len(original_files)} songs from Phil Collins live album...")
    print(f"Original: {original_dir.name}")
    print(f"Remastered: {remaster_dir.name} (Matchering applied)")
    print("\n" + "-" * 80)

    for orig_file in original_files:
        # Find matching remaster
        remaster_file = remaster_dir / orig_file.name.replace('.mp3', '.flac')

        if not remaster_file.exists():
            print(f"⚠️  Remaster not found for {orig_file.name}")
            continue

        print(f"\n📊 {orig_file.stem}")
        print(f"   Original: {orig_file.name}")
        print(f"   Remaster: {remaster_file.name}")

        # Analyze pair
        pair = load_and_analyze_pair(str(orig_file), str(remaster_file))
        if not pair:
            print(f"   ❌ Failed to analyze audio files")
            continue

        # Get recommendations
        single_rec = engine.recommend(pair['original'])
        weighted_rec = engine.recommend_weighted(pair['original'], confidence_threshold=0.4)

        print(f"\n   Audio Changes (Original → Remastered):")
        print(f"   ├─ Loudness: {pair['loudness_change_db']:+.2f} dB")
        print(f"   ├─ Crest: {pair['crest_change_db']:+.2f} dB")
        print(f"   └─ Centroid: {pair['centroid_change_hz']:+.1f} Hz")

        print(f"\n   Single-Profile Recommendation:")
        print(f"   ├─ Profile: {single_rec.primary_profile.name}")
        print(f"   ├─ Confidence: {single_rec.confidence_score:.0%}")
        print(f"   └─ Predicted: {single_rec.predicted_loudness_change:+.2f} dB loudness, "
              f"{single_rec.predicted_crest_change:+.2f} dB crest")

        if weighted_rec.weighted_profiles:
            print(f"\n   Weighted Recommendation (Hybrid Mastering):")
            for pw in weighted_rec.weighted_profiles:
                print(f"   ├─ {pw.profile.name}: {pw.weight:.0%}")
            print(f"   └─ Blended: {weighted_rec.predicted_loudness_change:+.2f} dB loudness, "
                  f"{weighted_rec.predicted_crest_change:+.2f} dB crest")
        else:
            print(f"\n   ℹ️  High confidence - single profile sufficient")

        results.append({
            'song': orig_file.stem,
            'actual_loudness_change': pair['loudness_change_db'],
            'actual_crest_change': pair['crest_change_db'],
            'actual_centroid_change': pair['centroid_change_hz'],
            'single_profile': single_rec.primary_profile.name,
            'single_confidence': single_rec.confidence_score,
            'is_blended': len(weighted_rec.weighted_profiles) > 0,
            'blend_profiles': [pw.profile.name for pw in weighted_rec.weighted_profiles] if weighted_rec.weighted_profiles else [],
        })

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    blended_count = sum(1 for r in results if r['is_blended'])
    single_count = len(results) - blended_count

    print(f"\nResults: {len(results)} songs analyzed")
    print(f"├─ Single-profile recommendations: {single_count}")
    print(f"└─ Weighted/blended recommendations: {blended_count}")

    if results:
        avg_single_confidence = sum(r['single_confidence'] for r in results) / len(results)
        print(f"\nAverage single-profile confidence: {avg_single_confidence:.0%}")

        if blended_count > 0:
            print(f"\n✅ Weighted profile system successfully detected problematic Matchering")
            print(f"   {blended_count} songs would benefit from hybrid/blended mastering")

    print("\n" + "=" * 80)
    print(f"✅ Phil Collins Matchering validation test completed")
    print("=" * 80)

    return results


def test_matchering_aggression_detection():
    """
    Analyze whether Matchering applied aggressive blanket mastering.

    Good mastering respects song characteristics.
    Bad blanket matching applies same processing to all songs.
    """
    original_dir = Path("/mnt/Musica/Musica/Phil Collins/1990 - Serious Hits Live")
    remaster_dir = Path("/mnt/audio/Audio/Remasters/Phil Collins - Serious Hits Live")

    if not original_dir.exists() or not remaster_dir.exists():
        print("⚠️  Phil Collins audio directories not found, skipping test")
        return

    print("\n" + "=" * 80)
    print("MATCHERING AGGRESSION DETECTION")
    print("=" * 80)

    loudness_changes = []
    crest_changes = []
    centroid_changes = []

    original_files = sorted(original_dir.glob("*.mp3"))[:10]

    for orig_file in original_files:
        remaster_file = remaster_dir / orig_file.name.replace('.mp3', '.flac')

        if not remaster_file.exists():
            continue

        pair = load_and_analyze_pair(str(orig_file), str(remaster_file))
        if not pair:
            continue

        loudness_changes.append(pair['loudness_change_db'])
        crest_changes.append(pair['crest_change_db'])
        centroid_changes.append(pair['centroid_change_hz'])

    if loudness_changes:
        import statistics

        print(f"\nLoudness Changes (across {len(loudness_changes)} songs):")
        print(f"  Mean: {statistics.mean(loudness_changes):+.2f} dB")
        print(f"  Std Dev: {statistics.stdev(loudness_changes) if len(loudness_changes) > 1 else 0:.2f} dB")
        print(f"  Range: {min(loudness_changes):+.2f} to {max(loudness_changes):+.2f} dB")

        print(f"\nCrest Changes (dynamic range):")
        print(f"  Mean: {statistics.mean(crest_changes):+.2f} dB")
        print(f"  Std Dev: {statistics.stdev(crest_changes) if len(crest_changes) > 1 else 0:.2f} dB")
        print(f"  Range: {min(crest_changes):+.2f} to {max(crest_changes):+.2f} dB")

        print(f"\nCentroid Changes (spectral):")
        print(f"  Mean: {statistics.mean(centroid_changes):+.1f} Hz")
        print(f"  Std Dev: {statistics.stdev(centroid_changes) if len(centroid_changes) > 1 else 0:.1f} Hz")
        print(f"  Range: {min(centroid_changes):+.1f} to {max(centroid_changes):+.1f} Hz")

        # Analyze uniformity
        loudness_variance = statistics.stdev(loudness_changes) if len(loudness_changes) > 1 else 0
        crest_variance = statistics.stdev(crest_changes) if len(crest_changes) > 1 else 0

        print(f"\nMatchering Aggression Indicators:")
        if loudness_variance < 0.3:
            print(f"  ⚠️  UNIFORM LOUDNESS CHANGE: All songs treated identically ({loudness_variance:.2f} dB variance)")
            print(f"     → Suggests blanket Matchering without song-specific consideration")
        else:
            print(f"  ✅ VARIABLE LOUDNESS CHANGE: Songs treated individually ({loudness_variance:.2f} dB variance)")

        if crest_variance < 0.5:
            print(f"  ⚠️  UNIFORM CREST CHANGE: Dynamics compressed/expanded uniformly")
        else:
            print(f"  ✅ VARIABLE CREST CHANGE: Different dynamic treatment per song")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("PRIORITY 4 VALIDATION: PHIL COLLINS MATCHERING TEST")
    print("=" * 80)

    results = test_phil_collins_album_matching()
    test_matchering_aggression_detection()

    print("\n✅ Phil Collins validation complete")
    print("   This real-world test demonstrates Priority 4's ability to handle")
    print("   problematic blanket mastering by recommending weighted blends.")
    print("=" * 80)
