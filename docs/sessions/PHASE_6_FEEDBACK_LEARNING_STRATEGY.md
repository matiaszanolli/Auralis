# Phase 6+: Feedback Learning Strategy

**Date**: November 17, 2025
**Status**: Planning for continuous improvement
**Objective**: Design a lightweight learning system to improve fingerprinting and mastering over time

---

## Challenge

The current system has:
- ✅ Accurate 25D fingerprinting (works correctly)
- ✅ Recalibrated detection profiles (now 85% confident)
- ❓ No feedback mechanism to learn from real user results

**Problem**: We make predictions, but never learn if they're right or wrong. The system can't improve beyond Phase 6.2 boundaries without manual intervention.

---

## Solution: Lightweight Feedback Learning

Rather than building a complex ML model, we can use **simple statistical learning** that:
1. Captures user satisfaction/feedback
2. Tracks actual mastering results
3. Incrementally adjusts profiles
4. Requires minimal computational overhead

---

## Architecture: Three-Tier Learning System

### Tier 1: User Feedback Collection (Simple)
**Capture**: User rates mastering quality after processing
- ⭐⭐⭐⭐⭐ (1-5 stars)
- Optional comment: "What could be better?"
- Auto-capture: Played/skipped (engagement proxy)

**Storage**: Simple JSON file per track
```json
{
  "track_id": "deep_purple_speed_king",
  "detected_type": "studio",
  "confidence": 0.85,
  "rating": 4,
  "comment": "Excellent clarity, bass could be slightly boosted",
  "fingerprint": {...},
  "parameters_applied": {...},
  "timestamp": "2025-11-17T21:35:00Z"
}
```

### Tier 2: Aggregate Statistics (Simple Math)
**Analysis**: No ML required, just aggregation
```python
# For each detected type (e.g., "HD Bright Transparent")
average_rating = mean([r.rating for r in ratings if r.detected_type == type])
confidence_vs_rating = correlation(confidence, rating)
parameter_adjustments = mean_feedback_comments()  # Text frequency
```

**Example Output**:
```
HD Bright Transparent Profile:
  Average Rating: 4.2/5 (from 47 samples)
  Confidence Correlation: 0.78 (high confidence = good results)
  Top Feedback: "bass +0.5dB" (mentioned 12 times)
  Recommendation: Slightly increase bass in fine-tuning
```

### Tier 3: Profile Adjustment (Rule-Based)
**Update Logic**: Simple rules based on feedback patterns
```python
if avg_rating < 3.5:
    # This profile isn't working well
    adjust_boundaries(make_wider=True)  # Less strict classification

if feedback_mentions("bass", count=10+):
    # Users want more bass
    increase_bass_adjustment_db(0.5)

if confidence < 0.6 and rating > 4.0:
    # Low confidence but users like it - boost confidence threshold
    lower_confidence_threshold(0.05)
```

---

## Implementation: Minimal Model Approach

Instead of training a neural network, use **weighted adjustment formulas**:

### Formula 1: Profile Boundary Adjustment
```python
new_boundary = old_boundary + (avg_rating - 3.5) * sensitivity_factor
# If users rate 4.2/5, boundaries naturally expand slightly
# If users rate 2.8/5, boundaries contract (stricter matching)
```

### Formula 2: Parameter Fine-Tuning
```python
feedback_signal = extract_numeric_adjustments(comments)  # "bass +0.5" → 0.5
weighted_adjustment = feedback_signal * (count / total_feedback)
new_parameter = old_parameter + (weighted_adjustment * learning_rate)
```

### Formula 3: Confidence Recalibration
```python
observed_confidence = rating / 5.0  # User's implicit confidence
delta = observed_confidence - reported_confidence
new_confidence_threshold = old_threshold + (delta * learning_rate)
```

---

## Data Structure: Feedback Repository

