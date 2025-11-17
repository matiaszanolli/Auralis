# Phase 7: Personalized Mastering Architecture

**Date**: November 17, 2025
**Vision**: Base Model + Personal Preferences = Truly Personalized Mastering
**Scope**: Local-first, privacy-preserving, infinitely customizable

---

## The Insight

Current mastering systems work one of two ways:

**Option A: Generic Presets**
- "Warm", "Bright", "Punchy"
- One size fits nobody perfectly
- No personalization

**Option B: Professional Engineers**
- Perfect for professional studios
- Too expensive for personal use
- Not scalable

**Option C: Our Approach (NEW)**
- Start with **professionally-trained base model** (objective)
- Layer on **personal preferences** (subjective)
- Result: Mastering that matches both technical quality AND your hearing

---

## Three-Tier Architecture

### Tier 1: Base Model (Auralis-Provided)
**What**: Professional fingerprints + proven profiles
**How**: Trained on:
- Real professional remasters (Steven Wilson, Matchering, etc.)
- Verified high-quality masters
- Acoustic physics (spectral analysis)

**Version**: v1.0, v1.1, v2.0 (updated every major version)
**Purpose**: "This is what good mastering sounds like objectively"
**Example**:
```
Base Model v1.0
  Studio (HD Bright): +1.5dB bass, +2.0dB treble, 0.13 stereo
  Metal: +3.85dB bass, -1.22dB treble, 0.35 stereo
  Bootleg: -4.0dB bass, +4.0dB treble, 0.20 stereo
```

### Tier 2: Personal Preferences (User-Generated)
**What**: Your adjustments on top of the base model
**How**: Generated from:
- Your ratings of processed tracks
- Your feedback comments
- Your listening patterns
- Your gear/hearing characteristics

**Version**: Personal, always evolving
**Purpose**: "This is what good mastering sounds like to ME"
**Example**:
```
Your Personal Profile v1.2 (after 50 tracks)
  Adjustment to Studio: +0.3dB bass (you like more punch)
  Adjustment to Metal: -0.3dB treble (you find it harsh)
  Stereo preference: consistently -0.05 narrower
  Confidence boost: +0.05 (you trust the detector)
```

### Tier 3: Distributed Learning (Community)
**What**: Aggregated insights from all users
**How**: Generated from:
- Anonymized user feedback (optional opt-in)
- Cross-device patterns
- Mastering outcome comparisons

**Version**: Feeds into next major base model version
**Purpose**: "What did millions of listeners prefer?"
**Example**:
```
Distributed Insights (for v2.0 training)
  Studio profiles: 85% of users prefer +0.2dB more bass
  Metal profiles: Users with bright gear prefer -0.3dB treble
  Confidence calibration: Model confidence correlates 0.92 with user satisfaction
```

---

## Data Flow: Personal Mastering Loop

### Step 1: User Processes Audio
```
Your Track
    ↓
[Base Model v1.0 detects: Studio, 85% confidence]
[Generates: +1.5dB bass, +2.0dB treble]
    ↓
[Apply Your Personal Layer]
[Your preference: +0.3dB bass adjustment]
    ↓
Final Processing: +1.8dB bass, +2.0dB treble
    ↓
Mastered Audio
```

### Step 2: User Rates Result
```
You listen: "Pretty good, but needs slightly more bass"
    ↓
./scripts/rate_track.py track.flac --rating 4 --comment "more bass"
    ↓
Saved to: data/personal/feedback/track_001.json
    ↓
Feedback Aggregator (runs weekly)
    ↓
Analyzed: "Bass mentioned in 7/12 recent ratings"
    ↓
Personal profile adjusted: studio bass +0.5dB (from +0.3dB)
    ↓
Next track processed with new personal layer applied
```

