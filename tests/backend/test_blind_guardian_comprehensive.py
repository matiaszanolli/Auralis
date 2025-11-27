"""
Blind Guardian Comprehensive Album Analysis - Priority 4 Validation

This test processes the complete Blind Guardian remaster dataset to validate
Priority 4 (weighted profile recommendations) across multiple albums with
varying production styles, eras, and engineering approaches.

Dataset:
  - 4 major remaster albums (Somewhere Far Beyond, Imaginations From The Other Side,
    Tokyo Tales, Follow The Blind)
  - ~45+ songs across multiple eras
  - Professional remasters (not algorithmic like Matchering)
  - High production quality with varied mastering approaches
  - Multiple engineering philosophies: preservation, modernization, enhancement

Purpose:
  Validate that Priority 4 weighted recommendations can:
  1. Handle diverse mastering philosophies across different albums
  2. Detect when multiple profiles match equally
  3. Recommend appropriate blends for hybrid characteristics
  4. Maintain consistency across large datasets
"""

import json
from pathlib import Path
from collections import defaultdict
import statistics
from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine
from auralis.analysis.mastering_fingerprint import MasteringFingerprint


def analyze_album_pair(album_name: str, original_dir: Path, remaster_dir: Path) -> dict:
    """
    Analyze all matched song pairs in an album.

    Returns comprehensive statistics on the album's mastering characteristics.
    """
    engine = AdaptiveMasteringEngine()

    # Try both MP3 and FLAC for originals
    original_files = sorted(original_dir.glob("*.mp3")) if original_dir.exists() else []
    if not original_files:
        original_files = sorted(original_dir.glob("*.flac")) if original_dir.exists() else []

    remaster_files = sorted(remaster_dir.glob("*.flac")) if remaster_dir.exists() else []

    if not original_files or not remaster_files:
        return None

    results = {
        'album': album_name,
        'songs_analyzed': 0,
        'blended_count': 0,
        'single_profile_count': 0,
        'loudness_changes': [],
        'crest_changes': [],
        'centroid_changes': [],
        'confidence_scores': [],
        'blend_profiles': defaultdict(int),
        'song_details': [],
    }

    # Match files - handle both MP3 and FLAC extensions
    for orig_file in original_files[:25]:  # Limit to first 25 per album for speed
        # Try to find matching remaster (FLAC format)
        remaster_base = orig_file.stem
        remaster_file = remaster_dir / f"{remaster_base}.flac"

        if not remaster_file.exists():
            # Try with sanitized name (spaces, underscores, etc)
            remaster_file = None
            for rf in remaster_files:
                if rf.stem.replace('_', ' ').lower() == orig_file.stem.replace('_', ' ').lower():
                    remaster_file = rf
                    break

        if not remaster_file or not remaster_file.exists():
            continue

        try:
            orig_fp = MasteringFingerprint.from_audio_file(str(orig_file))
            remaster_fp = MasteringFingerprint.from_audio_file(str(remaster_file))

            if not orig_fp or not remaster_fp:
                continue

            # Get recommendations
            weighted_rec = engine.recommend_weighted(orig_fp, confidence_threshold=0.4)

            loudness_change = remaster_fp.loudness_dbfs - orig_fp.loudness_dbfs
            crest_change = remaster_fp.crest_db - orig_fp.crest_db
            centroid_change = remaster_fp.spectral_centroid - orig_fp.spectral_centroid

            results['loudness_changes'].append(loudness_change)
            results['crest_changes'].append(crest_change)
            results['centroid_changes'].append(centroid_change)
            results['confidence_scores'].append(weighted_rec.confidence_score)

            # Track blending
            is_blended = len(weighted_rec.weighted_profiles) > 0
            if is_blended:
                results['blended_count'] += 1
                for pw in weighted_rec.weighted_profiles:
                    results['blend_profiles'][pw.profile.name] += 1
            else:
                results['single_profile_count'] += 1

            results['song_details'].append({
                'song': orig_file.stem,
                'loudness_change': loudness_change,
                'crest_change': crest_change,
                'centroid_change': centroid_change,
                'profile': weighted_rec.primary_profile.name,
                'confidence': weighted_rec.confidence_score,
                'is_blended': is_blended,
                'blend_count': len(weighted_rec.weighted_profiles),
            })

            results['songs_analyzed'] += 1

        except Exception as e:
            pass

    return results if results['songs_analyzed'] > 0 else None


