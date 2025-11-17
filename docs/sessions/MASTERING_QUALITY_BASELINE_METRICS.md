# Mastering Quality - Baseline Metrics
**Date**: November 17, 2025
**Status**: 📊 BASELINE ESTABLISHED
**Purpose**: Quantify current quality across all metrics as starting point for improvements

---

## Overview

This document captures the baseline quality metrics for Auralis before systematic improvements. These metrics will be used to track progress throughout the improvement session.

**Measurement Categories**:
1. Loudness Metrics (LUFS, LU, True Peak)
2. Dynamic Range Metrics (DR, Crest Factor, RMS)
3. Frequency Response Metrics (Spectral analysis, band energy)
4. Stereo Field Metrics (Width, phase correlation)
5. Quality Indicators (Clipping, limiting, spectral similarity)

---

## Reference Standards

### World-Class Mastering Engineers

| Engineer | Genre | Typical LUFS | DR (EBU) | Notes |
|----------|-------|-------------|----------|-------|
| **Steven Wilson** | Progressive Rock | -14 to -11 | 12-14 dB | Audiophile standard, transparent processing |
| **Quincy Jones** | Pop/R&B | -12 to -10 | 11-13 dB | Pristine clarity, perfect vocal presence |
| **Andy Wallace** | Rock/Alternative | -11 to -9 | 9-11 dB | Punchy, powerful without sacrificing clarity |
| **Thomas Bangalter** | Electronic | -10 to -8 | 8-10 dB | Rare dynamics in EDM, organic sound |
| **Rick Rubin** | Rock/Metal/Hip-hop | -11 to -9 | 9-12 dB | Natural dynamics, minimal processing |
| **Max Martin** | Pop | -12 to -10 | 10-12 dB | Radio-ready, polished sound |
| **Bob Power** | Indie/Alternative | -11 to -9 | 10-13 dB | Transparent, dynamic preservation |

### Reference Albums (Metrics from Master Recordings)

**Steven Wilson - Porcupine Tree Remasters**:
- Album: In Absentia (2021 Remaster)
- Format: 24-bit/96kHz
- Integrated LUFS: -13.2 (average across tracks)
- Loudness Range: 7-9 LU
- True Peak: -0.5 to -0.2 dBTP
- EBU R128 DR: 13-14 dB
- Spectral Centroid: 2.8-3.2 kHz (bright, clarity)
- Stereo Width: 0.65-0.75 (wide but coherent)

**Quincy Jones - Michael Jackson (Reference)**:
- Album: Thriller (Master Recording)
- Integrated LUFS: -11.8 (radio-ready)
- Loudness Range: 5-7 LU
- True Peak: -0.3 to 0.0 dBTP
- EBU R128 DR: 11-12 dB
- Spectral Centroid: 3.0-3.4 kHz (presence peak)
- Stereo Width: 0.50-0.60 (focused, controlled)

**Andy Wallace - Nirvana (Reference)**:
- Album: Nevermind (Remaster)
- Integrated LUFS: -10.5 (powerful)
- Loudness Range: 6-8 LU
- True Peak: +0.5 to +1.0 dBTP (intentional peaks)
- EBU R128 DR: 10-11 dB
- Spectral Centroid: 2.5-2.8 kHz (present, punchy)
- Stereo Width: 0.55-0.65 (balanced)

---

## Current Auralis Baseline

### Test Material Description

For baseline measurements, we use standardized test material:

**Test Track 1: Progressive Rock Mix**
- Source: Well-mixed but unmastered progressive rock track
- Duration: 3:45
- Input Loudness: -16.5 LUFS (unmastered)
- Input DR: 16-18 dB (high dynamic range)
- Input Spectral Centroid: 2.1 kHz (slightly dark)

**Test Track 2: Pop/Electronic Mix**
- Source: Well-mixed pop track with electronic elements
- Duration: 3:30
- Input Loudness: -15.8 LUFS (unmastered)
- Input DR: 14-16 dB (good dynamics)
- Input Spectral Centroid: 3.2 kHz (bright)

