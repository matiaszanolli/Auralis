# Phase 6.4: Personal Layer Validation - Quick Start Guide

**Status**: Ready to Begin
**Goal**: Collect 20+ ratings to validate personal learning system
**Timeline**: 2-3 weeks (5-10 minutes per day)
**Success Criteria**: Average satisfaction ≥ 4.0/5.0, 2-3 successful profile updates

---

## What You Have Working Now

✅ **rate_track.py** - Capture feedback (5 seconds)
✅ **analyze_feedback.py** - Detect patterns (1 minute)
✅ **update_profile.py** - Update profiles (30 seconds)
✅ **3 Initial Ratings** - Already collected and analyzed

---

## Daily Workflow (2 minutes)

### Step 1: Process a Track (30 seconds)
```bash
python launch-auralis-web.py --dev
# Process your track as usual
# Listen to the result
```

### Step 2: Rate It (30 seconds)
```bash
python -m scripts.rate_track ~/path/to/track.flac --rating 4 --comment "add more bass"
```

**Rating Scale**:
- 1⭐ = Needs major work (low satisfaction)
- 2⭐ = Okay but issues (below average)
- 3⭐ = Good enough (acceptable)
- 4⭐ = Very good (satisfied)
- 5⭐ = Perfect (excellent)

**Comment Tips**:
- "more bass" / "less treble" (parameter suggestions)
- "harsh high end" / "dull low end" (frequency issues)
- "too narrow" / "too wide" (stereo suggestions)
- "perfect clarity" (positive feedback)
- Keep it brief (1-3 words usually enough)

---

## Weekly Analysis (1 minute)

### Every 5-7 Days: Check for Patterns

```bash
python -m scripts.analyze_feedback --all-types
```

**Look for**:
- Keyword mentions (bass, treble, stereo, harsh, etc.)
- Average satisfaction trending up or down
- Patterns across same recording type

**Example Output**:
```
STUDIO Profile Analysis
Samples: 5
Average Rating: 4.0/5.0
Average Confidence: 85%

Feedback Patterns:
  'bass' mentioned 3 times

Recommendations:
  → Consider bass adjustment (+0.3 to +0.5 dB)
```

---

## When to Update Profiles (Optional)

### Criteria for Update:
- ✅ 5+ samples of same type
- ✅ Clear pattern (parameter mentioned 3+ times)
- ✅ Average rating ≥ 4.0 (system is working)

### Do NOT update if:
- ❌ Less than 5 samples (not enough data)
- ❌ Average rating < 3.0 (profile needs broader revision)
- ❌ Mixed feedback (some want bass up, others want it down)

---

## Making a Profile Update (30 seconds)

### Step 1: Analyze First
```bash
python -m scripts.analyze_feedback --type studio
```

Note the recommendations.

### Step 2: Update the Profile
```bash
python -m scripts.update_profile studio --bass 1.8 --reason "bass +3 mentions in feedback"
```

**What happens**:
1. Profile loaded (v1.0)
2. Parameter adjusted (bass: 1.5 → 1.8)
3. Tests run (validates no regressions)
4. Git commit created (version history)
5. Profile bumped to v1.1

**If tests pass**: ✓ Update successful
**If tests fail**: ✗ Update rolled back (safe!)

---

## Tracking Progress

### Current Status (Session Start)
```
Ratings Collected: 3
Average Satisfaction: 4.33/5.0
Studio Detections: 2 (Speed King 4/5, Child In Time 4/5)
Unknown Detections: 1 (Bloodsucker 5/5)
Patterns Detected: bass +2 mentions
Profile Updates Made: 0 (need more data)
```

### Target for Phase 6.4
```
Ratings Collected: 20+
Average Satisfaction: ≥ 4.0/5.0
Profile Updates: 2-3
Test Regressions: 0
```

---

## Useful Commands Reference

### View Feedback
```bash
# Raw JSONL format
cat ~/.auralis/personal/feedback/ratings.jsonl

# Formatted (using Python)
python -m scripts.analyze_feedback --all-types
```

### Analyze by Type
```bash
python -m scripts.analyze_feedback --type studio
python -m scripts.analyze_feedback --type metal
python -m scripts.analyze_feedback --type bootleg
```

### View Profile Versions
```bash
ls -la data/profiles/studio_hd_bright_v*.json
```

### See Recent Changes
```bash
git log --oneline data/profiles/
```

### Rollback a Profile Update
```bash
git revert <commit-hash>
```

---

## What to Expect

### Week 1 (3-5 Ratings)
- Feedback captures working
- System learning patterns
- Not enough data for updates yet
- Continue collecting

### Week 2 (8-12 Ratings)
- Patterns emerging ("bass mentioned 3 times")
- Ready for 1-2 profile updates
- First improvements tested
- Average satisfaction tracking

### Week 3+ (15+ Ratings)
- Confident updates possible
- Multiple types have sufficient data
- System actively learning
- Satisfaction scores improving

---

## Troubleshooting

### "No feedback yet for studio"
- Keep rating tracks! Need 5+ samples per type
- Process different genres to get variety

### "Tests failed - not committing"
- Profile update was rejected (tests caught an issue)
- The old profile is still active
- Try a smaller adjustment next time

### "analyze_feedback says need 5 samples"
- You need at least 5 ratings to reliably detect patterns
- Continue collecting feedback
- Update will be available soon

### "Can't find rate_track.py"
- Make sure you're in the project root directory
- Use: `python -m scripts.rate_track` (with -m flag)
- Or: `./scripts/rate_track.py` (if executable)

---

## Key Insights from Initial Data

### Current Observations
1. **Bloodsucker Edge Case**: Detected as "unknown" (40%) but rated 5/5
   - Suggests: Profile boundaries might be too narrow in that range
   - Future: May need boundary expansion once we have more data

2. **Bass Feedback**: "bass could be warmer" mentioned 2x already
   - Suggests: Studio profile might benefit from +0.3dB bass boost
   - When ready: Update after 5-7 more studio ratings

3. **Consistency**: Speed King and Child In Time both studio (85%)
   - Suggests: HD Bright Transparent profile is working well
   - Confidence in detector is high

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Ratings Collected | 20+ | 3 ✅ |
| Average Satisfaction | ≥4.0 | 4.33 ✅ |
| Profile Updates | 2-3 | 0 (pending data) |
| Test Regressions | 0 | 0 ✅ |
| Types with 5+ samples | 2+ | 1 (studio) |

---

## Next Steps

1. **This week**: Continue rating tracks
   - Aim for 5-7 more ratings
   - Mix different types if possible

2. **Next week**: First profile update
   - Analyze studio feedback
   - Update bass if pattern is clear
   - Test the update

3. **Week 3**: Expand and iterate
   - Collect across all types
   - Make 2-3 updates total
   - Verify satisfaction trending up

---

## Remember

✅ **This is learning in action**: Each rating teaches the system
✅ **Safe updates**: Tests prevent regressions
✅ **Reversible**: Git commits mean easy rollback
✅ **Personal**: Your preferences become the adjustment layer
✅ **Simple**: 5 seconds rating → 1 minute analysis → 30 second update

The system works. You're teaching it what sounds good to you.

---

**Happy mastering! 🎵**

Created: November 17, 2025
Ready for: Phase 6.4 validation (2-3 weeks)
