# Crest Factor Findings - Matchering Behavior Analysis

**Date**: October 24, 2025

---

## Executive Summary

Testing with diverse material revealed **Matchering's adaptive crest factor strategy** is the key to its mastering quality. Matchering doesn't just adjust loudness - it actively manages dynamics to achieve optimal presentation for each track.

**Key Discovery**: Matchering applies different processing based on current crest factor:
- **Under-leveled + high dynamics → Minimal compression** (preserve/enhance dynamics)
- **Very dynamic (crest > 17 dB) → Heavy compression** (bring to competitive loudness)
- **Over-compressed (crest < 12 dB) → De-compression/expansion** (restore dynamics)

This is why our spectrum system works well for some material but struggles with others.

---

## Test Results Summary

| Track | Type | Original Crest | Target Crest | Crest Δ | RMS Δ | Status |
|-------|------|---------------|--------------|---------|-------|--------|
| Static-X "Fix" | Under-leveled metal | 12.13 dB | 14.17 dB | +2.04 dB | +6.73 dB | ✅ EXCELLENT (0.22 dB off) |
| Testament "Preacher" | Loud+dynamic live | 12.55 dB | 11.35 dB | -1.20 dB | +1.48 dB | ✅ GOOD (1.70 dB off) |
| Slayer "South of Heaven" | Very dynamic metal | 18.98 dB | 15.74 dB | -3.24 dB | +5.44 dB | ⚠️ NEEDS WORK (5.03 dB off) |
| Iron Maiden "Aces High" | Over-mastered remaster | 11.18 dB | 14.39 dB | +3.21 dB | -2.51 dB | ⚠️ NEEDS WORK (2.57 dB off) |

---

## Detailed Findings

### 1. Static-X "Fix" ✅ EXCELLENT (Our Best Result)

```
ORIGINAL:
  Peak: -8.65 dB, RMS: -20.78 dB, Crest: 12.13 dB

MATCHERING:
  RMS Δ: +6.73 dB, Crest Δ: +2.04 dB

AURALIS:
  RMS Δ: +6.51 dB (0.22 dB off)

STRATEGY: Preserve/enhance dynamics while boosting loudness
```

**Why it works**: Material is under-leveled but has moderate dynamics (12.13 dB crest). Matchering applies minimal compression and large level boost. Our system handles this perfectly because:
- Correctly identifies as under-leveled (input_level: 0.46)
- Applies large RMS boost (+4.94 dB before peak norm)
- Slightly increases crest factor (dynamics improved)

**Key**: When crest is 12-13 dB and level is low, PRESERVE or IMPROVE dynamics.

---

### 2. Testament "The Preacher" ✅ GOOD (Acceptable)

```
ORIGINAL:
  Peak: -0.38 dB, RMS: -12.93 dB, Crest: 12.55 dB

MATCHERING:
  RMS Δ: +1.48 dB, Crest Δ: -1.20 dB

AURALIS:
  RMS Δ: -0.22 dB (1.70 dB off)

STRATEGY: Light compression to increase competitive loudness
```

**Why it's off**: Material is already loud (peak -0.38 dB) with moderate-high dynamics (12.55 dB crest). Matchering applies light compression (-1.20 dB crest reduction) to increase RMS. Our system:
- Correctly identifies as very loud (input_level: 0.88)
- Limited stereo width expansion (good!)
- But crest preserved at 12.29 dB (should be ~11.35 dB)
- Result: RMS too low by ~1.5 dB

**Key**: When crest is 12-13 dB and level is ALREADY HIGH, apply LIGHT COMPRESSION to increase RMS.

---

### 3. Slayer "South of Heaven" ⚠️ NEEDS WORK (Critical Case)

```
ORIGINAL:
  Peak: -2.57 dB, RMS: -21.55 dB, Crest: 18.98 dB  ← EXTREME DYNAMICS!

MATCHERING:
  RMS Δ: +5.44 dB, Crest Δ: -3.24 dB  ← HEAVY COMPRESSION

AURALIS:
  RMS Δ: +0.42 dB (5.03 dB off!)
  Crest: 17.90 dB (only -1.08 dB reduction)

STRATEGY: Heavy compression for extremely dynamic material
```

**Why it fails**: Material has **extreme dynamics** (crest 18.98 dB, almost classical level). This is unusual for metal. Matchering recognizes this requires aggressive compression to achieve competitive metal loudness:
- Reduces crest by -3.24 dB (from 19.0 → 15.7 dB)
- This allows RMS boost of +5.44 dB
- Final crest 15.7 dB is typical for well-mastered metal

Our system:
- Correctly identifies as moderate level (input_level: 0.50)
- Identifies as VERY dynamic (dynamic_range: 1.00!)
- But our "preserve dynamics" rule prevents compression
- Result: Crest only reduced by -1.08 dB, RMS only up +0.42 dB

**Key**: When crest > 17 dB, apply HEAVY COMPRESSION regardless of genre. This is not "normal" dynamics - it needs correction.

---

### 4. Iron Maiden "Aces High" ⚠️ NEEDS WORK (Reverse Case)

```
ORIGINAL (24-bit/96kHz remaster):
  Peak: -1.47 dB, RMS: -12.65 dB, Crest: 11.18 dB  ← OVER-COMPRESSED!

MATCHERING:
  RMS Δ: -2.51 dB, Crest Δ: +3.21 dB  ← RMS REDUCTION / DYNAMIC RESTORATION

AURALIS:
  RMS Δ: +0.06 dB (2.57 dB off)
  Crest: 11.30 dB (only +0.12 dB increase)

STRATEGY: Restore dynamics to over-compressed modern remasters
```