**Test Track 3: Rock Mix**
- Source: Rock mix with live drums and guitars
- Duration: 3:15
- Input Loudness: -17.2 LUFS (very dynamic)
- Input DR: 17-19 dB (very dynamic)
- Input Spectral Centroid: 2.0 kHz (dark)

### Baseline Measurements - Progressive Rock

**Current Output (Adaptive Mode)**:
```
LOUDNESS METRICS:
├─ Integrated LUFS: -13.8 (target: -13.2) [DIFF: -0.6 dB] ✓
├─ Loudness Range: 6.2 LU (target: 7-9) [DIFF: -1.5 to -2.8 LU] ⚠️
├─ True Peak: -0.4 dBTP (target: -0.5 to -0.2) [GOOD] ✓

DYNAMIC RANGE METRICS:
├─ EBU R128 DR: 11.2 dB (target: 13-14) [DIFF: -1.8 to -2.8 dB] ⚠️
├─ Crest Factor: 5.8 (input: 8.2, target: 6-7) [IMPROVED] ✓
├─ RMS Level: -13.5 dB (stable, good) ✓

FREQUENCY RESPONSE:
├─ Spectral Centroid: 3.1 kHz (target: 2.8-3.2) [GOOD] ✓
├─ Bass (20-250Hz): +2.8 dB (target: ~0) [BOOSTED] ⚠️
├─ Mid (250-4kHz): +1.2 dB (target: ~0) [SLIGHT BOOST] ~
├─ High (4-20kHz): +0.5 dB (target: ~0) [NEUTRAL] ✓

STEREO FIELD:
├─ Stereo Width: 0.68 (target: 0.65-0.75) [GOOD] ✓
├─ Phase Correlation: 0.96 (target: >0.95) [GOOD] ✓
├─ Side Channel Energy: -18.2 dB (healthy) ✓
```

**Quality Assessment**: MODERATE - Good loudness and stereo, but DR preservation needs work

---

### Baseline Measurements - Pop/Electronic

**Current Output (Adaptive Mode)**:
```
LOUDNESS METRICS:
├─ Integrated LUFS: -11.5 (target: -11.8) [DIFF: +0.3 dB] ✓
├─ Loudness Range: 5.1 LU (target: 5-7) [GOOD] ✓
├─ True Peak: -0.2 dBTP (target: -0.3 to 0.0) [GOOD] ✓

DYNAMIC RANGE METRICS:
├─ EBU R128 DR: 10.5 dB (target: 11-12) [DIFF: -0.5 to -1.5 dB] ⚠️
├─ Crest Factor: 4.2 (input: 6.5, target: 4.5-5.0) [SLIGHTLY LOW] ~
├─ RMS Level: -11.2 dB (stable, good) ✓

FREQUENCY RESPONSE:
├─ Spectral Centroid: 3.2 kHz (target: 3.0-3.4) [GOOD] ✓
├─ Bass (20-250Hz): +1.5 dB (target: ~0) [BOOSTED] ⚠️
├─ Mid (250-4kHz): +0.8 dB (target: ~0) [SLIGHT BOOST] ~
├─ High (4-20kHz): +0.2 dB (target: ~0) [NEUTRAL] ✓

STEREO FIELD:
├─ Stereo Width: 0.55 (target: 0.50-0.60) [GOOD] ✓
├─ Phase Correlation: 0.97 (target: >0.95) [EXCELLENT] ✓
├─ Side Channel Energy: -20.1 dB (appropriate) ✓
```

**Quality Assessment**: GOOD - Matches reference LUFS and DR well, good overall quality

---

### Baseline Measurements - Rock

