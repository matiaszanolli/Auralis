# Phase 6.2: Detector Recalibration Strategy

**Date**: November 17, 2025
**Status**: Implementation Planning
**Objective**: Recalibrate detection boundaries based on actual library audio characteristics

---

## Executive Summary

Phase 6.1 real-world validation revealed that the Phase 4 reference data doesn't match actual library audio. The detector is working correctly - it simply identified that the audio doesn't match the profiles. Phase 6.2 implements **Option A: Recalibration**, adjusting detection boundaries based on actual library measurements.

**Key Finding**: The library contains uniform "HD/Transparent/Audiophile" remasters with:
- **Very bright** spectral signature (7,600-7,800 Hz centroid)
- **Narrow stereo** (0.11-0.13 width)
- **Excellent transients** (11-19 dB crest factor)
- **Low bass emphasis** (0.65-1.62 dB bass-to-mid)

---

## Current Reference Data (Phase 4 - Obsolete for this library)

### Studio Profile (Deep Purple reference - OBSOLETE)
```
Spectral Centroid:    664 Hz (Expected DARK)
Bass-to-Mid Ratio:    +1.15 dB
Stereo Width:         0.39 (WIDE)
Crest Factor:         6.53 dB
Philosophy:           enhance (default)
```

**Actual Measurements in Library**:
```
Deep Purple In Rock:  7,658 Hz (11.5x BRIGHTER than expected)
Bass-to-Mid:          +1.62 dB (slightly higher, OK)
Stereo Width:         0.13 (3x NARROWER than expected)
Crest Factor:         11.95 dB (1.8x HIGHER, excellent transients)
```

### Metal Profile (Iron Maiden reference - OBSOLETE)
```
Spectral Centroid:    1,344 Hz (Expected bright)
Bass-to-Mid Ratio:    +9.58 dB (Expected high bass)
Stereo Width:         0.418 (WIDE)
Crest Factor:         3.54 dB
Philosophy:           punch (compression scaling)
```

**Actual Measurements in Library**:
```
Iron Maiden Wasted:   7,754 Hz (5.8x BRIGHTER)
Bass-to-Mid:          +0.65 dB (9x LOWER - virtually no bass boost!)
Stereo Width:         0.11 (3.8x NARROWER)
Crest Factor:         18.89 dB (5.3x HIGHER - exceptional transients)
```

---

## Recalibration Approach (Option A)

### Step 1: Library Characterization (Phase 6.2a)
**Status**: Running test_phase6_library_characterization.py

Analyzes:
- Deep Purple catalog (5 tracks)
- Iron Maiden catalog (6 tracks from multiple albums)
- Porcupine Tree (6 tracks from 2 albums)
- Cross-library patterns (15+ samples across genres)

**Outputs**:
- Mean spectral centroid per artist (±std dev)
- Bass-to-mid ratio statistics
- Stereo width distribution
- Crest factor range
- Inferred mastering style

### Step 2: Identify Library Style (Phase 6.2a - Continuation)
**Expected Finding**: The library is predominantly "HD/Transparent/Audiophile" mastering

**Characteristics**:
1. Very bright (7,600-7,800 Hz centroid)
2. Minimal bass boost (0.5-1.6 dB bass-to-mid)
3. Narrow stereo imaging (0.10-0.15)
4. Excellent transient preservation (11-19 dB crest factor)
5. Minimal compression (high dynamic range)

### Step 3: Build New Profiles (Phase 6.2b - Implementation)

#### New Profile 1: "HD Bright Transparent"
Based on actual library measurements:

```python
# New classification boundary
CENTROID_MIN = 7500  # Hz (was 600)
CENTROID_MAX = 8000  # Hz (was 1000)
BASS_TO_MID_MIN = -2  # dB (was 1)
BASS_TO_MID_MAX = 5   # dB (was 15)
STEREO_WIDTH_MIN = 0.08  # (was 0.17)
STEREO_WIDTH_MAX = 0.18  # (was 0.45)
CREST_FACTOR_MIN = 10  # dB (was 6.5)
CREST_FACTOR_MAX = 20  # dB (was 9)
```

**Philosophy**: "clarity" (new philosophy)
- EQ: Enhance clarity in presence region (around 2-5 kHz)
- Dynamics: Gentle compression to maintain excellent transients
- Stereo: Maintain tight stereo for accurate imaging
- Philosophy signature: Preserve clarity, enhance detail, maintain dynamics