### Step 3: Personal Layer Evolves
```
Week 1:  5 ratings collected → personal profile v1.0
Week 2:  +5 more ratings → feedback shows "bass" pattern → profile v1.1
Week 3:  +5 more ratings → pattern confirmed → profile v1.2
Month 1: 50 ratings → stable adjustments → personal profile mature

Your mastering now:
- Matches technical excellence (base model)
- Matches your hearing preferences (personal layer)
- Continuously improving (feedback-driven)
```

---

## Implementation: Three Files, Three Layers

### File Structure
```
matchering/
├── data/
│   ├── base_model/                    # Provided by Auralis
│   │   └── v1.0/
│   │       ├── studio_hd_bright.json
│   │       ├── metal_bright.json
│   │       ├── bootleg_dark.json
│   │       └── model_metadata.json
│   │
│   └── personal/                      # Your adjustments
│       ├── feedback/                  # Your ratings
│       │   └── ratings.jsonl
│       ├── preferences/               # Your adjustments layer
│       │   ├── personal_v1.0.json
│       │   ├── personal_v1.1.json
│       │   └── versions.json
│       └── stats/
│           └── preference_analysis.json
│
└── scripts/
    ├── rate_track.py                  # 20 lines
    ├── analyze_personal_preferences.py # 30 lines
    ├── apply_personal_layer.py        # 50 lines
    └── export_personal_profile.py     # 20 lines
```

### Implementation: Personal Preference Layer

**File**: `auralis/core/personal_preferences.py`

```python
"""Personal preference layer - applies on top of base model."""

from dataclasses import dataclass
from typing import Dict
import json
from pathlib import Path

@dataclass
class PersonalPreferences:
    """User's personal adjustments to base profiles."""

    # Per-profile adjustments
    profile_adjustments: Dict[str, float]  # {"studio_bass": +0.3, "metal_treble": -0.2}

    # Per-characteristic adjustments
    centroid_preference: float = 0.0      # Brighter/darker preference
    stereo_width_preference: float = 0.0  # Wider/narrower preference
    confidence_adjustment: float = 0.0    # Trust the detector more/less

    # Gear/hearing characteristics
    gear_profile: str = "neutral"         # "bright_headphones", "dark_speakers", etc.
    hearing_profile: str = "normal"       # "bass_sensitive", "treble_sensitive", etc.

    def apply_to_parameters(self, base_params: dict) -> dict:
        """Apply personal preferences to base model parameters."""

        adjusted = base_params.copy()

        # Apply direct adjustments
        for param, adjustment in self.profile_adjustments.items():
            if param in adjusted:
                adjusted[param] += adjustment

        # Apply characteristic preferences
        if self.centroid_preference != 0:
            adjusted["target_spectral_centroid_hz"] += self.centroid_preference * 500

        if self.stereo_width_preference != 0:
            adjusted["stereo_width_target"] += self.stereo_width_preference * 0.1

        return adjusted

    @staticmethod
    def load_or_create(user_data_dir: Path):
        """Load personal preferences or create defaults."""
        prefs_file = user_data_dir / "personal/preferences/current.json"

        if prefs_file.exists():
            data = json.loads(prefs_file.read_text())
            return PersonalPreferences(**data)

        # Default: no adjustments
        return PersonalPreferences(profile_adjustments={})

    def save(self, user_data_dir: Path, version: str):
        """Save personal preferences with version."""
        prefs_dir = user_data_dir / "personal/preferences"
        prefs_dir.mkdir(parents=True, exist_ok=True)

        # Versioned file
        version_file = prefs_dir / f"personal_{version}.json"
        version_file.write_text(json.dumps({
            "profile_adjustments": self.profile_adjustments,
            "centroid_preference": self.centroid_preference,
            "stereo_width_preference": self.stereo_width_preference,
            "confidence_adjustment": self.confidence_adjustment,
            "gear_profile": self.gear_profile,
            "hearing_profile": self.hearing_profile,
        }, indent=2))

        # Current pointer
        current_file = prefs_dir / "current.json"
        current_file.write_text(version_file.read_text())
```

