# Phase 4: Chroma CQT - Algorithm Study (Days 1-2) ✅

**Date**: November 24, 2025
**Status**: Algorithm Study Complete
**Objective**: Deep understanding of CQT algorithm and implementation strategy

---

## 1. Constant-Q Transform (CQT) - Algorithm Foundation

### What is CQT?

The Constant-Q Transform is a time-frequency analysis technique where all frequency bins have constant **Q factor**:

```
Q = center_frequency / bandwidth
```

Unlike STFT (which uses fixed window length), CQT uses variable filter lengths:
- **Low frequencies**: Longer filters (better frequency resolution, worse time resolution)
- **High frequencies**: Shorter filters (worse frequency resolution, better time resolution)

This matches human auditory perception (logarithmic frequency spacing).

### CQT vs STFT

| Property | STFT | CQT |
|----------|------|-----|
| Frequency spacing | Linear | Logarithmic |
| Filter length | Fixed | Variable |
| Q factor | Varies | Constant |
| Frequency bins | 1024+ | 252 (for chroma) |
| Audio perception match | Fair | Excellent |
| Computational cost | Low-Medium | High |

### Mathematical Definition

For each frequency bin `k`:

```
kernel[k] = windowed_sinusoid(f_k) for f_k = f_min * 2^(k / bins_per_octave)

Where:
  f_min = 32.7 Hz (C1)
  bins_per_octave = 36 (0.333 semitone spacing)
  n_bins = 252 (7 octaves)
```

Filter length for bin `k`:
```
window_length[k] = ceil(Q * sr / f_k)

Where Q ≈ 34.66 (for 36 bins/octave)
```

### Key Parameters for Phase 4

```rust
const FMIN: f64 = 32.7;              // C1 (lowest)
const FMAX: f64 = 4186.0;            // C8 (highest)
const BINS_PER_OCTAVE: u32 = 36;     // 0.333 semitones per bin
const N_OCTAVES: u32 = 7;            // 32.7 Hz to 4186 Hz
const N_BINS: usize = 252;           // 7 × 36
const HOP_LENGTH: usize = 512;       // Consistent with HPSS/YIN
const Q_FACTOR: f64 = 34.66;         // Derived from 36 bins/octave
```

---

## 2. Chromagram - From CQT to 12 Semitones

### Chroma Mapping Process

The 252 CQT bins are **folded** into 12 semitones (one octave):

```
bin_to_semitone = bin % 36   (gives 0-35, then map to 0-11)
```

For example:
- Bins 0-35: C (octave 1-7)
- Bins 36-71: C# (octave 1-7)
- ...
- Bins 216-251: B (octave 1-7)

### Output Shape

```
Input:  (252, n_frames)   <- CQT magnitude spectrogram
            ↓
        [Bin folding + per-octave summation]
            ↓
Output: (12, n_frames)    <- Chromagram (normalized)
```

### Normalization

Per-frame normalization ensures values sum to 1.0:

```
chroma[:, frame_idx] /= sum(chroma[:, frame_idx]) + epsilon
```

This gives energy distribution across 12 pitch classes per frame.

---

## 3. Implementation Strategy - High-Level Overview

### Three Main Stages

#### Stage 1: Filter Bank Generation
```
Create 252 complex exponential filters with Gaussian windowing
- Each filter tuned to logarithmic frequency
- Variable filter length based on Q factor
- Pre-compute once, reuse for all audio frames
```

#### Stage 2: Convolution
```
Convolve audio with all 252 filters
- Variable-length filters for each bin
- Result: (252, n_frames) complex spectrogram
- Extract magnitude (discard phase)
```

#### Stage 3: Chroma Mapping & Normalization
```
Fold 252 bins → 12 semitones per frame
Normalize so each column sums to 1.0
Output: (12, n_frames) chromagram
```

### Rust Parallelization Strategy

**Per-bin parallelization using Rayon**:
```rust
let chromagram: Vec<Vec<f64>> = (0..N_BINS)
    .into_par_iter()
    .map(|bin_idx| {
        convolve_audio_with_filter(audio, kernels[bin_idx])
    })
    .collect();
```

