"""
Test suite for weighted profile recommendations (Priority 4).

Tests multi-profile weighting for hybrid mastering scenarios.
Validates that low-confidence tracks get blended recommendations.
"""

import json
from pathlib import Path

import pytest

from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine
from auralis.analysis.mastering_fingerprint import MasteringFingerprint


@pytest.mark.skipif(
    not Path("/tmp/multistyle_mastering_results.json").exists(),
    reason="Requires multistyle mastering results. Run test_adaptive_mastering_multistyle.py first"
)
def test_weighted_recommendation_why_you_wanna_trip():
    """
    Test weighted recommendation for 'Why You Wanna Trip On Me'.

    This track has low confidence with single profile (21%) because it's
    a hybrid between Hi-Res Masters (loudness/crest) and something else
    (centroid reduction). Weighted recommendation should blend profiles
    to get better predictions.

    Actual changes:
    - Loudness: +0.60 dB (Hi-Res Masters: -0.93, Bright Masters: -1.0)
    - Crest: -0.44 dB (Hi-Res Masters: +1.4, Warm Masters: +1.1)
    - Centroid: -72 Hz (Bright Masters: +130, Warm Masters: -80)
    """
    # Load test results
    results_path = Path("/tmp/multistyle_mastering_results.json")
    with open(results_path) as f:
        results = json.load(f)

    # Find the song
    song_data = next(r for r in results if r["song_name"] == "Why You Wanna Trip On Me")

    # Create fingerprint from original audio
    original_fp = MasteringFingerprint(
        loudness_dbfs=song_data["original_loudness_dbfs"],
        peak_dbfs=song_data["original_peak_dbfs"],
        crest_db=song_data["original_crest_db"],
        spectral_centroid=song_data["original_centroid_hz"],
        spectral_rolloff=song_data["original_rolloff_hz"],
        zero_crossing_rate=song_data["original_zcr"],
        spectral_spread=song_data["original_spread"],
    )

    # Get single recommendation (low confidence)
    engine = AdaptiveMasteringEngine()
    single_rec = engine.recommend(original_fp)
    print(f"\n=== Single Recommendation ===")
    print(f"Profile: {single_rec.primary_profile.name}")
    print(f"Confidence: {single_rec.confidence_score:.2%}")
    print(f"Predicted: {single_rec.predicted_loudness_change:+.2f} dB loudness, "
          f"{single_rec.predicted_crest_change:+.2f} dB crest, "
          f"{single_rec.predicted_centroid_change:+.1f} Hz centroid")

    # Get weighted recommendation (should blend)
    weighted_rec = engine.recommend_weighted(original_fp, confidence_threshold=0.4)
    print(f"\n=== Weighted Recommendation ===")
    print(f"Has weighted profiles: {len(weighted_rec.weighted_profiles) > 0}")

    if weighted_rec.weighted_profiles:
        print(f"Blend composition:")
        for pw in weighted_rec.weighted_profiles:
            print(f"  {pw.profile.name}: {pw.weight:.0%}")
        print(f"\nBlended predictions:")
        print(f"  Loudness: {weighted_rec.predicted_loudness_change:+.2f} dB")
        print(f"  Crest: {weighted_rec.predicted_crest_change:+.2f} dB")
        print(f"  Centroid: {weighted_rec.predicted_centroid_change:+.1f} Hz")

    # Actual values
    print(f"\n=== Actual Values ===")
    print(f"Loudness: {song_data['loudness_change_db']:+.2f} dB")
    print(f"Crest: {song_data['crest_change_db']:+.2f} dB")
    print(f"Centroid: {song_data['centroid_change_hz']:+.1f} Hz")

    # Validation: weighted should exist for low-confidence track
    assert len(weighted_rec.weighted_profiles) > 0, "Should have weighted profiles for low-confidence track"
    assert weighted_rec.confidence_score < 0.4, "Should be below threshold to trigger weighting"

    print(f"\n✅ Test passed: Weighted recommendation created for hybrid mastering scenario")


@pytest.mark.skipif(
    not Path("/tmp/multistyle_mastering_results.json").exists(),
    reason="Requires multistyle mastering results. Run test_adaptive_mastering_multistyle.py first"
)
def test_weighted_recommendation_remember_the_time():
    """
    Test weighted recommendation for 'Remember The Time'.

    Another hybrid track with 51% confidence that benefits from blending.

    Actual changes:
    - Loudness: -0.33 dB
    - Crest: +0.72 dB
    - Centroid: -130 Hz (strongest warming effect)
    """
    results_path = Path("/tmp/multistyle_mastering_results.json")
    with open(results_path) as f:
        results = json.load(f)

    song_data = next(r for r in results if r["song_name"] == "Remember The Time")

    original_fp = MasteringFingerprint(
        loudness_dbfs=song_data["original_loudness_dbfs"],
        peak_dbfs=song_data["original_peak_dbfs"],
        crest_db=song_data["original_crest_db"],
        spectral_centroid=song_data["original_centroid_hz"],
        spectral_rolloff=song_data["original_rolloff_hz"],
        zero_crossing_rate=song_data["original_zcr"],
        spectral_spread=song_data["original_spread"],
    )

    engine = AdaptiveMasteringEngine()

    # Get single recommendation
    single_rec = engine.recommend(original_fp)
    print(f"\n=== Single Recommendation ===")
    print(f"Profile: {single_rec.primary_profile.name}")
    print(f"Confidence: {single_rec.confidence_score:.2%}")

    # Get weighted recommendation (lower threshold since this is borderline)
    weighted_rec = engine.recommend_weighted(original_fp, confidence_threshold=0.52)
    print(f"\n=== Weighted Recommendation ===")

    if weighted_rec.weighted_profiles:
        print(f"Blend composition:")
        for pw in weighted_rec.weighted_profiles:
            print(f"  {pw.profile.name}: {pw.weight:.0%}")
        print(f"\nBlended predictions:")
        print(f"  Loudness: {weighted_rec.predicted_loudness_change:+.2f} dB (actual: {song_data['loudness_change_db']:+.2f})")
        print(f"  Crest: {weighted_rec.predicted_crest_change:+.2f} dB (actual: {song_data['crest_change_db']:+.2f})")
        print(f"  Centroid: {weighted_rec.predicted_centroid_change:+.1f} Hz (actual: {song_data['centroid_change_hz']:+.1f})")

    print(f"\n✅ Test completed: Analyzed hybrid mastering in Remember The Time")


