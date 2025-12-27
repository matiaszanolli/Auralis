#!/usr/bin/env python3
"""
Multi-Style Remaster Analysis Test Suite
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Analyzes Michael Jackson Dangerous album remasters using the adaptive mastering engine.
Tests the engine's ability to recommend mastering profiles for real production styles.

Test Data:
- Original: Michael Jackson Dangerous (1991, 320kbps MP3)
- Remaster: Hi-Res Masters collection (FLAC, various mastering approaches)
- Matching songs: 7 before/after pairs from different songs

Test Goals:
1. Extract audio fingerprints from original and remaster versions
2. Compare fingerprint changes (loudness, dynamics, spectrum)
3. Recommend mastering profile for original based on fingerprint
4. Analyze if recommended profile matches actual remaster characteristics
5. Document production style differences across songs
"""

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add matchering to path
sys.path.insert(0, '/mnt/data/src/matchering')

from auralis.analysis.adaptive_mastering_engine import AdaptiveMasteringEngine
from auralis.analysis.mastering_fingerprint import MasteringFingerprint
from auralis.io.unified_loader import load_audio

# Test data
DANGEROUS_DIR = "/home/matias/Downloads/Michael Jackson - Dangerous [320-Bubanee]"
HIRES_DIR = None  # Will be found dynamically

# Song pairs: (original_file, remaster_file, song_name)
TEST_SONGS = [
    ("02 - Why You Wanna Trip On Me - Michael Jackson.mp3", "34. Why You Wanna Trip on Me.flac", "Why You Wanna Trip On Me"),
    ("03 - In The Closet - Michael Jackson.mp3", "36. In the Closet.flac", "In The Closet"),
    ("05 - Remember The Time - Michael Jackson.mp3", "35. Remember the Time.flac", "Remember The Time"),
    ("07 - Heal The World - Michael Jackson.mp3", "38. Heal the World.flac", "Heal The World"),
    ("08 - Black Or White - Michael Jackson.mp3", "33. Black or White.flac", "Black Or White"),
    ("09 - Who Is It - Michael Jackson.mp3", "32. Who Is It.flac", "Who Is It"),
    ("11 - Will You Be There - Michael Jackson.mp3", "37. Will You Be There.flac", "Will You Be There"),
]


@dataclass
class RemasterAnalysis:
    """Analysis result for a single song's before/after remaster"""
    song_name: str
    original_file: str
    remaster_file: str

    # Original audio metrics
    original_loudness_dbfs: float
    original_crest_db: float
    original_centroid_hz: float
    original_rolloff_hz: float
    original_zcr: float
    original_spread: float
    original_peak_dbfs: float

    # Remaster audio metrics
    remaster_loudness_dbfs: float
    remaster_crest_db: float
    remaster_centroid_hz: float
    remaster_rolloff_hz: float
    remaster_zcr: float
    remaster_spread: float
    remaster_peak_dbfs: float

    # Changes (remaster - original)
    loudness_change_db: float
    crest_change_db: float
    centroid_change_hz: float
    rolloff_change_hz: float
    zcr_change: float
    spread_change: float
    peak_change_db: float

    # Recommendation
    recommended_profile_name: str
    recommendation_confidence: float
    predicted_loudness_change: float
    predicted_crest_change: float
    predicted_centroid_change: float

    # Accuracy assessment
    loudness_prediction_error_db: float
    crest_prediction_error_db: float
    centroid_prediction_error_hz: float

    def to_dict(self):
        return asdict(self)


def find_hires_directory() -> str:
    """Find the Hi-Res Masters directory with special characters"""
    downloads = Path("/home/matias/Downloads")
    for d in downloads.iterdir():
        if "Hi-Res" in d.name and d.is_dir():
            return str(d)
    raise FileNotFoundError("Could not find Hi-Res Masters directory")


def load_and_analyze(file_path: str) -> Tuple[np.ndarray, MasteringFingerprint, float]:
    """Load audio file and extract mastering fingerprint"""
    try:
        audio, sr = load_audio(file_path)
        fingerprint = MasteringFingerprint.from_audio_file(file_path)
        return audio, fingerprint, sr
    except Exception as e:
        print(f"Failed to load {file_path}: {e}")
        raise


