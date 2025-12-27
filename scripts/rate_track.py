#!/usr/bin/env python3
"""Quick track rating for feedback collection.

This script captures user feedback on mastered tracks with minimal friction:
  - 5 seconds per track
  - Automatic fingerprint and detection capture
  - Stores feedback for later analysis

Usage:
    ./scripts/rate_track.py track.flac --rating 4 --comment "more bass"
    ./scripts/rate_track.py ~/Music/song.mp3 --rating 5
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import librosa
import numpy as np

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.core.recording_type_detector import RecordingTypeDetector


def rate_track(
    audio_file: str,
    rating: int,
    comment: Optional[str] = None,
    data_dir: Optional[Path] = None
) -> None:
    """Rate a mastered track and save feedback.

    Args:
        audio_file: Path to audio file
        rating: Rating 1-5 stars
        comment: Optional feedback comment
        data_dir: Directory for feedback storage (defaults to ~/.auralis)
    """
    audio_path = Path(audio_file)

    # Validate input
    if not audio_path.exists():
        print(f"✗ File not found: {audio_file}")
        return

    if not 1 <= rating <= 5:
        print(f"✗ Rating must be 1-5 (got {rating})")
        return

    # Determine data directory
    if data_dir is None:
        data_dir = Path.home() / ".auralis"

    feedback_dir = data_dir / "personal" / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    # Load audio and analyze
    print(f"Analyzing: {audio_path.name}...", end=" ", flush=True)

    try:
        audio, sr = librosa.load(
            str(audio_path), sr=44100, mono=False
        )
    except Exception as e:
        print(f"\n✗ Could not load audio: {e}")
        return

    # Detect recording type
    detector = RecordingTypeDetector()
    analyzer = AudioFingerprintAnalyzer()

    try:
        recording_type, adaptive_params = detector.detect(audio, sr)
        fingerprint = analyzer.analyze(audio, sr)
    except Exception as e:
        print(f"\n✗ Could not analyze audio: {e}")
        return

    print("Done!")

    # Create feedback entry
    feedback = {
        "track": str(audio_path.name),
        "track_path": str(audio_path.absolute()),
        "detected_type": recording_type.value,
        "confidence": float(adaptive_params.confidence),
        "philosophy": adaptive_params.mastering_philosophy,
        "rating": rating,
        "comment": comment if comment else "",
        "timestamp": datetime.now().isoformat(),
        "fingerprint": {
            "centroid_hz": float(
                fingerprint.get("spectral_centroid", 0) * 20000
            ),
            "bass_to_mid": float(fingerprint.get("bass_mid_ratio", 0)),
            "stereo_width": float(fingerprint.get("stereo_width", 0)),
            "crest_db": float(fingerprint.get("crest_db", 0)),
        },
        "parameters_applied": {
            "bass_adjustment_db": adaptive_params.bass_adjustment_db,
            "mid_adjustment_db": adaptive_params.mid_adjustment_db,
            "treble_adjustment_db": adaptive_params.treble_adjustment_db,
            "stereo_strategy": adaptive_params.stereo_strategy,
        },
    }

    # Append to ratings.jsonl (one JSON per line for easy streaming)
    feedback_file = feedback_dir / "ratings.jsonl"

    try:
        with open(feedback_file, "a") as f:
            f.write(json.dumps(feedback) + "\n")
    except Exception as e:
        print(f"✗ Could not save feedback: {e}")
        return

    # Print summary
    stars = "⭐" * rating
    print(f"\n✓ Rated: {audio_path.name}")
    print(f"  Type: {recording_type.value} ({adaptive_params.confidence:.0%} confidence)")
    print(f"  Rating: {stars} ({rating}/5)")
    if comment:
        print(f"  Note: {comment}")
    print(f"  Saved to: {feedback_file}")


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Rate a track for feedback collection",
        epilog="Example: ./scripts/rate_track.py track.flac --rating 4 --comment 'more bass'",
    )
    parser.add_argument("audio_file", help="Path to audio file")
    parser.add_argument(
        "--rating",
        type=int,
        required=True,
        choices=[1, 2, 3, 4, 5],
        help="Rating: 1-5 stars",
    )
    parser.add_argument(
        "--comment",
        help="Optional feedback comment",
        default=None,
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Data directory for feedback storage (defaults to ~/.auralis)",
        default=None,
    )

    args = parser.parse_args()
    rate_track(
        args.audio_file,
        args.rating,
        args.comment,
        args.data_dir
    )


if __name__ == "__main__":
    main()