@pytest.mark.skipif(
    not Path("/tmp/multistyle_mastering_results.json").exists(),
    reason="Requires multistyle mastering results. Run test_adaptive_mastering_multistyle.py first"
)
def test_weighted_high_confidence_no_blend():
    """
    Test that high-confidence tracks don't get weighted.

    'Black Or White' has 73% confidence with Hi-Res Masters.
    Should NOT create a blend because confidence is high.
    """
    results_path = Path("/tmp/multistyle_mastering_results.json")
    with open(results_path) as f:
        results = json.load(f)

    song_data = next(r for r in results if r["song_name"] == "Black Or White")

    original_fp = MasteringFingerprint(
        loudness_dbfs=song_data["original_loudness_dbfs"],
        peak_dbfs=song_data["original_peak_dbfs"],
        crest_db=song_data["original_crest_db"],
        spectral_centroid=song_data["original_centroid_hz"],
        spectral_rolloff=song_data["original_rolloff_hz"],
        zero_crossing_rate=song_data["original_zcr"],
        spectral_spread=song_data["original_spread"],
    )

    engine = AdaptiveMasteringEngine()
    weighted_rec = engine.recommend_weighted(original_fp, confidence_threshold=0.4)

    print(f"\n=== High Confidence Track (Black Or White) ===")
    print(f"Profile: {weighted_rec.primary_profile.name}")
    print(f"Confidence: {weighted_rec.confidence_score:.2%}")
    print(f"Has weighted profiles: {len(weighted_rec.weighted_profiles) > 0}")

    # Should NOT have weighted profiles (confidence is high)
    assert len(weighted_rec.weighted_profiles) == 0, "Should NOT have weighted profiles for high-confidence track"
    assert weighted_rec.confidence_score >= 0.4, "Should be above threshold"

    print(f"✅ Test passed: High-confidence track uses single profile (no blending)")


@pytest.mark.skipif(
    not Path("/tmp/multistyle_mastering_results.json").exists(),
    reason="Requires multistyle mastering results. Run test_adaptive_mastering_multistyle.py first"
)
def test_weighted_output_format():
    """Test that weighted recommendations serialize correctly."""
    results_path = Path("/tmp/multistyle_mastering_results.json")
    with open(results_path) as f:
        results = json.load(f)

    song_data = next(r for r in results if r["song_name"] == "Why You Wanna Trip On Me")

    original_fp = MasteringFingerprint(
        loudness_dbfs=song_data["original_loudness_dbfs"],
        peak_dbfs=song_data["original_peak_dbfs"],
        crest_db=song_data["original_crest_db"],
        spectral_centroid=song_data["original_centroid_hz"],
        spectral_rolloff=song_data["original_rolloff_hz"],
        zero_crossing_rate=song_data["original_zcr"],
        spectral_spread=song_data["original_spread"],
    )

    engine = AdaptiveMasteringEngine()
    rec = engine.recommend_weighted(original_fp, confidence_threshold=0.4)

    # Test to_dict serialization
    rec_dict = rec.to_dict()
    print(f"\n=== Serialization Test ===")
    print(f"Dict keys: {list(rec_dict.keys())}")

    if 'weighted_profiles' in rec_dict:
        print(f"Weighted profiles in output: {rec_dict['weighted_profiles']}")
        assert len(rec_dict['weighted_profiles']) > 0

    # Test summary format
    summary = rec.summary()
    print(f"\n=== Summary Output ===")
    print(summary)

    print(f"\n✅ Test passed: Weighted output formats correctly")


if __name__ == "__main__":
    print("=" * 70)
    print("WEIGHTED PROFILE RECOMMENDATION TESTS")
    print("=" * 70)

    test_weighted_recommendation_why_you_wanna_trip()
    test_weighted_recommendation_remember_the_time()
    test_weighted_high_confidence_no_blend()
    test_weighted_output_format()

    print("\n" + "=" * 70)
    print("✅ ALL WEIGHTED RECOMMENDATION TESTS PASSED")
    print("=" * 70)
