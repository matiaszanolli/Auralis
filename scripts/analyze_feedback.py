#!/usr/bin/env python3
"""Analyze feedback patterns and suggest adjustments.

This script aggregates feedback from multiple track ratings and identifies
patterns that suggest profile improvements. Used for monthly analysis and
learning progress tracking.

Usage:
    ./scripts/analyze_feedback.py --type studio
    ./scripts/analyze_feedback.py --monthly-summary
    ./scripts/analyze_feedback.py --all-types
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median, stdev
from typing import Dict, List, Optional

from auralis.core.recording_type_detector import RecordingType


def load_feedback(data_dir: Path, recording_type: Optional[str] = None) -> List[dict]:
    """Load all feedback entries from ratings.jsonl.

    Args:
        data_dir: Data directory containing feedback
        recording_type: Filter to specific type (e.g., 'studio', 'metal')

    Returns:
        List of feedback entries
    """
    feedback_file = data_dir / "personal" / "feedback" / "ratings.jsonl"

    if not feedback_file.exists():
        return []

    ratings = []
    try:
        with open(feedback_file, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if recording_type is None or entry.get("detected_type") == recording_type:
                        ratings.append(entry)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load feedback: {e}")

    return ratings


def extract_feedback_keywords(comments: List[str]) -> Dict[str, int]:
    """Extract parameter names from feedback comments.

    Args:
        comments: List of user comments

    Returns:
        Dictionary of parameter names and mention counts
    """
    keywords = ["bass", "treble", "mid", "stereo", "bright", "dark", "narrow", "wide"]
    counts = {k: 0 for k in keywords}

    for comment in comments:
        comment_lower = comment.lower()
        for keyword in keywords:
            counts[keyword] += comment_lower.count(keyword)

    return {k: v for k, v in counts.items() if v > 0}


def analyze_by_type(data_dir: Path, recording_type: str) -> None:
    """Analyze feedback for a specific recording type.

    Args:
        data_dir: Data directory
        recording_type: Type to analyze (e.g., 'studio')
    """
    ratings = load_feedback(data_dir, recording_type)

    if not ratings:
        print(f"No feedback yet for {recording_type}")
        return

    print(f"\n{'=' * 70}")
    print(f"{recording_type.upper()} Profile Analysis")
    print(f"{'=' * 70}")
    print(f"Samples: {len(ratings)}")

    # Rating statistics
    rating_values = [r["rating"] for r in ratings]
    avg_rating = mean(rating_values)
    print(f"Average Rating: {avg_rating:.1f}/5.0")

    if len(rating_values) > 1:
        print(f"Std Dev: {stdev(rating_values):.2f}")
        print(f"Range: {min(rating_values)} - {max(rating_values)}")

    # Confidence analysis
    confidences = [r["confidence"] for r in ratings]
    avg_conf = mean(confidences)
    print(f"Average Confidence: {avg_conf:.0%}")

    # Extract feedback patterns
    comments = [r.get("comment", "") for r in ratings if r.get("comment")]
    keywords = extract_feedback_keywords(comments)

    if keywords:
        print(f"\nFeedback Patterns:")
        for keyword, count in sorted(keywords.items(), key=lambda x: x[1], reverse=True):
            print(f"  '{keyword}' mentioned {count} times")

    # Recommendations
    print(f"\nRecommendations:")
    if len(ratings) < 5:
        print(f"  (Need at least 5 samples for reliable patterns, have {len(ratings)})")
    else:
        made_recommendation = False

        if "bass" in keywords and keywords["bass"] >= 3:
            print(f"  → Consider bass adjustment (+0.3 to +0.5 dB)")
            made_recommendation = True

        if ("bright" in keywords or "harsh" in keywords) and keywords.get("bright", 0) + keywords.get("harsh", 0) >= 2:
            print(f"  → Consider treble reduction (-0.2 to -0.3 dB)")
            made_recommendation = True

        if "narrow" in keywords and keywords.get("narrow", 0) >= 2:
            print(f"  → Consider stereo width increase (+0.05 to +0.10)")
            made_recommendation = True

        if avg_rating < 3.5:
            print(f"  → Profile not satisfying users. Consider profile expansion.")
            made_recommendation = True

        if avg_rating > 4.3 and avg_conf < 0.7:
            print(f"  → Low confidence but high satisfaction. Consider raising confidence threshold.")
            made_recommendation = True

        if not made_recommendation:
            print(f"  No clear patterns yet. Keep collecting feedback.")

    # Rating distribution
    print(f"\nRating Distribution:")
    for star in range(5, 0, -1):
        count = sum(1 for r in rating_values if r == star)
        bar = "█" * count
        print(f"  {star}★: {bar} ({count})")

    print(f"{'=' * 70}\n")


def analyze_all_types(data_dir: Path) -> None:
    """Analyze feedback across all recording types.

    Args:
        data_dir: Data directory
    """
    all_ratings = load_feedback(data_dir)

    if not all_ratings:
        print("No feedback collected yet.")
        return

    # Group by type
    by_type = {}
    for rating in all_ratings:
        t = rating.get("detected_type", "unknown")
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(rating)

    print(f"\n{'=' * 70}")
    print("Feedback Summary Across All Types")
    print(f"{'=' * 70}")
    print(f"Total Samples: {len(all_ratings)}")
    print(f"\nBy Type:")

    for recording_type in sorted(by_type.keys()):
        ratings_for_type = by_type[recording_type]
        rating_values = [r["rating"] for r in ratings_for_type]
        avg_rating = mean(rating_values)
        print(f"  {recording_type.upper():15} {len(ratings_for_type):3} samples, {avg_rating:.1f}/5.0 avg")

    print(f"{'=' * 70}\n")

    # Detailed analysis for each type
    for recording_type in sorted(by_type.keys()):
        analyze_by_type(data_dir, recording_type)


def analyze_monthly_summary(data_dir: Path) -> None:
    """Show monthly summary of feedback trends.

    Args:
        data_dir: Data directory
    """
    ratings = load_feedback(data_dir)

    if not ratings:
        print("No feedback collected yet.")
        return

    # Group by week
    from datetime import datetime, timedelta

    by_week = {}
    for rating in ratings:
        try:
            timestamp = datetime.fromisoformat(rating.get("timestamp", ""))
            week_key = timestamp.strftime("%Y-W%V")
            if week_key not in by_week:
                by_week[week_key] = []
            by_week[week_key].append(rating)
        except (ValueError, AttributeError):
            pass

    print(f"\n{'=' * 70}")
    print("Monthly Feedback Summary")
    print(f"{'=' * 70}")

    for week_key in sorted(by_week.keys()):
        week_ratings = by_week[week_key]
        rating_values = [r["rating"] for r in week_ratings]
        avg_rating = mean(rating_values)

        print(f"\n{week_key}:")
        print(f"  Samples: {len(week_ratings)}")
        print(f"  Avg Rating: {avg_rating:.1f}/5.0")

        # Count by type
        by_type = {}
        for r in week_ratings:
            t = r.get("detected_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        for t in sorted(by_type.keys()):
            print(f"    {t}: {by_type[t]}")

    print(f"\n{'=' * 70}\n")


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze feedback patterns and suggest adjustments",
        epilog="Examples:\n"
               "  ./scripts/analyze_feedback.py --type studio\n"
               "  ./scripts/analyze_feedback.py --all-types\n"
               "  ./scripts/analyze_feedback.py --monthly-summary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--type",
        help="Analyze specific recording type (e.g., studio, metal, bootleg)"
    )
    group.add_argument(
        "--all-types",
        action="store_true",
        help="Analyze all recording types"
    )
    group.add_argument(
        "--monthly-summary",
        action="store_true",
        help="Show monthly summary of trends"
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Data directory (defaults to ~/.auralis)",
        default=None,
    )

    args = parser.parse_args()

    # Determine data directory
    if args.data_dir is None:
        data_dir = Path.home() / ".auralis"
    else:
        data_dir = args.data_dir

    # Run appropriate analysis
    if args.type:
        analyze_by_type(data_dir, args.type)
    elif args.all_types:
        analyze_all_types(data_dir)
    elif args.monthly_summary:
        analyze_monthly_summary(data_dir)


if __name__ == "__main__":
    main()