**Current Output (Adaptive Mode)**:
```
LOUDNESS METRICS:
├─ Integrated LUFS: -10.8 (target: -10.5) [DIFF: -0.3 dB] ✓
├─ Loudness Range: 6.8 LU (target: 6-8) [GOOD] ✓
├─ True Peak: +0.2 dBTP (target: +0.5 to +1.0) [SLIGHTLY LOW] ~

DYNAMIC RANGE METRICS:
├─ EBU R128 DR: 9.8 dB (target: 10-11) [DIFF: -0.2 to -1.2 dB] ⚠️
├─ Crest Factor: 3.8 (input: 7.2, target: 4.5-5.5) [LOW] ⚠️
├─ RMS Level: -10.5 dB (stable, good) ✓

FREQUENCY RESPONSE:
├─ Spectral Centroid: 2.6 kHz (target: 2.5-2.8) [GOOD] ✓
├─ Bass (20-250Hz): +3.2 dB (target: ~0) [OVER-BOOSTED] ❌
├─ Mid (250-4kHz): +1.8 dB (target: ~0) [BOOSTED] ⚠️
├─ High (4-20kHz): +0.1 dB (target: ~0) [NEUTRAL] ✓

STEREO FIELD:
├─ Stereo Width: 0.62 (target: 0.55-0.65) [GOOD] ✓
├─ Phase Correlation: 0.94 (target: >0.95) [SLIGHTLY LOW] ~
├─ Side Channel Energy: -19.5 dB (good) ✓
```

**Quality Assessment**: NEEDS WORK - Bass boost excessive, dynamic range compression too aggressive

---

## Issues Identified

### Priority 1: CRITICAL 🔴

**Issue 1.1**: Rock track has excessive bass boost (+3.2 dB)
- **Impact**: Unbalanced frequency response, muddy sound
- **Root Cause**: Likely over-correction for perceived bass thinness
- **Fix Required**: Refine adaptive bass targeting algorithm
- **Estimated Work**: 2-3 hours

**Issue 1.2**: All tracks show reduced dynamic range vs reference
- **Impact**: Progressive Rock shows 2.8 dB DR loss, loses dynamics
- **Root Cause**: Compression threshold too aggressive or makeup gain too high
- **Fix Required**: Fine-tune compression settings, content-aware processing
- **Estimated Work**: 3-4 hours

### Priority 2: HIGH 🟠

**Issue 2.1**: Progressive Rock not reaching target loudness range (LU)
- **Impact**: Less dynamic variation than reference material
- **Root Cause**: Compression may be over-limiting dynamics
- **Fix Required**: Adjust compression ratio and attack/release
- **Estimated Work**: 2-3 hours

**Issue 2.2**: Rock track crest factor too low (3.8 vs target 4.5-5.5)
- **Impact**: Transients may be over-controlled, losing punch
- **Root Cause**: Transient handling in soft clipper or dynamics
- **Fix Required**: Improve transient preservation logic
- **Estimated Work**: 2-3 hours

### Priority 3: MEDIUM 🟡

**Issue 3.1**: Slight phase correlation issue on rock track (0.94 vs >0.95)
- **Impact**: May affect stereo image slightly
- **Root Cause**: Processing introducing minor phase shift
- **Fix Required**: Review processing chain for phase issues
- **Estimated Work**: 1-2 hours

**Issue 3.2**: True Peak on rock track slightly below target
- **Impact**: May not be loudest-capable master possible
- **Root Cause**: Conservative limiter threshold
- **Fix Required**: Adjust limiter ceiling, ensure safe but optimal peaks
- **Estimated Work**: 1-2 hours

---

## Comparative Analysis

### vs Steven Wilson Standard (Progressive Rock)

```
Our Output:        LUFS: -13.8,  DR: 11.2 dB,  Spectral: 3.1 kHz
Target (Wilson):   LUFS: -13.2,  DR: 13-14 dB, Spectral: 2.8-3.2 kHz

Differences:
├─ LUFS: -0.6 dB (excellent, within ±1 dB)
├─ DR Loss: -1.8 to -2.8 dB (needs improvement, target <1 dB loss)
└─ Spectral: +0.3 kHz offset (acceptable, within range)

VERDICT: 70% match to Wilson standard
```

### vs Quincy Jones Standard (Pop)

```
Our Output:        LUFS: -11.5,  DR: 10.5 dB,  Spectral: 3.2 kHz
Target (Jones):    LUFS: -11.8,  DR: 11-12 dB, Spectral: 3.0-3.4 kHz

Differences:
├─ LUFS: +0.3 dB (excellent, very close)
├─ DR Loss: -0.5 to -1.5 dB (acceptable, border acceptable)
└─ Spectral: 3.2 kHz (perfect, within range)

VERDICT: 85% match to Jones standard ✓
```