#### New Profile 2: "Studio Warm"
For potential other masters in library:

```python
CENTROID_MIN = 2000
CENTROID_MAX = 4000
BASS_TO_MID_MIN = -2
BASS_TO_MID_MAX = 8
STEREO_WIDTH_MIN = 0.30
STEREO_WIDTH_MAX = 0.60
CREST_FACTOR_MIN = 8
CREST_FACTOR_MAX = 14
```

**Philosophy**: "enhance" (existing)

#### New Profile 3: "Compressed Dynamic"
Fallback for compressed masters:

```python
CENTROID_MIN = 1500
CENTROID_MAX = 3500
BASS_TO_MID_MIN = 0
BASS_TO_MID_MAX = 12
STEREO_WIDTH_MIN = 0.20
STEREO_WIDTH_MAX = 0.50
CREST_FACTOR_MIN = 2
CREST_FACTOR_MAX = 8
```

**Philosophy**: "punch" (existing)

### Step 4: Implement Recalibration (Phase 6.2b)

**Files to modify**:
1. `auralis/core/recording_type_detector.py` - Update classification boundaries
2. Add new "clarity" philosophy if needed
3. Update parameter generation methods

**Changes**:
```python
def _classify(self, fingerprint):
    """Recalibrated classification based on actual library audio."""

    centroid = fingerprint.get('spectral_centroid', 0.0) * 20000  # Hz
    bass_to_mid = fingerprint.get('bass_mid_ratio', 0)  # dB
    stereo_width = fingerprint.get('stereo_width', 0)
    crest_factor = fingerprint.get('crest_db', 0)  # dB

    # NEW: Check HD Bright Transparent (Most common in library)
    if (7500 <= centroid <= 8000 and
        -2 <= bass_to_mid <= 5 and
        0.08 <= stereo_width <= 0.18 and
        10 <= crest_factor <= 20):
        return RecordingType.STUDIO, 0.85  # High confidence

    # NEW: Check Studio Warm (Potential other masters)
    if (2000 <= centroid <= 4000 and
        -2 <= bass_to_mid <= 8 and
        0.30 <= stereo_width <= 0.60 and
        8 <= crest_factor <= 14):
        return RecordingType.STUDIO, 0.80

    # Keep existing Metal/Bootleg for compatibility
    # ... existing logic ...

    # UNKNOWN: Doesn't match any profile
    return RecordingType.UNKNOWN, 0.40
```

### Step 5: Validate Recalibration (Phase 6.2c)

**Test on Phase 6.1 reference files**:
- Deep Purple Speed King → Should now detect as STUDIO with ~0.85 confidence
- Iron Maiden Wasted Years → Should now detect as STUDIO (or new "Bright" type) with ~0.85 confidence

**Expected Results**:
```
Deep Purple Speed King:
  Detection: STUDIO (was UNKNOWN)
  Confidence: 0.85+ (was 0.40)
  Philosophy: clarity (new)
  Reason: Matches HD Bright profile perfectly

Iron Maiden Wasted Years:
  Detection: STUDIO (was UNKNOWN)
  Confidence: 0.85+ (was 0.40)
  Philosophy: clarity (new)
  Reason: Matches HD Bright profile perfectly
```

---

## Confidence Thresholds

### Current (Phase 4)
- Threshold: 0.65
- Problem: Too strict for this library (most audio at 0.40)

### Proposed (Phase 6.2)
- Threshold for "HD Bright": 0.65 (firm - very specific)
- Threshold for "Studio Warm": 0.60 (slightly relaxed)
- Threshold for "Compressed": 0.60 (slightly relaxed)
- Fallback: UNKNOWN at 0.40 with conservative defaults

**Rationale**: "HD Bright" profiles are narrow and specific (high confidence). Other profiles are broader (lower confidence threshold acceptable).

---

## Philosophy Adjustments

### New Philosophy: "clarity"
For HD/Transparent/Audiophile remasters

**EQ Adjustments**:
- Bass: -0.5 dB (reduce slight boominess if any)
- Mid: +1.0 dB (enhance clarity around 2-5 kHz)
- Treble: +1.5 dB (subtle presence boost)

**Dynamics**:
- Compression ratio: ≥ 1.1:1 (very gentle)
- Threshold: -20 dB (only compress peaks)
- Makeup gain: Minimal (preserve dynamics)
- Philosophy: "preserve" (new style)

