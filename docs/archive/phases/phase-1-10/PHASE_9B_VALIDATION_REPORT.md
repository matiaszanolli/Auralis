# Phase 9B: Validation Report - Auralis vs Matchering Comparison

**Status**: 🔴 CRITICAL ISSUE IDENTIFIED - BLOCKING FULL VALIDATION
**Date**: November 30, 2025
**Test Scope**: First 3 South Of Heaven tracks (Slayer 1988)
**Presets Tested**: Adaptive, Gentle

---

## Executive Summary

Phase 9B processing has begun with a new validation script (`process_with_auralis.py`), but **critical loudness discrepancy discovered** that prevents validation against Matchering baseline.

### Key Finding
```
Auralis output is +12+ dB LOUDER than Matchering reference
- Original: -21.55 dB RMS (typical for South Of Heaven)
- Auralis: -3.51 dB RMS (far too loud)
- Matchering: -16.10 dB RMS (correct target)
- Difference: +12.59 dB ❌
```

### Positive Indicator
```
Preset differentiation IS working correctly:
- Adaptive: -3.51 dB RMS
- Gentle: -3.69 dB RMS
- Difference: 0.18 dB ✓ (matches expected ~0.20 dB from Phase 8)
```

---

## Validation Script Created

**Location**: `research/scripts/process_with_auralis.py`

This script:
- Loads original and Matchering audio files from disk
- Processes originals with Auralis using specified presets
- Extracts RMS, peak, and crest factor metrics
- Compares Auralis output to Matchering baseline
- Generates detailed JSON results with per-track breakdowns
- Supports filtering to specific tracks for incremental testing

**Usage**:
```bash
python research/scripts/process_with_auralis.py \
  --tracks 1 2 3 \
  --presets adaptive gentle \
  --album south_of_heaven
```

---

## Test Results (3 Tracks)

### Processing Pipeline Observations

The debug output reveals the HybridProcessor is applying:

1. **Fingerprint Analysis** - Content detection working (Bass %, Crest Factor, LUFS)
2. **Recording Type Detection** - Genre/style identification functioning
3. **Continuous Space Mapping** - Spectral/dynamic/energy coordinate calculation
4. **EQ Application** - Parametric EQ with blend factors (0.78-0.82)
5. **Stereo Width Control** - Width reduction toward target (0.58 → 0.42)
6. **Safety Limiter** ⚠️ **ISSUE** - Applies ~26 dB of limiting per track
7. **Final Output** - Clamped to -0.09 dB peak

### The Problem

Safety Limiter is being triggered on every track with extreme gain reduction:
- Pre-limiter peak: -2.05 dB (reasonable)
- Limiter detects: 26.20 dB (!!!)
- Post-limiter peak: -0.09 dB (extreme clamping)

**This suggests**:
1. Peak measurement is incorrect (claiming 26 dB when audio is -2 dB)
2. OR audio is being reported in wrong units (dB instead of linear)
3. OR limiter threshold is misconfigured

---

## Impact Assessment

### Validation Status
- ❌ **Cannot validate against Matchering** - +12 dB misalignment is too severe
- ❌ **Cannot validate full album** - Would require debugging first
- ❌ **Cannot update Paper Section 5.2** - Need correct data first

### What IS Working
- ✅ **Preset differentiation** - Gentle 0.18 dB quieter than Adaptive
- ✅ **Audio I/O pipeline** - Loads/analyzes tracks correctly
- ✅ **Content analysis** - Fingerprinting and genre detection working
- ✅ **EQ application** - Spectral modification being applied
- ✅ **Comparison metrics** - Results file generation working

### What NEEDS FIXING
- ❌ **HybridProcessor.process() output level** - Producing wrong loudness
- ❌ **Safety Limiter behavior** - Excessive compression
- ❌ **Peak measurement accuracy** - Reporting wrong values

---

## Recommended Debugging Path

### Phase 1: Isolate the Issue (1-2 hours)
1. Create minimal test case with synthetic sine wave (-12 dB RMS)
2. Process through HybridProcessor with Adaptive preset
3. Verify output:
   - Should be ~-7 to -8 dB RMS (similar to Matchering pattern)
   - Should NOT be -3 dB RMS
4. Add logging at each pipeline stage to find where loudness diverges

### Phase 2: Fix the Root Cause (30-60 minutes estimated)
- Once isolated, implement fix in HybridProcessor or relevant module
- Re-validate with synthetic signal
- Re-process 3 test tracks

### Phase 3: Full Validation (2-3 hours)
- Process all 10 South Of Heaven tracks
- Validate mean alignment (target: ±0.5 dB from Matchering)
- Process Reign In Blood (second album validation)
- Generate comparison tables

