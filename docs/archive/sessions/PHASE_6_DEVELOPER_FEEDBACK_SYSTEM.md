# Phase 6.3+: Developer-Focused Feedback & Retraining System

**Date**: November 17, 2025
**Context**: Single developer (you) using the system to master your own music
**Goal**: Fast feedback loop + quick profile updates without UI overhead

---

## Key Insight: Simplify for Solo Developer

Instead of:
- ❌ User-facing feedback widgets
- ❌ Aggregation dashboards
- ❌ Complex UI for rating tracks

Do:
- ✅ CLI commands for quick feedback
- ✅ Simple JSON tracking
- ✅ Automated profile updates
- ✅ Git-tracked versions for easy rollback

---

## Architecture: Three CLI Tools

### Tool 1: Rate Track (2 seconds)
```bash
./scripts/rate_track.py deep_purple_speed_king.flac --rating 4 --comment "bass could be +0.3"
```

Saves to:
```json
{
  "track": "deep_purple_speed_king.flac",
  "detected_type": "studio",
  "confidence": 0.85,
  "rating": 4,
  "comment": "bass could be +0.3",
  "timestamp": "2025-11-17T21:35:00Z",
  "fingerprint": {...},
  "parameters_applied": {...}
}
```

### Tool 2: Analyze Feedback (1 minute)
```bash
./scripts/analyze_feedback.py --type studio --show-patterns
```

Output:
```
Studio Profile (HD Bright Transparent) - v1.0
========================================
Samples: 12
Average Rating: 4.1/5
Confidence Calibration: 0.92 (very good)

Feedback Patterns:
  "bass" mentioned 3 times → +0.3dB adjustment suggested
  "harsh treble" mentioned 2 times → -0.2dB treble suggested
  "too narrow" mentioned 0 times ✓ (stereo width good)

Top Ratings: 5 stars (1 sample) - "Perfect!"
Bottom Ratings: 3 stars (1 sample) - "bit bass-heavy"

Recommendation: Small bass boost (+0.3dB) would help
```

### Tool 3: Update Profile (30 seconds)
```bash
./scripts/update_profile.py studio --apply-suggestion bass=+0.3 --reason "user feedback"
```

Output:
```
Profile Updated: studio_hd_bright
  v1.0 → v1.1

Changes:
  - bass_adjustment_db: +1.5 → +1.8dB (+0.3dB increase)
  - reason: "user feedback - bass +0.3"

Test:
  Running 12 validation tests...
  ✓ All pass (no regressions)

Commit: git add -A && git commit -m "refactor: studio profile v1.1 - boost bass"
```

---

## File Structure: Developer Workflow

```
matchering/
├── data/
│   ├── feedback/
│   │   ├── ratings.jsonl          # One JSON per line = one rating
│   │   └── patterns.json           # Aggregated patterns (auto-generated)
│   └── profiles/
│       ├── studio_hd_bright_v1.0.json
│       ├── studio_hd_bright_v1.1.json  (after first feedback)
│       ├── studio_hd_bright_v1.2.json
│       └── versions.json           # Version tracking
├── scripts/
│   ├── rate_track.py               # Quick feedback capture
│   ├── analyze_feedback.py         # Pattern analysis
│   ├── update_profile.py           # Apply adjustments
│   ├── test_profile.py             # Quick validation
│   └── export_profiles.py          # For distribution
└── docs/
    └── FEEDBACK_WORKFLOW.md        # This process documented
```

---

## Workflow: Your Typical Day

### Morning: Process a Track
```bash
# 1. Load track, run mastering
python launch-auralis-web.py --dev
# (Process your track in UI)
# Deep Purple Speed King → STUDIO detected, 85% confidence

# 2. Listen to result (30 seconds)
# "Pretty good, but could use slightly more bass"

# 3. Rate it (5 seconds)
./scripts/rate_track.py \
  deep_purple_speed_king.flac \
  --rating 4 \
  --comment "bass could be +0.3dB"

# File saved to: data/feedback/ratings.jsonl
```