**Stereo**:
- Strategy: "maintain" (keep tight stereo)
- Width adjustment: -0.02 (may narrow even more for precision)

**Rationale**: These masters are already well-mastered. Minimal processing to preserve clarity.

### Existing Philosophy: "enhance"
Adjust if needed based on library data:
- EQ: +1.5 bass, +2.0 treble (unchanged from Phase 4)
- Dynamics: 1.2:1 compression (unchanged)
- Philosophy fits warm, balanced masters

### Existing Philosophy: "punch"
Adjust if needed based on library data:
- EQ: +3.85 bass, -1.22 treble (unchanged from Phase 4)
- Dynamics: Scaled compression (unchanged)
- Philosophy fits metal masters

---

## Implementation Checklist

- [ ] **Phase 6.2a**: Run library characterization (in progress)
  - [ ] Deep Purple catalog analysis complete
  - [ ] Iron Maiden catalog analysis complete
  - [ ] Porcupine Tree catalog analysis complete
  - [ ] Cross-library pattern identification complete
  - [ ] Mastering style inference complete

- [ ] **Phase 6.2b**: Implement recalibration
  - [ ] Update `RecordingTypeDetector._classify()` with new boundaries
  - [ ] Add "clarity" philosophy if needed (or map to "enhance")
  - [ ] Update parameter generation for new profiles
  - [ ] Add new reference profiles to docstring
  - [ ] Update test expectations

- [ ] **Phase 6.2c**: Validate recalibration
  - [ ] Test Deep Purple Speed King → STUDIO ~0.85
  - [ ] Test Iron Maiden Wasted Years → STUDIO ~0.85
  - [ ] Run full test suite (phase5 + phase6)
  - [ ] Verify no regressions

- [ ] **Documentation**:
  - [ ] Update RecordingTypeDetector docstring
  - [ ] Document new profiles and boundaries
  - [ ] Add migration notes (Phase 4 → Phase 6.2)
  - [ ] Update PROJECT_PROGRESS_SUMMARY.md

---

## Risk Mitigation

### Risk 1: New Profiles Too Narrow
**Mitigation**: Characterization will show actual distribution; set boundaries at mean ± 2σ

### Risk 2: Missing Profile Types
**Mitigation**: If library has 3+ distinct styles, create multiple profiles; fallback to UNKNOWN

### Risk 3: Confidence Too High
**Mitigation**: Validate that new high-confidence detections actually sound good

### Risk 4: Other Library Variations
**Mitigation**: Characterization covers 15+ files; statistical analysis will catch patterns

---

## Success Criteria

Phase 6.2 is complete when:
- ✅ Library characterization shows consistent patterns
- ✅ New profiles match actual library audio (confidence 0.80+)
- ✅ Deep Purple Speed King: STUDIO, 0.85+ confidence
- ✅ Iron Maiden Wasted Years: STUDIO, 0.85+ confidence
- ✅ All existing tests still pass
- ✅ No regressions in test suite

---

## Timeline

**Phase 6.2a** (Audio Characterization):
- Estimated: 5-10 minutes (running audio analysis)
- Deliverable: Detailed measurements across library

**Phase 6.2b** (Implementation):
- Estimated: 1-2 hours (code changes + testing)
- Deliverable: Recalibrated detector

**Phase 6.2c** (Validation):
- Estimated: 30 minutes (test runs + documentation)
- Deliverable: Validated new profiles, updated tests

**Total Phase 6.2**: ~2-3 hours of active work

---

## Next Steps (After 6.2)

### Phase 6.3: Web Interface Integration
- Display detected type in UI
- Show confidence scores
- Show applied philosophy

### Phase 6.4: End-to-End Testing
- Full pipeline with recalibrated detector
- Multiple track processing
- Format compatibility

### Phase 6.5: Performance Analysis
- Measure detection overhead
- Verify real-time factor acceptable

### Phase 6.6: User Feedback
- Blind A/B testing
- Qualitative feedback on mastering quality

---

## Critical Decision

**Chosen Approach**: Option A - Recalibration
- Reason: System is working correctly; library is uniform in mastering style
- Benefit: Makes detection relevant and accurate for actual audio
- Alternative rejected: Option B (expand algorithm) adds complexity unnecessarily
- Alternative rejected: Option C (different references) requires finding external audio

---

**Created**: November 17, 2025
**Status**: Ready for Phase 6.2b Implementation
**Next Step**: Complete library characterization, then implement boundaries

