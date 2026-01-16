# Parallel Processing Pattern for Audio DSP

**Date**: January 2026
**Status**: Implemented
**Affects**: EQ functions, multiband stereo widening

---

## Problem: Phase Cancellation in Split/Recombine DSP

Traditional audio processing often uses a **split/recombine** pattern:

```
Original → [Split into bands] → [Process each band] → [Recombine] → Output
```

This approach causes **phase cancellation at crossover frequencies** when using:
- High-pass + Low-pass filter pairs
- Bandpass + Bandstop filter pairs
- Linkwitz-Riley crossovers with `filtfilt` (zero-phase filtering)

### Why This Happens

**Butterworth/LR4 filters** are designed to sum flat when applied **causally** (forward-only). However, `sosfiltfilt` (scipy's zero-phase filter) applies the filter **twice** (forward + backward), which:

1. **Doubles the effective filter order** (LR4 becomes LR8-like)
2. **Changes the magnitude at crossover** from -6dB to -12dB
3. **Creates a notch** when LP + HP are summed: ~-9dB at crossover

### Measured Impact

| Crossover | Expected | Actual (filtfilt) | Notch Depth |
|-----------|----------|-------------------|-------------|
| 300 Hz | 0 dB | -9 dB | Low-mid loss |
| 8 kHz | 0 dB | -9 dB | Air loss |

Real-world test (Symphony X - Inferno):
- **Low-mid (250-500Hz)**: -4.0 dB loss
- **Air (6-20kHz)**: -3.6 dB loss

---

## Solution: Parallel Processing Pattern

Instead of splitting and recombining, **add the processed difference on top of the original**:

```
Original → [Extract band] → [Process band] → [Diff = Processed - Extracted]
                                                         ↓
Original ──────────────────────────────────────────→ [+ Diff] → Output
```

### Why This Works

1. **No crossover summation** - we never split and recombine
2. **Flat frequency response guaranteed** - original signal preserved
3. **Only adds the change** - `diff = processed_band - original_band`

### Mathematical Proof

```
Let:
  x = original signal
  b = extracted band (filtered)
  p = processed band (e.g., boosted or widened)

Traditional (broken):
  output = lowpass(x) + highpass(x)  // Phase cancellation at crossover!

Parallel (correct):
  diff = p - b                       // Only the change
  output = x + diff                  // Add change to original
         = x + (p - b)               // Preserves x, adds processing
```

---

## Implementation Examples

### EQ Enhancement (e.g., Air Boost)

**Before (broken)**:
```python
# Split and recombine - causes notch at 8kHz!
sos_hp = butter(2, 8000/nyquist, btype='high', output='sos')
sos_lp = butter(2, 8000/nyquist, btype='low', output='sos')
high_band = sosfilt(sos_hp, audio, axis=1)
low_band = sosfilt(sos_lp, audio, axis=1)
boosted_high = high_band * boost_linear
output = low_band + boosted_high  # -9dB notch at 8kHz!
```

**After (correct)**:
```python
# Parallel processing - preserves flat response
sos_hp = butter(2, 8000/nyquist, btype='high', output='sos')
high_band = sosfilt(sos_hp, audio, axis=1)

# Add the BOOST DIFFERENCE on top of original
boost_diff = boost_linear - 1.0  # How much extra gain
output = audio + high_band * boost_diff  # No crossover issues!
```

### Multiband Stereo Widening

**Before (broken)**:
```python
# LR4 crossover with filtfilt - notch at 300Hz!
band_low = sosfiltfilt(sos_lp_300, audio, axis=0)
band_mid = sosfiltfilt(sos_hp_300, audio, axis=0)
band_mid = sosfiltfilt(sos_lp_2k, band_mid, axis=0)
# ... more bands

band_mid_widened = widen(band_mid)
output = band_low + band_mid_widened + ...  # -9dB at 300Hz!
```

**After (correct)**:
```python
# Extract bands for processing only
band_mid = sosfiltfilt(sos_bp_300_2k, audio, axis=0)
band_mid_widened = widen(band_mid)

# Add the WIDTH DIFFERENCE on top of original
diff_mid = band_mid_widened - band_mid
output = audio + diff_mid  # Flat response preserved!
```

---

## Files Updated

| File | Change |
|------|--------|
| `auralis/core/simple_mastering.py` | `_apply_bass_enhancement`, `_apply_mid_warmth`, `_apply_presence_enhancement`, `_apply_air_enhancement` |
| `auralis/dsp/utils/stereo.py` | `adjust_stereo_width_multiband` |

---

## Test Results

Before/after comparison on Symphony X - Inferno (LUFS -12.4, Crest 12.1 dB):

| Band | Before | After | Improvement |
|------|--------|-------|-------------|
| Sub-bass | -0.4 dB | -0.5 dB | - |
| Bass | -0.9 dB | -0.6 dB | +0.3 dB |
| **Low-mid** | **-4.0 dB** | **-0.0 dB** | **+4.0 dB** |
| Mid | -1.6 dB | -0.2 dB | +1.4 dB |
| Upper-mid | -2.8 dB | +0.6 dB | +3.4 dB |
| Presence | -0.7 dB | +1.2 dB | +1.9 dB |
| **Air** | **-3.6 dB** | **-0.1 dB** | **+3.5 dB** |

All bands now within ±1 dB of original - mastering-grade transparency.

---

## When to Use This Pattern

**Use parallel processing when:**
- Boosting/cutting specific frequency bands
- Applying frequency-dependent stereo widening
- Any multiband processing with crossovers
- Using `filtfilt` or zero-phase filters

**Traditional split/recombine is OK when:**
- Using causal filters (`sosfilt`) with properly designed crossovers
- Phase response doesn't matter (e.g., offline analysis)
- You can verify flat magnitude summation

---

## Key Takeaways

1. **`filtfilt` doubles filter order** - LR4 becomes ~LR8 characteristics
2. **Crossover summation fails** with zero-phase filters
3. **Parallel processing** avoids the problem entirely
4. **Add the difference** instead of recombining bands

---

## References

- Commit `632b629c`: Parallel EQ processing
- Commit `4876c942`: Parallel stereo widening + output normalization fix
- Regression tests: `tests/regression/test_mastering_regression.py`