### Weekly: Analyze & Update Profiles
```bash
# 1. See what patterns emerged (1 minute)
./scripts/analyze_feedback.py --type studio

# Output shows:
# - "bass" mentioned 3 times
# - Average rating: 4.1/5
# - Suggestion: +0.3dB bass boost

# 2. Update profile (30 seconds)
./scripts/update_profile.py studio --apply-suggestion bass=+0.3

# Tests run automatically
# Git commit created automatically
# Profile v1.0 → v1.1

# 3. Test on your library (optional)
./scripts/test_profile.py studio --sample-size 5
# Runs detector on 5 random tracks with new profile
# Compares to old profile results
```

### Monthly: Review & Release
```bash
# See all profile changes made
git log --oneline data/profiles/

# Check feedback distribution
./scripts/analyze_feedback.py --monthly-summary

# Export new profiles for distribution
./scripts/export_profiles.py --version 1.1 --output-dir dist/

# Create release notes
git tag -a v1.1 -m "Profile updates: studio bass +0.3, metal treble -0.2"
```

---

## Implementation: Tool #1 - Rate Track

**File**: `scripts/rate_track.py`

```python
#!/usr/bin/env python3
"""Quick track rating for feedback collection."""

import json
import argparse
from pathlib import Path
from datetime import datetime
from auralis.core.recording_type_detector import RecordingTypeDetector
from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
import librosa

def rate_track(audio_file, rating, comment=None):
    """Rate a mastered track and save feedback."""

    # Load audio and get fingerprint
    audio, sr = librosa.load(audio_file, sr=44100, mono=False)

    detector = RecordingTypeDetector()
    analyzer = AudioFingerprintAnalyzer()

    recording_type, adaptive_params = detector.detect(audio, sr)
    fingerprint = analyzer.analyze(audio, sr)

    # Create feedback entry
    feedback = {
        "track": str(audio_file),
        "detected_type": recording_type.value,
        "confidence": float(adaptive_params.confidence),
        "philosophy": adaptive_params.mastering_philosophy,
        "rating": rating,
        "comment": comment,
        "timestamp": datetime.now().isoformat(),
        "fingerprint": {
            "centroid_hz": float(fingerprint.get('spectral_centroid', 0) * 20000),
            "bass_to_mid": float(fingerprint.get('bass_mid_ratio', 0)),
            "stereo_width": float(fingerprint.get('stereo_width', 0)),
            "crest_db": float(fingerprint.get('crest_db', 0)),
        },
        "parameters_applied": {
            "bass_adjustment_db": adaptive_params.bass_adjustment_db,
            "mid_adjustment_db": adaptive_params.mid_adjustment_db,
            "treble_adjustment_db": adaptive_params.treble_adjustment_db,
            "stereo_strategy": adaptive_params.stereo_strategy,
        }
    }

    # Append to ratings.jsonl (one JSON per line)
    feedback_file = Path("data/feedback/ratings.jsonl")
    feedback_file.parent.mkdir(parents=True, exist_ok=True)

    with open(feedback_file, "a") as f:
        f.write(json.dumps(feedback) + "\n")

    # Print summary
    print(f"✓ Rated: {Path(audio_file).name}")
    print(f"  Type: {recording_type.value} ({adaptive_params.confidence:.0%} confidence)")
    print(f"  Rating: {'⭐' * rating} ({rating}/5)")
    if comment:
        print(f"  Note: {comment}")
    print(f"  Saved to: {feedback_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rate a track for feedback")
    parser.add_argument("audio_file", help="Path to audio file")
    parser.add_argument("--rating", type=int, required=True, choices=[1,2,3,4,5])
    parser.add_argument("--comment", help="Optional feedback comment")

    args = parser.parse_args()
    rate_track(args.audio_file, args.rating, args.comment)
```

---

## Implementation: Tool #2 - Analyze Feedback

**File**: `scripts/analyze_feedback.py`