def analyze_song_pair(original_path: str, remaster_path: str, song_name: str,
                     engine: AdaptiveMasteringEngine) -> Optional[RemasterAnalysis]:
    """Analyze a before/after remaster pair"""
    try:
        print(f"\n{'='*70}")
        print(f"Analyzing: {song_name}")
        print(f"{'='*70}")

        # Load and analyze original
        print(f"Loading original: {Path(original_path).name}")
        orig_audio, orig_fp, sr = load_and_analyze(original_path)

        # Load and analyze remaster
        print(f"Loading remaster: {Path(remaster_path).name}")
        remas_audio, remas_fp, _ = load_and_analyze(remaster_path)

        # Get recommendation for original
        print("Getting mastering profile recommendation...")
        recommendation = engine.recommend(orig_fp)

        # Calculate changes
        loudness_change = remas_fp.loudness_dbfs - orig_fp.loudness_dbfs
        crest_change = remas_fp.crest_db - orig_fp.crest_db
        centroid_change = remas_fp.spectral_centroid - orig_fp.spectral_centroid
        rolloff_change = remas_fp.spectral_rolloff - orig_fp.spectral_rolloff
        zcr_change = remas_fp.zero_crossing_rate - orig_fp.zero_crossing_rate
        spread_change = remas_fp.spectral_spread - orig_fp.spectral_spread
        peak_change = remas_fp.peak_dbfs - orig_fp.peak_dbfs

        # Calculate prediction errors
        loudness_error = abs(recommendation.predicted_loudness_change - loudness_change)
        crest_error = abs(recommendation.predicted_crest_change - crest_change)
        centroid_error = abs(recommendation.predicted_centroid_change - centroid_change)

        # Create analysis result
        analysis = RemasterAnalysis(
            song_name=song_name,
            original_file=Path(original_path).name,
            remaster_file=Path(remaster_path).name,

            # Original metrics
            original_loudness_dbfs=orig_fp.loudness_dbfs,
            original_crest_db=orig_fp.crest_db,
            original_centroid_hz=orig_fp.spectral_centroid,
            original_rolloff_hz=orig_fp.spectral_rolloff,
            original_zcr=orig_fp.zero_crossing_rate,
            original_spread=orig_fp.spectral_spread,
            original_peak_dbfs=orig_fp.peak_dbfs,

            # Remaster metrics
            remaster_loudness_dbfs=remas_fp.loudness_dbfs,
            remaster_crest_db=remas_fp.crest_db,
            remaster_centroid_hz=remas_fp.spectral_centroid,
            remaster_rolloff_hz=remas_fp.spectral_rolloff,
            remaster_zcr=remas_fp.zero_crossing_rate,
            remaster_spread=remas_fp.spectral_spread,
            remaster_peak_dbfs=remas_fp.peak_dbfs,

            # Changes
            loudness_change_db=loudness_change,
            crest_change_db=crest_change,
            centroid_change_hz=centroid_change,
            rolloff_change_hz=rolloff_change,
            zcr_change=zcr_change,
            spread_change=spread_change,
            peak_change_db=peak_change,

            # Recommendation
            recommended_profile_name=recommendation.primary_profile.name,
            recommendation_confidence=recommendation.confidence_score,
            predicted_loudness_change=recommendation.predicted_loudness_change,
            predicted_crest_change=recommendation.predicted_crest_change,
            predicted_centroid_change=recommendation.predicted_centroid_change,

            # Errors
            loudness_prediction_error_db=loudness_error,
            crest_prediction_error_db=crest_error,
            centroid_prediction_error_hz=centroid_error,
        )

        # Log results
        print(f"\n✓ Original Metrics:")
        print(f"  Loudness: {orig_fp.loudness_dbfs:.2f} dBFS")
        print(f"  Crest: {orig_fp.crest_db:.2f} dB")
        print(f"  Centroid: {orig_fp.spectral_centroid:.1f} Hz")

        print(f"\n✓ Remaster Metrics:")
        print(f"  Loudness: {remas_fp.loudness_dbfs:.2f} dBFS (change: {loudness_change:+.2f} dB)")
        print(f"  Crest: {remas_fp.crest_db:.2f} dB (change: {crest_change:+.2f} dB)")
        print(f"  Centroid: {remas_fp.spectral_centroid:.1f} Hz (change: {centroid_change:+.1f} Hz)")

        print(f"\n✓ Recommendation:")
        print(f"  Profile: {recommendation.primary_profile.name}")
        print(f"  Confidence: {recommendation.confidence_score*100:.1f}%")
        print(f"  Predicted loudness change: {recommendation.predicted_loudness_change:+.2f} dB")
        print(f"  Actual loudness change: {loudness_change:+.2f} dB")
        print(f"  Prediction error: {loudness_error:.3f} dB")

        return analysis

    except Exception as e:
        print(f"Error analyzing {song_name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_test_suite():
    """Run the complete multi-style mastering test suite"""
    global HIRES_DIR

    print("\n" + "█"*80)
    print("MULTI-STYLE REMASTER ANALYSIS TEST SUITE")
    print("█"*80)
    print("\nTest Data: Michael Jackson Dangerous Album")
    print("Original: 320kbps MP3 (1991 release)")
    print("Remaster: Hi-Res Masters FLAC collection")
    print(f"Test songs: {len(TEST_SONGS)}")

    # Find Hi-Res directory
    try:
        HIRES_DIR = find_hires_directory()
        print(f"✓ Found Hi-Res Masters at: {Path(HIRES_DIR).name}")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        return False

    # Initialize engine
    print("\nInitializing adaptive mastering engine...")
    engine = AdaptiveMasteringEngine()
    print("✓ Engine ready")

    # Run analyses
    results: List[RemasterAnalysis] = []
    print(f"\n{'='*80}")
    print(f"ANALYZING {len(TEST_SONGS)} SONG PAIRS")
    print(f"{'='*80}")

    for orig_file, remas_file, song_name in TEST_SONGS:
        orig_path = os.path.join(DANGEROUS_DIR, orig_file)
        remas_path = os.path.join(HIRES_DIR, remas_file)

        if not os.path.exists(orig_path):
            print(f"Original file not found: {orig_path}")
            continue

        if not os.path.exists(remas_path):
            print(f"Remaster file not found: {remas_path}")
            continue

        analysis = analyze_song_pair(orig_path, remas_path, song_name, engine)
        if analysis:
            results.append(analysis)

    # Generate report
    print(f"\n{'='*80}")
    print(f"TEST RESULTS SUMMARY")
    print(f"{'='*80}\n")

    print(f"✓ Successfully analyzed {len(results)} songs\n")

    # Statistics
    if results:
        loudness_errors = [r.loudness_prediction_error_db for r in results]
        crest_errors = [r.crest_prediction_error_db for r in results]
        centroid_errors = [r.centroid_prediction_error_hz for r in results]

        print("PREDICTION ACCURACY:")
        print(f"  Loudness Error (avg): {np.mean(loudness_errors):.3f} dB")
        print(f"  Loudness Error (max): {np.max(loudness_errors):.3f} dB")
        print(f"  Crest Error (avg): {np.mean(crest_errors):.3f} dB")
        print(f"  Crest Error (max): {np.max(crest_errors):.3f} dB")
        print(f"  Centroid Error (avg): {np.mean(centroid_errors):.1f} Hz")
        print(f"  Centroid Error (max): {np.max(centroid_errors):.1f} Hz\n")

        # Confidence analysis
        confidence_scores = [r.recommendation_confidence for r in results]
        print("RECOMMENDATION CONFIDENCE:")
        print(f"  Average: {np.mean(confidence_scores)*100:.1f}%")
        print(f"  Min: {np.min(confidence_scores)*100:.1f}%")
        print(f"  Max: {np.max(confidence_scores)*100:.1f}%\n")

        # Profile distribution
        profiles = {}
        for r in results:
            profiles[r.recommended_profile_name] = profiles.get(r.recommended_profile_name, 0) + 1

        print("RECOMMENDED PROFILES:")
        for profile, count in sorted(profiles.items(), key=lambda x: x[1], reverse=True):
            print(f"  {profile}: {count}/{len(results)} songs")

        print("\n" + "="*80)
        print("DETAILED RESULTS")
        print("="*80 + "\n")

        for i, result in enumerate(results, 1):
            print(f"{i}. {result.song_name}")
            print(f"   Original Loudness: {result.original_loudness_dbfs:.2f} dBFS")
            print(f"   Remaster Loudness: {result.remaster_loudness_dbfs:.2f} dBFS (Δ {result.loudness_change_db:+.2f})")
            print(f"   Recommended Profile: {result.recommended_profile_name} ({result.recommendation_confidence*100:.0f}%)")
            print(f"   Loudness Prediction Error: {result.loudness_prediction_error_db:.3f} dB\n")

    # Save results to JSON
    results_file = "/tmp/multistyle_mastering_results.json"
    with open(results_file, 'w') as f:
        json.dump([r.to_dict() for r in results], f, indent=2, default=str)
    print(f"✓ Results saved to: {results_file}")

    return len(results) > 0


if __name__ == "__main__":
    try:
        success = run_test_suite()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