### Integration into Processing Pipeline

**File**: `auralis/core/processing/continuous_mode.py` (modification)

```python
def process(self, audio, sr):
    """Enhanced: apply personal preferences on top of base model."""

    # ... existing processing ...

    # 1. Detect recording type (base model)
    recording_type, adaptive_params = self.detector.detect(audio, sr)

    # 2. Load personal preferences
    personal_prefs = PersonalPreferences.load_or_create(Path.home() / ".auralis")

    # 3. Apply personal layer on top of base model
    adjusted_params = personal_prefs.apply_to_parameters({
        "bass_adjustment_db": adaptive_params.bass_adjustment_db,
        "mid_adjustment_db": adaptive_params.mid_adjustment_db,
        "treble_adjustment_db": adaptive_params.treble_adjustment_db,
        "stereo_width_target": adaptive_params.stereo_width_target,
        # ... other params ...
    })

    # 4. Continue with adjusted parameters
    # ... rest of processing ...

    return processed_audio, {
        "base_model_params": adaptive_params,
        "personal_adjustments": personal_prefs.profile_adjustments,
        "final_params": adjusted_params,
    }
```

---

## The Learning Flow

### Your First Week
```
Day 1: Process track 1 → Rate 3★ → "too bright"
Day 2: Process track 2 → Rate 5★ → "perfect!"
Day 3: Process track 3 → Rate 4★ → "close, needs bass"
...
Day 7: Analyze → "Users rates 4.1/5, treble feedback common"

Personal profile v1.0 created:
  treble_adjustment: -0.2dB
```

### Your First Month
```
Week 2: 5 more ratings → pattern shows "bass wanted" → profile v1.1
         bass_adjustment: +0.3dB

Week 3: Stereo width feedback emerges → profile v1.2
         stereo_width_preference: -0.05

Week 4: Confidence high (ratings 4.2/5) → profile v1.3
         confidence_adjustment: +0.05

Personal profile now mature, tracks sound "just right"
```

### After 3 Months
```
200+ ratings collected across all types
Personal profile v2.0 reflects:
  - Your hearing characteristics
  - Your gear (headphones/speakers)
  - Your music taste
  - Your preferences on every parameter

Base model + Your layer = Perfect for you
```

---

## Distributed Learning: Feeding Back to Auralis

### Optional: Share Feedback
```bash
# User has option to share their feedback (anonymized)
./scripts/export_feedback.py --anonymized --destination auralis-project
```

### What Gets Shared
```json
{
  "feedback": [
    {
      "base_model": "v1.0",
      "detected_type": "studio",
      "rating": 4,
      "adjustments_that_helped": {
        "bass": +0.3,
        "treble": -0.2
      }
    },
    // ... 100+ more ratings
  ],
  "gear_profile": "bright_headphones",
  "hearing_profile": "normal"
  // No identifying information
}
```

### What Doesn't Get Shared
```
❌ Audio files
❌ Your identity
❌ Specific track names
❌ Personal comments (unless you explicitly allow)
❌ Any identifying metadata
```

### How It Helps Next Version
```
Auralis v2.0 Training (2026):
  Collects anonymized feedback from 100+ users
  Finds patterns:
    - "Studio profiles need +0.2dB more bass on average"
    - "Metal profiles: bright gear users prefer -0.3dB treble"
    - "Confidence threshold should be 0.62, not 0.65"

  Updates base model with these insights

  v2.0 released with better defaults
  Users still keep their personal adjustments (which still help!)
```

---

## Complete Workflow Example: You

### Setup (5 minutes)
```bash
# Clone/install Auralis
# First run creates:
# - ~/.auralis/data/personal/
# - personal preferences (empty)
# - feedback storage

./scripts/init_personal_setup.py
# ✓ Personal mastering system ready
```