```python
#!/usr/bin/env python3
"""Analyze feedback patterns and suggest adjustments."""

import json
import argparse
from pathlib import Path
from collections import Counter
from statistics import mean, stdev

def analyze_feedback(recording_type):
    """Analyze all feedback for a recording type."""

    feedback_file = Path("data/feedback/ratings.jsonl")

    # Load all ratings
    ratings = []
    with open(feedback_file, "r") as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                if entry["detected_type"] == recording_type:
                    ratings.append(entry)

    if not ratings:
        print(f"No feedback yet for {recording_type}")
        return

    # Analyze
    print(f"\n{recording_type.upper()} Profile Analysis")
    print("=" * 50)
    print(f"Samples: {len(ratings)}")
    print(f"Average Rating: {mean([r['rating'] for r in ratings]):.1f}/5.0")

    # Extract feedback patterns (simple word frequency)
    all_comments = " ".join([r.get('comment', '') for r in ratings])
    words = all_comments.lower().split()

    # Look for parameter names
    params = ["bass", "treble", "mid", "stereo", "bright", "dark", "narrow", "wide"]
    print(f"\nFeedback Patterns:")
    for param in params:
        count = sum(1 for r in ratings if param in r.get('comment', '').lower())
        if count > 0:
            print(f"  '{param}' mentioned {count} times")

    # Suggestions
    print(f"\nRecommendations:")
    if "bass" in all_comments.lower() and "bass" not in ["reduce", "less"]:
        print(f"  → Consider +0.3dB bass adjustment")
    if "harsh" in all_comments.lower() or "bright" in all_comments.lower():
        print(f"  → Consider -0.2dB treble adjustment")

    # Distribution
    print(f"\nRating Distribution:")
    for star in range(5, 0, -1):
        count = sum(1 for r in ratings if r['rating'] == star)
        print(f"  {star}★: {'█' * count} ({count})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze feedback patterns")
    parser.add_argument("--type", required=True, help="Recording type to analyze")

    args = parser.parse_args()
    analyze_feedback(args.type)
```

---

## Implementation: Tool #3 - Update Profile

**File**: `scripts/update_profile.py`

```python
#!/usr/bin/env python3
"""Update profile based on feedback."""

import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
import shutil

def update_profile(recording_type, adjustments, reason):
    """Update a profile and version it."""

    # Load current profile
    profile_dir = Path("data/profiles")
    profile_files = list(profile_dir.glob(f"{recording_type}_hd_bright_v*.json"))

    if not profile_files:
        print(f"No profile found for {recording_type}")
        return

    # Find latest version
    latest = sorted(profile_files)[-1]
    current = json.loads(latest.read_text())

    # Parse version
    version_str = latest.stem.split("_v")[-1]
    major, minor = map(int, version_str.split("."))
    new_version = f"{major}.{minor + 1}"

    # Apply adjustments
    print(f"\nUpdating {recording_type} profile {version_str} → {new_version}")
    print("=" * 50)

    for param, value in adjustments.items():
        if param in current:
            old_value = current[param]
            current[param] = value
            print(f"  {param}: {old_value} → {value}")
        else:
            print(f"  (unknown param: {param})")

    # Save new version
    new_file = latest.parent / f"{recording_type}_hd_bright_v{new_version}.json"
    new_file.write_text(json.dumps(current, indent=2))

    # Run tests
    print(f"\nRunning validation tests...")
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/auralis/test_recording_type_detector.py", "-v"],
        capture_output=True
    )

    if result.returncode == 0:
        print(f"  ✓ All tests pass")

        # Git commit
        subprocess.run([
            "git", "add", str(new_file),
            "-m", f"refactor: {recording_type} profile v{new_version} - {reason}"
        ])

        print(f"\n✓ Profile updated and committed")
        print(f"  File: {new_file.name}")
        print(f"  Reason: {reason}")
    else:
        print(f"  ✗ Tests failed - not committing")
        new_file.unlink()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update profile from feedback")
    parser.add_argument("type", help="Recording type")
    parser.add_argument("--bass", type=float, help="New bass_adjustment_db")
    parser.add_argument("--treble", type=float, help="New treble_adjustment_db")
    parser.add_argument("--reason", required=True, help="Why this change")

    args = parser.parse_args()

    adjustments = {}
    if args.bass is not None:
        adjustments["bass_adjustment_db"] = args.bass
    if args.treble is not None:
        adjustments["treble_adjustment_db"] = args.treble

    update_profile(args.type, adjustments, args.reason)
```