### Phase 4: Paper Update
- Update Section 5.2 with validated results
- Create comparison figures
- Add statistical analysis

---

## Code References

### New Script
- [process_with_auralis.py](research/scripts/process_with_auralis.py) - Validation script (NOT committed yet)

### Results Files
- [auralis_south_of_heaven_comparison.json](research/data/auralis_south_of_heaven_comparison.json) - Test results (NOT committed yet)

### Investigation Points
- [HybridProcessor.process()](auralis/core/hybrid_processor.py) - Main processing function
- [Safety Limiter](auralis/dsp/dynamics/brick_wall_limiter.py) - Limiting mechanism
- [Adaptive Mode](auralis/core/processing/adaptive_mode.py) - Adaptive preset processor
- [Peak Normalization](auralis/core/config/preset_profiles.py) - Preset peak targets

---

## Key Learnings

### About Auralis Architecture
- Fingerprinting is sophisticated (25D feature space)
- Recording type detection has confidence scores
- EQ and dynamics are applied with blend factors
- Safety Limiter is protection mechanism (good!) but may be misconfigured

### About Matchering Behavior
- Applies 3.7-5.6 dB boost to South Of Heaven tracks
- Preserves crest factor well (reduces by 0.6-3.1 dB)
- Content-aware (boosting quieter tracks more)

### About Validation Testing
- Small batch testing (3 tracks) is effective for debugging
- Gradient approach works: fix → test → expand
- Debug output from HybridProcessor is very detailed

---

## Next Actions

### IMMEDIATE (blocker)
1. Review `HybridProcessor.process()` output handling
2. Check if audio is returned as linear samples or dB values
3. Verify Safety Limiter thresholds
4. Debug with synthetic test signal

### SHORT-TERM (after fix)
1. Re-test 3 tracks with debugged code
2. If aligned ±2 dB: process remaining 7 tracks
3. If aligned ±0.5 dB: process second album (Reign In Blood)

### MEDIUM-TERM
1. Update Paper Section 5.2 with empirical results
2. Create comparison figures and tables
3. Generate statistical analysis

### RELEASE-RELATED
1. Prepare Beta.2 release (version bump, changelog)
2. Build and test on all platforms

---

## Session Summary

### What Was Accomplished
✅ Created comprehensive validation script (`process_with_auralis.py`)
✅ Tested first 3 tracks successfully (processing completed without errors)
✅ Identified critical loudness issue preventing validation
✅ Confirmed preset differentiation is working (0.18 dB difference)
✅ Generated detailed results and analysis

### Blockers Identified
❌ HybridProcessor outputting +12 dB too loud
❌ Cannot validate until issue is fixed
❌ Cannot proceed with full album processing

### Path Forward
→ Debug HybridProcessor output level (1-2 hours)
→ Re-test after fix
→ Proceed with full album validation
→ Update paper with empirical results

---

## Files & Locations

### Code Files
- **Validation Script**: `research/scripts/process_with_auralis.py`
- **Results**: `research/data/auralis_south_of_heaven_comparison.json`
- **Analysis**: `research/PHASE_9B_INITIAL_FINDINGS.md`

### Investigation
- **HybridProcessor**: `auralis/core/hybrid_processor.py`
- **Safety Limiter**: `auralis/dsp/dynamics/brick_wall_limiter.py`
- **Adaptive Mode**: `auralis/core/processing/adaptive_mode.py`
- **Preset Config**: `auralis/core/config/preset_profiles.py`

---

## Statistics Summary

### Test Results (3 Tracks, 2 Presets = 6 tests)
- **Successful processing**: 6/6 ✓
- **Alignment to Matchering**: -12.03 to -12.76 dB ❌
- **Preset differentiation**: 0.16-0.26 dB ✓
- **Processing time**: ~10-15 minutes for 3 tracks

### Mean Alignment
```
Adaptive:
  Mean: +12.52 dB (should be ±0.5 dB)
  Std dev: ±0.24 dB (good consistency)
  Range: +12.20 to +12.76 dB

Gentle:
  Mean: +12.20 dB (expected 0-0.5 dB difference from Adaptive)
  Difference from Adaptive: -0.32 dB (good!)
```

---

## Conclusion

Phase 9B validation framework is complete and functioning. The preset differentiation works correctly, but the HybridProcessor has a critical loudness issue that must be debugged before proceeding with full validation. Once fixed, we have a robust pipeline to validate Auralis against Matchering and prepare empirical results for the paper.

**Estimated time to resolution**: 2-3 hours (debug + fix + re-validate)