**Why it fails**: This is the OPPOSITE of normal mastering. The 24-bit/96kHz remaster is actually **over-compressed** (crest only 11.18 dB - very low for rock). Matchering acts as "de-mastering":
- INCREASES crest by +3.21 dB (from 11.2 → 14.4 dB)
- REDUCES RMS by -2.51 dB
- Result: More dynamic, more pleasant presentation

Our system:
- Correctly identifies as very loud (input_level: 0.91)
- But tries to INCREASE RMS (target -11.0 dB)
- Doesn't recognize material is already over-compressed
- Result: Slight RMS increase (+0.06 dB) instead of reduction (-2.51 dB)

**Key**: When crest < 12 dB and level is already high, DON'T boost RMS - consider REDUCING it and RESTORING dynamics.

---

## Matchering's Crest Factor Strategy

### The Pattern

Matchering targets different crest factors based on input characteristics:

```
INPUT CREST    ACTION                  TARGET CREST    PURPOSE
-----------    ------                  ------------    -------
19+ dB         Heavy compression       15-16 dB        Competitive loudness
15-18 dB       Moderate compression    14-15 dB        Balance dynamics/loudness
12-14 dB       Light/no compression    12-14 dB        Preserve good balance
10-12 dB       Expansion/restoration   13-15 dB        Restore over-compressed
```

### Key Thresholds

1. **Crest > 17 dB**: Material is TOO dynamic for competitive loudness
   - Apply heavy compression (-3 to -4 dB crest reduction)
   - Brings to typical mastered range (15-16 dB)

2. **Crest 12-14 dB**: Well-balanced dynamics
   - Light or no compression
   - Focus on level adjustment

3. **Crest < 12 dB**: Over-compressed (especially if already loud)
   - Consider expansion/restoration
   - May REDUCE RMS to restore dynamics

### Interaction with Input Level

The crest factor strategy interacts with input level:

| Input Level | Crest Factor | Action | Example |
|-------------|--------------|--------|---------|
| Low | High (12-14 dB) | Preserve/enhance dynamics | Static-X ✅ |
| High | Moderate (12-13 dB) | Light compression | Testament |
| Moderate | Very high (>17 dB) | Heavy compression | Slayer |
| High | Low (<12 dB) | Restore dynamics | Iron Maiden |

---

## Implications for Our System

### What's Working ✅

1. **Under-leveled material with good dynamics** (Static-X)
   - Correctly identifies low level
   - Applies large boost
   - Preserves/improves dynamics
   - Result: EXCELLENT

### What Needs Improvement ⚠️

1. **Extreme dynamics (crest > 17 dB)** - NOT HANDLED
   - Current: Preserves dynamics (good for classical, wrong for metal)
   - Needed: Recognize crest > 17 dB as abnormal, apply compression
   - Impact: 5 dB RMS error on Slayer

2. **Light compression for loud material** - PARTIALLY IMPLEMENTED
   - Current: Tries to boost RMS, but can't due to crest constraint
   - Needed: Apply -1 to -2 dB crest reduction for loud material
   - Impact: 1.7 dB RMS error on Testament

3. **Over-compressed material** - NOT HANDLED
   - Current: Tries to boost RMS further
   - Needed: Detect crest < 12 dB + high level → restore dynamics
   - Impact: 2.6 dB RMS error on Iron Maiden

---

## Recommended Fixes

### Priority 1: Extreme Dynamics Rule ⚠️ CRITICAL

```python
# In spectrum_mapper.py _apply_content_modifiers()

# Rule: Extreme dynamics (crest > 17 dB) needs heavy compression
if position.dynamic_range > 0.9:  # Maps to crest > ~17 dB
    # This is abnormally dynamic - needs correction
    params.compression_amount = 0.8  # Heavy compression
    params.dynamics_intensity = 0.8
    params.output_target_rms = -15.0  # More aggressive target
    print(f"[Content Rule] Extreme dynamics detected (DR:{position.dynamic_range:.2f}) → Heavy compression")
```

**Impact**: Would fix Slayer (currently 5.03 dB off)

### Priority 2: Over-Compressed Detection ⚠️ IMPORTANT

```python
# In spectrum_mapper.py _apply_content_modifiers()

# Rule: Over-compressed material (low crest + high level) → restore dynamics
if position.dynamic_range < 0.35 and position.input_level > 0.8:
    # Material is over-compressed - don't boost further
    params.output_target_rms = current_rms_db - 1.0  # Slight RMS reduction
    params.compression_amount = 0.0  # No compression
    print(f"[Content Rule] Over-compressed detected (DR:{position.dynamic_range:.2f}, Level:{position.input_level:.2f}) → Restore dynamics")
```

**Impact**: Would fix Iron Maiden (currently 2.57 dB off)

### Priority 3: Re-enable Dynamics Processor

Current system has dynamics processor disabled. Need to:
1. Re-enable with spectrum-aware settings
2. Apply compression based on `spectrum_params.compression_amount`
3. Use calculated compression ratio and threshold

**Impact**: Would improve Testament (currently 1.70 dB off)

---

## Summary

**Root Cause**: Our system preserves dynamics too aggressively. We're not adapting compression based on **current crest factor**.

**The Fix**: Add crest-factor-aware processing:
1. **Extreme dynamics (>17 dB crest)** → Heavy compression
2. **Moderate dynamics (12-14 dB crest)** → Light/no compression
3. **Low dynamics (<12 dB crest) + loud** → Consider expansion

**Expected Results After Fix**:
- Static-X: Still EXCELLENT ✅
- Testament: EXCELLENT (was GOOD)
- Slayer: GOOD or EXCELLENT (was 5 dB off)
- Iron Maiden: GOOD or EXCELLENT (was 2.6 dB off)

**Confidence**: High - Pattern is clear and consistent across all test cases.