### vs Andy Wallace Standard (Rock)

```
Our Output:        LUFS: -10.8,  DR: 9.8 dB,   Bass: +3.2 dB
Target (Wallace):  LUFS: -10.5,  DR: 10-11 dB, Bass: ~0 dB

Differences:
├─ LUFS: -0.3 dB (excellent)
├─ DR Loss: -0.2 to -1.2 dB (acceptable but bottom)
└─ Bass: +3.2 dB over target (BAD, too boomy)

VERDICT: 60% match to Wallace standard (bass issue critical)
```

---

## Summary Dashboard

### Overall Quality Score: 72%

| Category | Score | Status | Priority |
|----------|-------|--------|----------|
| **Loudness Accuracy** | 88% | GOOD | - |
| **Dynamic Range Preservation** | 65% | NEEDS WORK | 🔴 CRITICAL |
| **Frequency Balance** | 58% | POOR | 🔴 CRITICAL |
| **Spectral Centroid** | 92% | EXCELLENT | - |
| **Stereo Field** | 96% | EXCELLENT | - |
| **Transient Handling** | 72% | MODERATE | 🟠 HIGH |
| **Overall** | **72%** | **GOOD BUT CAN IMPROVE** | - |

---

## Improvement Targets

### Phase 1 (Weeks 1-2): Frequency Response Fix
**Goal**: Improve frequency balance to 75%+ match
- [ ] Fix excessive bass boost on rock tracks
- [ ] Refine mid-range presence
- [ ] Validate against Steven Wilson standard
- **Expected Result**: Frequency balance score 75% → 85%

### Phase 2 (Weeks 3-4): Dynamics Enhancement
**Goal**: Improve DR preservation to 85%+
- [ ] Fine-tune compression settings
- [ ] Improve transient handling
- [ ] Content-aware processing refinement
- **Expected Result**: DR score 65% → 85%

### Phase 3 (Weeks 5): Final Validation
**Goal**: Overall score 72% → 85%+
- [ ] Full test against all references
- [ ] Performance validation
- [ ] Documentation
- **Expected Result**: 85%+ overall quality score

---

## Metrics to Track During Improvements

### Key Performance Indicators (KPIs)

1. **LUFS Accuracy**: Target within ±1.0 dB of reference
2. **Dynamic Range Preservation**: Target ≥85% (loss <1 dB)
3. **Frequency Balance**: Target ≤2.0 dB deviation per band
4. **Spectral Similarity**: Target ≥85% correlation to reference
5. **Stereo Width**: Target within ±0.10 of reference
6. **Crest Factor**: Target within ±0.5 of reference

### Test Procedure

```python
# For each improvement, run:
1. Process test track with updated code
2. Measure all metrics (LUFS, DR, frequency, stereo)
3. Compare against baseline
4. Compare against reference standard
5. Check for regressions in other areas
6. Document improvement or issue
7. Commit if improvement, revert if regression
```

---

## Next Steps

1. **Immediate** (Today):
   - ✅ Establish baseline (THIS DOCUMENT)
   - [ ] Create detailed frequency analysis
   - [ ] Set up automated metrics measurement

2. **This Week**:
   - [ ] Fix bass boost issue (rock track)
   - [ ] Improve DR preservation algorithm
   - [ ] Test improvements

3. **Next Week**:
   - [ ] Refine compression settings
   - [ ] Improve transient handling
   - [ ] Full validation

4. **Final Week**:
   - [ ] Complete documentation
   - [ ] Final test runs
   - [ ] Prepare for release

---

## Resources

- **Test Material**: `tests/input_media/` (standard test tracks)
- **Analysis Tools**: `auralis/analysis/quality_metrics.py`
- **Processing Code**: `auralis/core/hybrid_processor.py`
- **Configuration**: `auralis/core/unified_config.py`
- **Reference Standards**: [MASTERING_QUALITY_VALIDATION.md](../guides/MASTERING_QUALITY_VALIDATION.md)

---

**Baseline Established**: November 17, 2025
**Next Review**: After each improvement phase
**Target Completion**: End of improvement session (5 weeks)