### Directory Structure
```
data/
├── feedback/
│   ├── raw/
│   │   ├── 2025-11-17/
│   │   │   ├── track_001.json
│   │   │   ├── track_002.json
│   │   │   └── ...
│   │   └── 2025-11-18/
│   ├── aggregated/
│   │   ├── studio_hd_bright.stats.json
│   │   ├── bootleg_dark.stats.json
│   │   └── metal_bright.stats.json
│   └── profile_updates/
│       ├── studio_hd_bright_v1.0.json
│       ├── studio_hd_bright_v1.1.json (after 50 samples)
│       └── studio_hd_bright_v2.0.json (after 200 samples)
```

### Feedback Entry Schema
```python
@dataclass
class FeedbackEntry:
    track_id: str
    track_metadata: dict  # artist, album, title

    # Detection results
    detected_type: RecordingType
    confidence: float
    fingerprint: dict  # The 25D vector
    adaptive_params: AdaptiveParameters

    # Processing results
    processing_time_ms: float
    output_metrics: dict  # LUFS, peak, spectrum after

    # User feedback
    rating: int  # 1-5 stars
    comment: Optional[str]
    feedback_timestamp: datetime

    # Engagement signals
    played: bool
    skip_time_seconds: Optional[int]
    reprocessed: bool  # User re-ran processing
```

---

## Learning Pipeline: Phase 6+ Components

### Component 1: Feedback Collector (UI)
**Location**: Enhancement panel in web interface

```
┌─────────────────────────────────┐
│ How satisfied with this master? │
├─────────────────────────────────┤
│ ⭐⭐⭐⭐⭐ (click to rate)        │
│ [Optional] What could improve?  │
│ [Comment text field]             │
│ [Submit Feedback]               │
└─────────────────────────────────┘
```

**Backend**: Simple POST endpoint
```python
@router.post("/enhancement/feedback")
async def submit_feedback(
    track_id: str,
    detected_type: str,
    confidence: float,
    rating: int,
    comment: Optional[str] = None
):
    # Save to feedback/raw/{date}/track.json
    # Trigger aggregation if threshold met
    return {"status": "saved"}
```

### Component 2: Aggregator (Batch Job)
**Runs**: Every 24 hours or after N new samples
```python
def aggregate_daily_feedback():
    """Summarize feedback by detected type."""
    for detected_type in RecordingType:
        samples = load_feedback(detected_type)

        if len(samples) >= MIN_SAMPLES:  # 30+ per type
            stats = compute_statistics(samples)
            recommend_adjustments(stats)
            save_stats_report(stats)
```

### Component 3: Profile Adjuster (Rule Engine)
**Runs**: Weekly or when significant patterns emerge
```python
def update_profiles_from_feedback():
    """Adjust detection boundaries and parameters."""
    for profile in PROFILES:
        stats = load_stats(profile.type)

        if should_update(stats):
            new_profile = profile.clone()

            # Adjust boundaries
            if stats.avg_rating < 3.5:
                new_profile.expand_boundaries(rate=0.1)

            # Adjust parameters
            for param, feedback_value in stats.requested_adjustments.items():
                new_profile[param] += feedback_value * LEARNING_RATE

            save_profile_version(new_profile, version_bump=True)
            log_changes(profile, new_profile)
```

### Component 4: Version Control
**Track profile evolution**:
```
studio_hd_bright_v1.0.json  (Initial Phase 6.2)
  └─ Used for: samples 1-50
  └─ Avg rating: 4.1/5

studio_hd_bright_v1.1.json  (After 50 samples)
  └─ Changes: bass +0.3dB, confidence threshold -0.05
  └─ Used for: samples 51-120
  └─ Avg rating: 4.3/5

studio_hd_bright_v2.0.json  (After 200 samples)
  └─ Major revision based on feedback patterns
  └─ Changes: centroid range +200Hz, new stereo strategy
  └─ Used for: samples 121+
```

---

## Feedback Patterns to Watch For

### Pattern 1: Rating Bias
```python
if profile.confidence < 0.6 and avg_rating > 4.0:
    # Users like low-confidence detections
    # → Lower confidence threshold

if profile.confidence > 0.9 and avg_rating < 3.0:
    # High confidence but low satisfaction
    # → Expand profile boundaries
```