Each bin is processed independently → excellent parallelization.

---

## 4. Reference Implementation Analysis

### How librosa.feature.chroma_cqt Works

From librosa source code (simplified):

```python
def chroma_cqt(y, sr, ...):
    # Step 1: Compute CQT (constant-Q transform)
    C = librosa.cqt(y, sr=sr, ...)  # Shape: (252, n_frames)

    # Step 2: Compute magnitude
    S = np.abs(C)  # Complex → real magnitude

    # Step 3: Log compression (optional)
    S = librosa.power_to_db(S)  # dB scale

    # Step 4: Fold to chroma (252 → 12)
    chromagram = np.zeros((12, S.shape[1]))
    for bin_idx in range(252):
        semitone = bin_idx % 12
        chromagram[semitone, :] += S[bin_idx, :]

    # Step 5: Normalize per column
    chromagram /= (chromagram.sum(axis=0, keepdims=True) + 1e-10)

    return chromagram  # Shape: (12, n_frames)
```

### Key Implementation Details

1. **Log Compression**: librosa uses `power_to_db()` but for our use case (chroma_energy = mean(chromagram)), linear magnitude is sufficient
2. **Normalization Epsilon**: Use small epsilon (1e-10) to avoid division by zero
3. **Bin Folding**: Simple modulo operation maps 252 → 12
4. **Frame Count**: `n_frames = ceil(audio_len / hop_length)`

---

## 5. Algorithm Validation Approach

### Test Cases Planned

#### Unit Tests (15-16 total)

**Filter Bank Tests (3)**:
- Verify frequency spacing is logarithmic
- Verify filter lengths match Q factor formula
- Verify window is Gaussian (or similar)

**Convolution Tests (3)**:
- Single frequency detection (440 Hz → peak at C)
- Chord detection (C+E+G → peaks at C, E, G)
- Complex signal (multiple overlapping frequencies)

**Chroma Mapping Tests (3)**:
- Bin folding is correct (252 → 12)
- Per-frame normalization (sum ≈ 1.0)
- Output shape is (12, n_frames)

**Edge Cases (3)**:
- Silence (all values near zero)
- Short audio (< hop_length)
- Extreme values (prevent NaN/Inf)

#### Integration Tests (8-9 total)

- Real audio validation on Blind Guardian tracks
- Comparison against librosa.chroma_cqt()
- Performance benchmark vs librosa
- ParameterMapper integration test

### Validation Criteria

✅ **Accuracy**:
- Harmonic content correctly detected in real audio
- Energy distributed correctly across semitones

✅ **Numerical Stability**:
- No NaN/Inf values
- Proper handling of silent frames

✅ **Performance**:
- 8-12x speedup vs librosa

---

## 6. Implementation Pattern from HPSS & YIN

### Established Patterns to Follow

#### From HPSS (364 lines):
- Use `ndarray::Array2` for 2D arrays
- Complex convolution with `num_complex::Complex64`
- Per-frame processing with rayon parallelization
- Gaussian windowing for filters

#### From YIN (430 lines):
- Frame-level independence enables parallelization
- Simple pure functions (no state)
- Comprehensive edge case handling
- Rayon `.into_par_iter()` for frame-level parallelism

#### For CQT:
- Per-bin independence → `.into_par_iter()` on bins
- Variable-length filters (unlike HPSS fixed STFT)
- Complex convolution (like HPSS, unlike YIN)
- Magnitude extraction (like HPSS)

### Code Structure to Match

```
1. Constants at top (frequency parameters)
2. Helper functions (filter bank, frequency calculation)
3. Main public function with doc comments
4. Integration with rayon for parallelization
5. Comprehensive unit tests at bottom
```

---

## 7. Expected Implementation Size

### Code Breakdown

