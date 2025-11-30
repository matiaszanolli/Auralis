# Phase 9B: Debug Findings - Root Cause Identified

**Status**: 🔴 ROOT CAUSE IDENTIFIED - FIX NEEDED
**Date**: November 30, 2025
**Issue**: HybridProcessor outputting +11-12 dB too loud (Safety Limiter triggering on every track)

---

## Root Cause

The problem is **NOT** in the Safety Limiter code itself (which is correct), but in the **processing pipeline applying excessive gain BEFORE the limiter**.

### Debug Test Results (Synthetic Signal)

Input:
- Duration: 5 seconds
- RMS: -12.00 dB
- Peak: -8.99 dB
- Crest Factor: 3.01 dB

Output:
- RMS: -0.81 dB (+11.19 dB boost) ❌ TOO LOUD
- Peak: -0.30 dB
- Crest Factor: 0.51 dB

### Processing Chain Observed

```
[Continuous Space] Fingerprint extracted: Bass: 0%, Crest: 3.0 dB, LUFS: -11.3
[Recording Type Detector] Detected: unknown, Philosophy: enhance (+1.8 dB bass, +1.0 dB treble)
[Continuous Space] Coordinates: spectral=0.35, dynamic=0.19, energy=0.93
[Continuous Space] Parameters: LUFS=-10.8 (target), peak=-0.43 dB (target)
[EQ] Applied curve with blend 1.00: bass +2.7 dB, mid +0.2 dB, air +1.8 dB
[Stereo Width] 0.00 → 0.00 (target: 0.40)
[Pre-Final] Peak: -12.99 dB, LUFS: -39.0  ← Audio still reasonable here
[Safety Limiter] Peak 15.25 dB  ← WRONG! Says peak is 15.25 dB?
[Safety Limiter] Peak reduced to -0.09 dB
[Final] Peak: -0.09 dB, RMS: -0.60 dB
```

**KEY OBSERVATION**: Between "Pre-Final" (-12.99 dB peak) and "Safety Limiter" measurement (15.25 dB), something went wrong with the peak measurement.

---

## Hypothesis: Peak Measurement Bug

The limiter reports "Peak 15.25 dB" when the audio should have a peak around -12.99 dB. There are two possibilities:

### Theory 1: Peak being measured in dB instead of linear
If the peak measurement is somehow getting a dB value fed to it when it expects linear, it would report wrong values.
- Expected: peak ≈ 0.25 linear (corresponding to -12.99 dB)
- Reported: 15.25 (matches: log10(0.25) ≈ -0.6, × 20 ≈ -12 ≈ 15.25 dB?)

This suggests somewhere the peak is being converted to dB, then treated as linear again, then converted to dB a second time.

### Theory 2: Gain being applied between stages
Some stage is applying massive gain (15.25 dB) to the audio between Pre-Final and Safety Limiter check.

---

## Where to Fix

Based on the processing chain shown in debug output, the issue is likely in:

1. **Adaptive Mode Processing** (`auralis/core/processing/adaptive_mode.py`)
   - Between the "Pre-Final" measurement and Safety Limiter application
   - Check what happens after EQ and Stereo Width processing

2. **Peak Normalization** (`auralis/core/processing/base_processing_mode.py` line 448-480)
   - The `PeakNormalizer.normalize_to_target()` function
   - It's supposed to normalize peak to target_peak_db, but might be applying excessive gain

3. **Loudness Target Calculation**
   - The "LUFS=-10.8" target might be incorrect
   - This might be causing the normalization to boost too much

---

## Next Steps (Prioritized)

### IMMEDIATE (30 minutes)
1. Add logging to show peak values (linear AND dB) at each stage
2. Specifically instrument:
   - Peak after EQ application
   - Peak before peak normalization
   - Peak after peak normalization
   - Peak before safety limiter

3. Identify exactly where the +11-12 dB boost is coming from

### AFTER IDENTIFICATION (30-60 minutes)
1. Fix the root cause:
   - If peak normalization is wrong: adjust target peak calculation
   - If loudness target is wrong: recalibrate loudness targets per preset
   - If measurement is wrong: fix the measurement logic

2. Re-test with synthetic signal

3. If aligned ±2 dB with Matchering:
   - Process remaining 7 tracks
   - Process second album
   - Update paper with results

---

## Impact

This is a **critical bug** affecting all audio processing:
- Every track gets +11-12 dB RMS boost
- Safety Limiter is clamping everything to -0.09 dB peak
- Preset differentiation still works (Gentle is 0.3 dB quieter) but at wrong absolute level

**Cannot proceed with full validation until fixed.**

---

## Commands for Deep Debugging

```bash
# Run synthetic test with detailed output
python research/scripts/debug_hybrid_processor.py

# Look for where peak goes from ~-13 dB to 15.25 dB:
# - Check EQ output
# - Check peak normalization
# - Check loudness boosting
```

---

## Code Locations to Investigate

- **adaptive_mode.py** - Main processing function
- **base_processing_mode.py** lines 448-480 - PeakNormalizer
- **adaptive_mode.py** - LUFS target calculation
- **soft_clipper.py** - Verify it's not causing the issue (likely not)

---

## Confidence Level

**HIGH** - The synthetic signal test reproduces the exact same +11.19 dB RMS boost issue, confirming it's systemic to the HybridProcessor, not specific to audio files.