### Pattern 2: Parameter Drift
```python
if comments_mention("bass", 15+ times):
    # Strong bass adjustment signal
    increase_bass_adjustment(0.5)

if comments_mention("harsh", 8+ times):
    # Treble adjustment needed
    decrease_treble_adjustment(0.3)
```

### Pattern 3: Profile Confusion
```python
if (detected_type_A.avg_confidence > 0.85 and
    detected_type_B.avg_confidence > 0.85 and
    both_get_4.5_ratings):
    # Two profiles solving same problem
    # → Merge or refine boundary between them
```

---

## Data Privacy & Ethics

### What NOT to Collect
- ❌ Audio waveform data
- ❌ User identity (just track metadata)
- ❌ Personal information

### What We Collect
- ✅ Anonymized feedback (rating + comment)
- ✅ Fingerprint (acoustic signature, not audio)
- ✅ Processing parameters (non-user-specific)
- ✅ Engagement signals (play/skip)

### User Control
- Users can opt-out of feedback collection
- Feedback data stored locally (not transmitted)
- Users can view/delete their feedback
- Option to make feedback anonymous

---

## Learning Rates & Stability

### Conservative Learning Strategy
```python
LEARNING_RATE_INITIAL = 0.1  # First adjustments are small
LEARNING_RATE_MIN_SAMPLES = 30  # Require 30 samples before updating
LEARNING_RATE_THRESHOLD = 0.65  # Only adjust if pattern is 65%+ consistent
PROFILE_VERSION_BUMP = 100  # Version bump after 100 samples minimum
```

### Stability Checks
```python
def is_adjustment_stable(before, after, feedback_samples):
    """Check if proposed adjustment is based on real pattern."""
    # 1. Minimum sample size check
    if len(feedback_samples) < 30:
        return False

    # 2. Consistency check (75%+ agreement on direction)
    agree_direction = sum(1 for s in feedback_samples if
                          (s.rating > 3.5) == (after > before))
    if agree_direction / len(feedback_samples) < 0.75:
        return False

    # 3. Effect size check (must be meaningful)
    effect_size = abs(after - before) / before
    if effect_size < 0.05:  # <5% change
        return False

    return True
```

---

## Integration with Existing System

### No Breaking Changes
- Feedback collection is **optional** (users can opt-out)
- Profiles remain valid even without feedback
- System works identically with or without user input
- Fallback: Use Phase 6.2 profiles if feedback data unavailable

### Enhancement Points
```python
# In processing pipeline (continuous_mode.py)
if ENABLE_FEEDBACK_COLLECTION:
    log_feedback_datapoint(
        track_id=current_track.id,
        detected_type=recording_type,
        confidence=params.confidence,
        fingerprint=fingerprint,
        parameters=adaptive_params
    )
```

### UI Integration
```typescript
// In Enhancement Panel (React)
{feedback_enabled && (
    <FeedbackWidget
        trackId={current_track.id}
        detectedType={detectionResult.type}
        onSubmit={submitFeedback}
    />
)}
```

---

## Expected Improvement Curve

### Timeline: How Fast Does It Learn?

**Month 1**: 100-300 samples collected
- Identify major issues with profiles
- Make 1-2 major adjustments
- Estimated improvement: 2-5%

**Month 3**: 1,000+ samples
- Refine profile boundaries
- Adjust parameters based on patterns
- Estimated improvement: 5-15%

**Month 6**: 3,000+ samples
- High confidence adjustments
- New profiles may emerge (if data supports)
- Estimated improvement: 10-25%

**Year 1**: 10,000+ samples
- Profiles stabilize
- Rare edge cases handled
- Estimated improvement: 15-40%

---

## Metrics to Track

### System Metrics
- Average rating by profile type (target: 4.0+/5.0)
- Confidence calibration (target: confidence = actual accuracy)
- Processing accuracy over time (trending)