```
chroma_cqt() entry point:           ~50 lines
create_filter_bank():                ~60 lines  (complex exponentials + windowing)
cqt_frequencies():                   ~20 lines  (logarithmic spacing)
convolve_cqt():                      ~80 lines  (per-bin convolution)
fold_to_chroma():                    ~30 lines  (bin folding + normalization)
helper functions:                    ~40 lines  (window generation, etc.)
─────────────────────────────────
Total implementation:               ~280 lines
Unit tests:                         ~150 lines
─────────────────────────────────
Total module:                       ~430 lines
```

Expected: 350-400 lines total (similar to YIN)

---

## 8. Key Implementation Challenges & Solutions

### Challenge 1: Variable-Length Filters
**Problem**: Each CQT bin has different filter length, making vectorization difficult

**Solution**:
- Pre-compute all filter lengths
- Store filters as `Vec<Vec<Complex64>>`
- Use loop-based convolution (simple, correct)
- Parallelize the outer loop (per-bin)

### Challenge 2: Numerical Precision
**Problem**: CQT can produce very small values (frequency bins far from signal content)

**Solution**:
- Use `f64` for all calculations
- Add epsilon in normalization to prevent 0/0
- Clamp output to [0, 1] after normalization

### Challenge 3: Performance
**Problem**: Convolution is O(n_frames × filter_length) per bin

**Solution**:
- Rayon parallelization (per-bin)
- Consider FFT-based convolution if needed (fallback)
- Expected: 50-100ms per 60-second track with 4 cores

### Challenge 4: Integration with librosa
**Problem**: Rust output must match librosa output for validation

**Solution**:
- Use same parameters (fmin, bins_per_octave, hop_length)
- Log compression not needed (chroma_energy doesn't require it)
- Compare magnitude output, not dB scale
- Relax tolerance for floating-point comparison (±5%)

---

## 9. Dependencies Check

All required crates already in Cargo.toml:

```toml
✅ ndarray = "0.15"      # 2D array storage
✅ num-complex = "0.4"   # Complex numbers
✅ rustfft = "6.1"       # FFT (if needed)
✅ rayon = "1.7"         # Parallelization
```

No new dependencies needed!

---

## 10. Phase 4 → Phase 5 Transition

### Phase 4 Deliverables (Ready for PyO3)

1. **chroma.rs**: Complete, tested implementation
2. **Integration tests**: Validated against librosa
3. **Performance**: 8-12x speedup confirmed
4. **Documentation**: Algorithm and usage

### Phase 5 Requirements

PyO3 wrapper will create Python binding:
```python
import auralis_dsp
chroma = auralis_dsp.chroma_cqt(audio, sr=44100)
```

Phase 4 must ensure:
- ✅ Correct function signature
- ✅ Correct output shape (12, n_frames)
- ✅ Correct output values (normalized)
- ✅ No panics or undefined behavior

---

## 11. Algorithm Study Summary

### Core Concepts Understood

1. **CQT Principle**: Logarithmic frequency spacing via variable filter lengths
2. **Q Factor**: center_freq / bandwidth = constant (≈34.66 for music)
3. **Chroma Mapping**: 252 bins folded to 12 semitones via modulo arithmetic
4. **Normalization**: Per-frame column normalization for energy distribution
5. **Parallelization**: Per-bin independence → rayon `.into_par_iter()`

### Implementation Ready

- ✅ Algorithm fully understood
- ✅ Integration point clear (HarmonicAnalyzer._calculate_chroma_energy)
- ✅ Test strategy defined (unit + integration)
- ✅ Code patterns established (from HPSS/YIN)
- ✅ Dependencies verified
- ✅ Performance targets set (8-12x speedup)

### Next Steps

**Days 3-4**: Implement filter bank generation
- Logarithmic frequency spacing
- Gaussian-windowed complex exponentials
- Unit test each component

**Days 5-6**: Implement convolution + chroma mapping
- Per-bin convolution with variable-length filters
- Magnitude extraction
- Bin folding and normalization

**Days 7-8**: Comprehensive unit tests (15-16)
**Days 9-10**: Integration tests on real audio
**Days 11-13**: Validation and optimization
**Day 14**: Code review and merge

---

*Generated: 2025-11-24 - Phase 4 Algorithm Study Complete*