### Daily (2 minutes per track)
```bash
# 1. Process track (existing UI)
python launch-auralis-web.py --dev
# Process your music...

# 2. Rate it (5 seconds)
./scripts/rate_track.py ~/Music/track.flac --rating 4 --comment "more bass"

# Done! Feedback captured, personal preferences will improve
```

### Weekly (5 minutes)
```bash
# Analyze patterns
./scripts/analyze_personal_preferences.py

# Output:
# Personal Mastering Profile v1.X
# Average satisfaction: 4.2/5 (you're happy!)
# Patterns: bass +0.3dB, treble -0.2dB working well
# New observation: stereo width feedback suggests -0.05 adjustment
```

### Monthly (optional)
```bash
# Update personal profile
./scripts/update_personal_profile.py --apply-patterns

# Or manually
./scripts/update_personal_profile.py \
  --studio-bass 1.8 \
  --metal-treble 1.8 \
  --reason "feedback patterns"

# Personal profile v1.5 created
# Tests run automatically
# Everything committed to git
```

---

## Privacy & Control: All Local

### Where Data Lives
- **Base Model**: Downloaded once from Auralis (read-only)
- **Personal Data**: Always local (`~/.auralis/`) - NEVER sent anywhere
- **Optional Sharing**: User explicitly exports if they want to share

### User Controls
```bash
# See what you've shared
./scripts/view_shared_feedback.py

# Delete feedback
./scripts/delete_feedback.py --older-than 90-days

# Opt-out of sharing
./scripts/disable_sharing.py

# Full export (backup)
./scripts/export_personal_data.py --format tar.gz
```

---

## The Beautiful Part

### For You (Solo User)
- ✅ Base model handles objective quality
- ✅ Personal layer captures your hearing
- ✅ Continuous improvement without work
- ✅ Eventually "just works" perfectly for you
- ✅ All data stays local

### For Auralis v2.0 (Next Version)
- ✅ Better defaults from user feedback patterns
- ✅ More confident profiling
- ✅ Addresses real problems (not guesses)
- ✅ Still optional to share

### For Other Users
- ✅ Can use v2.0 base model straight
- ✅ Can layer their own preferences on top
- ✅ No tracking, no privacy concerns
- ✅ Complete control and transparency

---

## Implementation Timeline

### Phase 6.3 (This week)
- [ ] Implement `PersonalPreferences` class
- [ ] Integrate into processing pipeline
- [ ] Create rating script
- [ ] Create analysis script

### Phase 6.4 (Next week)
- [ ] Profile update script
- [ ] Versioning system
- [ ] Test personal layer with real ratings

### Phase 7 (2-4 weeks)
- [ ] Finalize personal mastering system
- [ ] Optional sharing infrastructure
- [ ] Documentation for distribution
- [ ] v1.0 release

---

## Comparison: Before & After

### Before (Generic Presets)
```
Your track → "Warm" preset → Generic mastering
Same parameters for everyone
No learning from your feedback
```

### After (Personalized Mastering)
```
Your track
    ↓
Base Model: "This is technically good mastering"
    ↓
+ Your Personal Layer: "This matches how I hear music"
    ↓
Result: Mastering that's both objective AND personal
    ↓
Feedback: Continuously refines your layer
    ↓
Over time: Perfect for YOU
```

---

## The Vision

**Auralis = Professional Mastering + Personal Preferences**

Most people hear things differently:
- Different ears (hearing sensitivity)
- Different gear (headphones vs speakers)
- Different music taste (bass-heavy metal fan vs acoustic purist)
- Different purpose (stream vs vinyl)

Our system respects this:
1. **Base Model**: "What does professional mastering sound like?"
2. **Personal Layer**: "What does professional mastering sound like to ME?"
3. **Result**: Mastering that's personalized at scale, impossible with traditional approaches

---

**Created**: November 17, 2025
**Vision**: Objective base + subjective preferences = truly personalized mastering
**Privacy**: Local-first, user-controlled, fully transparent
**Timeline**: Phase 6.3-7, ready by month-end