### Business Metrics
- Reprocessing rate (% of users who reprocess - should decrease)
- Engagement (play time, skip time)
- Feature adoption (% enabling feedback)

### Data Metrics
- Feedback sample size by profile
- Comment sentiment (positive/negative/neutral)
- Adjustment frequency (how often profiles change)

---

## Implementation Roadmap

### Phase 6.3 Extension
Add UI for feedback collection:
- [ ] Feedback widget in Enhancement Panel
- [ ] Rate mastering quality (1-5 stars)
- [ ] Optional text comment
- [ ] Submit button

### Phase 6.4+
Feedback storage & aggregation:
- [ ] Save feedback to local JSON files
- [ ] Daily aggregation job
- [ ] Statistics dashboard (internal)
- [ ] Change logging

### Phase 7+
Profile learning:
- [ ] Automatic profile boundary adjustment
- [ ] Parameter tuning from feedback
- [ ] Version management for profiles
- [ ] A/B testing framework (old vs new profiles)

---

## Risk Mitigation

### Risk 1: Feedback Bias
**Problem**: Users rate based on subjective preference, not objective quality
**Mitigation**:
- Weight feedback by listening patterns (frequent listeners > casual)
- Cross-check with objective metrics (LUFS, dynamic range)
- Require consensus before major changes (75%+ agreement)

### Risk 2: Profile Divergence
**Problem**: Profiles drift in opposite directions, become unstable
**Mitigation**:
- Enforce minimum profile distance (no two profiles get too similar)
- Regular profile consolidation (merge if <95% different)
- Rollback mechanism (revert to v1 if v2 performs worse)

### Risk 3: Data Staleness
**Problem**: Old profile versions used if new ones fail
**Mitigation**:
- Always track which profile version was used
- Compare ratings across versions
- Automatic rollback if new version underperforms

---

## Comparison: Learning Approaches

### Option A: Simple Feedback (RECOMMENDED)
- Effort: Low (JSON + basic aggregation)
- Accuracy: High (based on real results)
- Maintenance: Minimal (no ML pipeline)
- Transparency: Complete (easy to understand)
- **Best for**: Continuous improvement without ML complexity

### Option B: Machine Learning Model
- Effort: High (TensorFlow, PyTorch setup)
- Accuracy: Very high (if trained well)
- Maintenance: High (versioning, retraining)
- Transparency: Low (black box)
- **Best for**: Complex pattern recognition

### Option C: Manual Tuning
- Effort: Medium (expert review)
- Accuracy: High (expert judgment)
- Maintenance: Low (episodic)
- Transparency: Complete
- **Best for**: Occasional improvements, expert input

---

## Recommended Approach: Hybrid

**Use Simple Feedback + Expert Review**:
1. Collect user feedback automatically ✅
2. Aggregate and analyze monthly 📊
3. Expert reviews patterns and recommends changes 👤
4. Make conscious adjustments to profiles 🎯
5. Roll out new versions with A/B testing 🧪

This combines:
- ✅ Continuous learning from users
- ✅ Expert judgment to avoid mistakes
- ✅ Transparency and control
- ✅ Minimal technical complexity
- ✅ Easy to understand and maintain

---

## Next Steps

1. **Phase 6.3**: Add feedback UI widget
2. **Phase 6.4**: Implement feedback storage
3. **Phase 6.5**: Create aggregation & analysis tools
4. **Phase 7**: Deploy profile learning system
5. **Post-Launch**: Monthly review & profile adjustments

---

## Success Metrics

Phase 6+ learning system succeeds when:
- ✅ Users provide feedback on >50% of processed tracks
- ✅ Average rating stays ≥4.0/5.0
- ✅ Confidence vs. satisfaction correlation > 0.70
- ✅ Profile adjustments based on feedback show measurable improvement
- ✅ System requires <1 hour/month maintenance

---

**Created**: November 17, 2025
**Status**: Ready for Phase 6.3 planning
**Approach**: Simple statistical learning + expert review
**Timeline**: Feedback UI in Phase 6.3, learning in Phase 7