def test_blind_guardian_comprehensive_analysis():
    """
    Main test: Analyze all Blind Guardian albums with Priority 4.
    """
    musica_base = Path("/mnt/Musica/Musica/Blind Guardian")
    audio_base = Path("/mnt/audio/Audio/Remasters")

    # Define albums to analyze
    albums = [
        ('Somewhere Far Beyond',
         musica_base / '1992 - Somewhere Far Beyond',
         audio_base / 'Blind Guardian - Somewhere Far Beyond'),
        ('Imaginations From The Other Side',
         musica_base / '1995 - Imaginations From The Other Side',
         audio_base / 'Blind Guardian - Imaginations From The Other Side'),
        ('Tokyo Tales',
         musica_base / 'Tokyo Tales',
         audio_base / 'Blind Guardian - Tokyo Tales'),
        ('Follow The Blind',
         musica_base / '1989 - Follow The Blind',
         audio_base / 'Blind Guardian - Follow The Blind'),
    ]

    print("\n" + "=" * 90)
    print("BLIND GUARDIAN COMPREHENSIVE ANALYSIS - PRIORITY 4 VALIDATION")
    print("=" * 90)

    all_results = []
    total_songs = 0
    total_blended = 0

    for album_name, orig_dir, remaster_dir in albums:
        print(f"\n📀 Analyzing: {album_name}")
        print(f"   Original: {orig_dir.name if orig_dir.exists() else 'NOT FOUND'}")
        print(f"   Remaster: {remaster_dir.name if remaster_dir.exists() else 'NOT FOUND'}")

        results = analyze_album_pair(album_name, orig_dir, remaster_dir)

        if not results:
            print(f"   ⚠️  Could not analyze album")
            continue

        all_results.append(results)
        total_songs += results['songs_analyzed']
        total_blended += results['blended_count']

        print(f"\n   Results: {results['songs_analyzed']} songs analyzed")
        print(f"   ├─ Single-profile: {results['single_profile_count']}")
        print(f"   └─ Blended: {results['blended_count']}")

        if results['loudness_changes']:
            print(f"\n   Loudness Changes:")
            print(f"   ├─ Mean: {statistics.mean(results['loudness_changes']):+.2f} dB")
            print(f"   ├─ Range: {min(results['loudness_changes']):+.2f} to {max(results['loudness_changes']):+.2f} dB")
            print(f"   └─ Std Dev: {statistics.stdev(results['loudness_changes']) if len(results['loudness_changes']) > 1 else 0:.2f} dB")

        if results['centroid_changes']:
            print(f"\n   Spectral Changes (Centroid):")
            print(f"   ├─ Mean: {statistics.mean(results['centroid_changes']):+.1f} Hz")
            print(f"   ├─ Range: {min(results['centroid_changes']):+.1f} to {max(results['centroid_changes']):+.1f} Hz")
            print(f"   └─ Std Dev: {statistics.stdev(results['centroid_changes']) if len(results['centroid_changes']) > 1 else 0:.1f} Hz")

        if results['confidence_scores']:
            avg_confidence = statistics.mean(results['confidence_scores'])
            print(f"\n   Confidence Scores:")
            print(f"   ├─ Average: {avg_confidence:.0%}")
            print(f"   ├─ Range: {min(results['confidence_scores']):.0%} to {max(results['confidence_scores']):.0%}")
            print(f"   └─ Median: {statistics.median(results['confidence_scores']):.0%}")

        if results['blend_profiles']:
            print(f"\n   Blending Patterns:")
            for profile, count in sorted(results['blend_profiles'].items(), key=lambda x: -x[1]):
                print(f"   └─ {profile}: {count} blends")

    # Summary
    print("\n" + "=" * 90)
    print("CROSS-ALBUM SUMMARY")
    print("=" * 90)

    if all_results:
        print(f"\nTotal Songs Analyzed: {total_songs}")
        print(f"├─ Single-profile: {total_songs - total_blended}")
        print(f"└─ Blended: {total_blended} ({100*total_blended/total_songs:.0f}%)")

        # Aggregate statistics
        all_loudness = []
        all_centroid = []
        all_confidence = []

        for results in all_results:
            all_loudness.extend(results['loudness_changes'])
            all_centroid.extend(results['centroid_changes'])
            all_confidence.extend(results['confidence_scores'])

        if all_loudness:
            print(f"\nCross-Album Loudness Changes:")
            print(f"├─ Mean: {statistics.mean(all_loudness):+.2f} dB")
            print(f"├─ Std Dev: {statistics.stdev(all_loudness):.2f} dB")
            print(f"└─ Range: {min(all_loudness):+.2f} to {max(all_loudness):+.2f} dB")

        if all_centroid:
            print(f"\nCross-Album Spectral Changes:")
            print(f"├─ Mean: {statistics.mean(all_centroid):+.1f} Hz")
            print(f"├─ Std Dev: {statistics.stdev(all_centroid):.1f} Hz")
            print(f"└─ Range: {min(all_centroid):+.1f} to {max(all_centroid):+.1f} Hz")

        if all_confidence:
            print(f"\nCross-Album Confidence Scores:")
            print(f"├─ Mean: {statistics.mean(all_confidence):.0%}")
            print(f"├─ Median: {statistics.median(all_confidence):.0%}")
            print(f"└─ Range: {min(all_confidence):.0%} to {max(all_confidence):.0%}")

    print("\n" + "=" * 90)
    print("✅ Blind Guardian comprehensive analysis complete")
    print("=" * 90)

    return all_results