---

## Workflow: Your Actual Day (Real Examples)

### Example 1: Rate a Track (5 seconds)
```bash
$ ./scripts/rate_track.py ~/Music/deep_purple_speed_king.flac --rating 4 --comment "bass +0.3"
✓ Rated: deep_purple_speed_king.flac
  Type: studio (85% confidence)
  Rating: ⭐⭐⭐⭐ (4/5)
  Note: bass +0.3
  Saved to: data/feedback/ratings.jsonl
```

### Example 2: Analyze After 10 Ratings (1 minute)
```bash
$ ./scripts/analyze_feedback.py --type studio

STUDIO Profile Analysis
==================================================
Samples: 10
Average Rating: 4.2/5.0

Feedback Patterns:
  'bass' mentioned 3 times
  'harsh' mentioned 2 times
  'treble' mentioned 1 time

Recommendations:
  → Consider +0.3dB bass adjustment
  → Consider -0.2dB treble adjustment

Rating Distribution:
  5★: ███ (3)
  4★: ████ (4)
  3★: (2)
  2★: (1)
```

### Example 3: Update Profile (30 seconds)
```bash
$ ./scripts/update_profile.py studio \
    --bass 1.8 \
    --treble 1.8 \
    --reason "user feedback - bass +0.3, treble -0.2"

Updating studio profile 1.0 → 1.1
==================================================
  bass_adjustment_db: 1.5 → 1.8
  treble_adjustment_db: 2.0 → 1.8

Running validation tests...
  ✓ All tests pass

✓ Profile updated and committed
  File: studio_hd_bright_v1.1.json
  Reason: user feedback - bass +0.3, treble -0.2
```

### Example 4: Track Changes Over Time
```bash
$ git log --oneline data/profiles/

abc1234 refactor: studio profile v1.2 - boost bass further (+0.3)
def5678 refactor: studio profile v1.1 - user feedback (bass +0.3, treble -0.2)
ghi9012 refactor: studio profile v1.0 - Phase 6.2 initial profiles
```

---

## Key Benefits for Solo Developer

| Aspect | Benefit |
|--------|---------|
| **Speed** | Rate track (5s), analyze (1m), update (30s) = quick feedback loop |
| **Simplicity** | No UI, just CLI - faster than clicking around |
| **Transparency** | See exactly what changed, why, and when |
| **Reversibility** | Git tracking means easy rollback |
| **Testing** | Auto-validate every change (no breaking profiles) |
| **History** | Profile versions show learning progression |
| **Reproducibility** | Anyone can see your decisions and reasoning |

---

## Phase 6.3 Scope (Quick)

Implement just three scripts:
1. ✅ `rate_track.py` - Save feedback (20 lines)
2. ✅ `analyze_feedback.py` - Show patterns (30 lines)
3. ✅ `update_profile.py` - Apply changes (40 lines)

**Total**: ~90 lines of code, infinite utility.

---

## Next: Phase 6.4 - Full Integration

Once these tools exist:
- Run mastering on a track
- Rate it (5 seconds)
- After 10+ ratings of same type, analyze patterns
- After patterns are clear, update profile
- Re-test on library
- Commit with reasoning
- Repeat

---

**Created**: November 17, 2025
**Context**: Solo developer workflow
**Approach**: Fast CLI tools, git-tracked versions, auto-tested updates
**Time to implement**: ~2 hours
**Time saved per month**: Hours of manual tuning