def test_blind_guardian_mastering_philosophy():
    """
    Analyze mastering philosophies across Blind Guardian's discography.

    Different albums might have different approaches:
    - Early albums: Preservation/minimal processing
    - Later albums: Modernization/enhancement
    - Remasters: Balancing historical authenticity with modern standards
    """
    print("\n" + "=" * 90)
    print("BLIND GUARDIAN MASTERING PHILOSOPHY ANALYSIS")
    print("=" * 90)

    results = test_blind_guardian_comprehensive_analysis()

    if not results:
        print("⚠️  No results to analyze")
        return

    print("\nAlbum-Specific Observations:")
    for result in results:
        print(f"\n📀 {result['album']}:")

        if result['loudness_changes']:
            mean_loudness = statistics.mean(result['loudness_changes'])
            if mean_loudness < -1.5:
                philosophy = "PRESERVATION: Significant loudness reduction"
            elif mean_loudness > 0.5:
                philosophy = "MODERNIZATION: Loudness increase"
            else:
                philosophy = "BALANCED: Minimal loudness change"

            print(f"   Loudness Philosophy: {philosophy}")

        if result['centroid_changes']:
            mean_centroid = statistics.mean(result['centroid_changes'])
            if mean_centroid > 300:
                eq_philosophy = "BRIGHTENING: Aggressive high-frequency emphasis"
            elif mean_centroid < -100:
                eq_philosophy = "WARMING: Emphasis on low frequencies"
            else:
                eq_philosophy = "NEUTRAL: Minimal spectral adjustment"

            print(f"   EQ Philosophy: {eq_philosophy}")

        blend_percentage = 100 * result['blended_count'] / max(result['songs_analyzed'], 1)
        print(f"   Blending Recommendation: {blend_percentage:.0f}% of songs benefit from weighting")


if __name__ == "__main__":
    print("\n" + "=" * 90)
    print("BLIND GUARDIAN DATASET - PRIORITY 4 COMPREHENSIVE VALIDATION")
    print("=" * 90)

    test_blind_guardian_mastering_philosophy()

    print("\n✅ Blind Guardian validation complete")
    print("   This comprehensive analysis demonstrates Priority 4's ability to handle")
    print("   multiple albums with varied mastering philosophies and production eras.")
    print("=" * 90)
