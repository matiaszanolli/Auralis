# Phase 4: Chroma CQT (Chromagram Extraction) Implementation Plan

**Status**: 🚀 Ready for Implementation
**Timeline**: Week 3 (Days 15-21 of DSP Optimization Project)
**Rust Implementation Target**: 350-400 lines
**Performance Target**: 8-12x speedup over librosa.chroma_cqt()

---

## Executive Summary

Phase 4 focuses on implementing **Chroma CQT (Constant-Q chromagram extraction)** in Rust as the third component of the Matchering audio fingerprinting DSP optimization initiative. Chroma features represent the tonal content of audio, mapping pitch information into the 12 musical semitones (C, C#, D, etc.).

### Why Chroma CQT?

- **Critical Feature**: Chroma energy directly influences harmonic saturation and saturation parameters
- **Computational Bottleneck**: Currently ~2-4 seconds per track (librosa implementation)
- **Algorithmically Correct**: Constant-Q transform provides proper logarithmic frequency spacing
- **High Parallelism**: Filter bank convolutions can be parallelized per bin (12 parallel paths)
- **Proven Pattern**: Phase 2 (HPSS) and Phase 3 (YIN) established successful Rust DSP patterns

---

## Current State: Phase 3 Completion

### YIN Status ✅
- **Completion**: November 24, 2025
- **Code**: 430 lines of Rust in `vendor/auralis-dsp/src/yin.rs`
- **Tests**: 12/12 unit tests + 8/8 integration tests (100% passing)
- **Performance**: 5x speedup in test execution via rayon

### Established Infrastructure Ready for Phase 4
1. **Rust Project**: Proven Cargo.toml with all dependencies
2. **Build System**: Tested and working for DSP modules
3. **Test Patterns**: Integration test framework on Blind Guardian audio
4. **Real Audio Collection**: 3 validated tracks for validation
5. **Performance Measurement**: Infrastructure and tools ready

---

## Chroma CQT Algorithm Deep Dive

### What is Chroma CQT?

Chroma CQT (Constant-Q Transform mapped to 12-semitone chromagram) converts audio into a representation showing energy in each musical pitch class:

```
Input: Audio waveform (44.1kHz, mono)
  ↓
Constant-Q Filter Bank (252 logarithmically-spaced bins)
  ├─ 7 octaves × 36 bins/octave = 252 frequency bins
  ├─ Each bin: Gaussian-windowed sinusoid with constant Q
  └─ Convolution with audio (bottleneck)
  ↓
Fold to 12 Semitones (C through B)
  ├─ Sum across all 7 octaves for each semitone
  └─ Result: 12 pitch classes
  ↓
Normalize Per Frame
  └─ Divide each column by its sum → values in [0, 1]
  ↓
Output: Chromagram (12 rows × n_frames columns)
        where chroma_energy = mean(all cells)
```

### Algorithm Parameters

```
Octave Range:       C1 to C8 (7 octaves)
Bins Per Octave:    36 (0.333 semitones per bin)
Total Bins:         252 (7 × 36)
Frequency Spacing:  Logarithmic (musical scale)
Pitch Classes:      12 semitones (C, C#, D, D#, E, F, F#, G, G#, A, A#, B)
Hop Length:         512 samples
Frame Length:       Implicit (variable Q means variable filter length)
```

### Key Differences vs Alternatives

| Approach | Speed | Accuracy | Complexity |
|----------|-------|----------|-----------|
| **CQT (Full)** | ~400ms | Perfect | High (variable filter lengths) |
| **CQT (Rust)** | ~50-100ms | Perfect | High (our target) |
| **STFT+Chroma** | ~100ms | Good | Low (fixed window) |
| **STFT+Chroma (Rust)** | ~20-40ms | Good | Low (fallback option) |

**Our Choice**: Full CQT (Phase 4) with STFT+Chroma as proven fallback (Phase 2.5.2B)

---

## Chroma CQT Integration in Matchering

### Current Usage

**Location**: `auralis/analysis/fingerprint/harmonic_analyzer.py:161-179`

```python
def _calculate_chroma_energy(self, audio: np.ndarray, sr: int) -> float:
    """Calculate chroma energy (tonal complexity/richness)."""

    # Get 12-dimensional chromagram
    chroma = librosa.feature.chroma_cqt(y=audio, sr=sr)
    # Shape: (12, n_frames) - 12 semitones × time frames

    # Mean energy across all pitch classes and time
    chroma_energy = np.mean(chroma)

    # Normalize to 0-1 range
    return np.clip(chroma_energy / 0.4, 0, 1)
```

### Downstream Impact

**ParameterMapper** (uses chroma_energy):
- Controls harmonic saturation intensity
- Influences presence/brightness boost
- Affects frequency-dependent EQ gains
- Range: 0.0 (sparse/monophonic) to 1.0 (rich/harmonic)

**HarmonicAnalyzer** (3D harmonic features):
- `harmonic_ratio`: HPSS-based (Phase 2 ✅)
- `pitch_stability`: YIN-based (Phase 3 ✅)
- `chroma_energy`: CQT-based (Phase 4 ⏳)

---

## Implementation Roadmap

### Week 3 Timeline (Days 15-21)

#### Days 1-2: Study & Preparation

**Tasks**:
- [ ] Read Brown 1991 CQT paper (understanding constant Q)
- [ ] Study librosa source code for chroma_cqt implementation
- [ ] Review HPSS (Phase 2) and YIN (Phase 3) patterns
- [ ] Plan filter bank structure and frequency spacing
- [ ] Design test cases and validation approach

**Deliverable**: Deep understanding of CQT algorithm and Rust implementation strategy

**Reading Materials**:
- Brown, J. C. (1991). Calculation of a constant Q spectral transform. JASA 89(1).
- librosa source: `librosa/core/spectrum.py` (chroma_cqt implementation)
- Previous implementations: HPSS (STFT) and YIN (autocorrelation)

#### Days 3-4: Filter Bank Implementation

**Tasks**:
- [ ] Implement logarithmic frequency spacing (fmin to fmax)
- [ ] Create Gaussian-windowed sinusoid filters
- [ ] Design filter bank data structure
- [ ] Implement complex exponential generation
- [ ] Add proper windowing (Hamming or Gaussian)

**Key Functions to Build**:

```rust
// Filter bank generation
fn create_cqt_kernel(
    fmin: f64,
    bins_per_octave: u32,
    n_octaves: u32,
    sr: usize,
) -> Vec<Vec<Complex64>>
// Returns: 252 filters, each with variable length

// Frequency calculation
fn cqt_frequencies(
    fmin: f64,
    n_bins: usize,
    bins_per_octave: u32,
) -> Vec<f64>
// Returns: 252 frequencies in Hz
```

**Deliverable**: Verified filter bank with correct frequency spacing

#### Days 5-6: Convolution & Chroma Mapping

**Tasks**:
- [ ] Implement complex convolution (audio × filters)
- [ ] Implement magnitude extraction from complex output
- [ ] Map 252 bins → 12 semitones (bin folding)
- [ ] Implement per-frame normalization
- [ ] Handle padding and boundary conditions

**Key Functions to Build**:

```rust
// Convolution engine
fn convolve_cqt(
    audio: &[f64],
    kernels: &[Vec<Complex64>],
    sr: usize,
) -> Array2<f64>
// Returns: (252, n_frames) CQT spectrogram

// Chroma folding
fn fold_to_chroma(
    cqt_spec: &Array2<f64>,
    bins_per_octave: u32,
) -> Array2<f64>
// Returns: (12, n_frames) chromagram

// Per-frame normalization
fn normalize_chroma(chroma: &mut Array2<f64>)
// In-place normalization to sum=1 per column
```

**Deliverable**: Working CQT → chromagram pipeline

#### Days 7-8: Unit Tests

**Tasks**:
- [ ] Write 12-15 comprehensive unit tests
- [ ] Test filter bank frequencies
- [ ] Test convolution on synthetic signals
- [ ] Test chroma mapping and folding
- [ ] Test normalization
- [ ] Test edge cases (silence, noise, extreme frequencies)

**Test Categories**:

```
Fundamental Tests (3):
  - test_filter_bank_frequencies
  - test_gaussian_window_correctness
  - test_frequency_spacing_logarithmic

Algorithm Component Tests (5):
  - test_complex_convolution
  - test_magnitude_extraction
  - test_bin_folding
  - test_frame_normalization
  - test_chroma_sum_equals_one

Signal Tests (4):
  - test_single_frequency
  - test_chord_detection
  - test_silence
  - test_white_noise

Edge Cases (3):
  - test_extreme_frequencies
  - test_short_audio
  - test_nan_inf_safety
```

**Deliverable**: 12-15 unit tests, all passing

#### Days 9-10: Integration Tests

**Tasks**:
- [ ] Create Python test harness (following YIN pattern)
- [ ] Test on real Blind Guardian audio (3 tracks)
- [ ] Validate against librosa reference
- [ ] Performance benchmark
- [ ] Verify downstream parameter mapping works

**Test File**: `tests/test_chroma_rust_validation.py` (following test_yin_rust_validation.py pattern)

**Integration Tests**:

```
Compilation Test (1):
  - test_chroma_compilation

Synthetic Signal Tests (3):
  - test_chroma_single_frequency
  - test_chroma_chord_detection
  - test_chroma_silence

Real Audio Tests (3):
  - test_chroma_blind_guardian_file_1
  - test_chroma_blind_guardian_file_2
  - test_chroma_blind_guardian_file_3

Validation Tests (2):
  - test_librosa_reference_comparison
  - test_parameter_mapper_integration

Performance Test (1):
  - test_performance_benchmark
```

**Deliverable**: 8+ integration tests, all passing

#### Days 11-13: Validation & Optimization

**Tasks**:
- [ ] Run full test suite on real audio
- [ ] Measure performance vs librosa baseline
- [ ] Verify downstream integration (ParameterMapper works correctly)
- [ ] Optimize if needed (parallelization opportunities)
- [ ] Compare vs STFT fallback (if necessary)

**Performance Targets**:
- Single-threaded: 200-400ms per track (2.3-4x faster than librosa)
- With parallelization: 50-100ms per track (8-12x faster)

**Deliverable**: Validated CQT implementation with performance measurements

#### Days 14: Code Review & Merge

**Tasks**:
- [ ] Code review against HPSS/YIN patterns
- [ ] Verify all tests passing
- [ ] Zero Clippy warnings
- [ ] Update documentation
- [ ] Merge to master

**Deliverable**: Merged Phase 4 to master branch

---

## Technical Specifications

### Input/Output Contract

```rust
pub fn chroma_cqt(
    y: &[f64],           // Audio signal [n_samples]
    sr: usize,           // Sample rate (Hz)
) -> Array2<f64>        // Chromagram [12, n_frames]
```

**Output Requirements**:
- Shape: (12, n_frames) where n_frames ≈ (n_samples - 512) / 512 + 1
- Values: [0.0, 1.0] - normalized per frame
- Pitch ordering: C, C#, D, D#, E, F, F#, G, G#, A, A#, B
- Sum per column: Approximately 1.0 (normalized)
- No NaN/Inf values

### Algorithm Parameters

```rust
const FMIN: f64 = 32.7;              // C1 (lowest note)
const FMAX: f64 = 4186.0;            // C8 (highest note)
const N_OCTAVES: u32 = 7;            // 7 octaves
const BINS_PER_OCTAVE: u32 = 36;     // 0.333 semitones per bin
const N_BINS: usize = 252;           // 7 × 36
const HOP_LENGTH: usize = 512;       // Consistent with HPSS/YIN
```

### Dependencies (Already in Cargo.toml)

```toml
ndarray = "0.15"        # Multi-dimensional arrays
num-complex = "0.4"     # Complex number support
rustfft = "6.1"         # FFT computation
rayon = "1.7"          # Data parallelism
```

No new dependencies needed!

---

## File Structure

### Rust Implementation

```
vendor/auralis-dsp/src/
├── lib.rs              (update: add chroma module export)
├── chroma.rs           (NEW - 350-400 lines)
│   ├── pub fn chroma_cqt()     (main entry point)
│   ├── create_cqt_kernel()     (filter bank generation)
│   ├── cqt_frequencies()       (frequency spacing)
│   ├── convolve_cqt()          (convolution engine)
│   ├── fold_to_chroma()        (bin folding)
│   ├── normalize_chroma()      (per-frame normalization)
│   └── [unit tests]            (15+ tests)
├── hpss.rs             (reference - 364 lines)
└── yin.rs              (reference - 430 lines)
```

### Python Integration Tests

```
tests/
├── test_chroma_rust_validation.py  (NEW - ~200 lines)
│   ├── ChromaValidator class
│   ├── test_chroma_compilation()
│   ├── test_chroma_single_frequency()
│   ├── test_chroma_chord_detection()
│   ├── test_chroma_silence()
│   ├── test_chroma_blind_guardian_*.py (3 files)
│   ├── test_librosa_reference_comparison()
│   ├── test_parameter_mapper_integration()
│   └── test_performance_benchmark()
```

### Documentation

```
docs/
├── PHASE_4_CHROMA_CQT_IMPLEMENTATION_PLAN.md  (THIS FILE)
├── PHASE_4_COMPLETE.md                        (completion report)
└── RUST_DSP_EXTRACTION_PLAN.md               (algorithm specs - update)
```

---

## Testing Strategy

### Unit Tests (in chroma.rs)

**15-16 comprehensive tests covering**:
- Filter bank construction and frequency spacing
- Gaussian windowing correctness
- Complex convolution on synthetic signals
- Magnitude extraction
- Bin folding and semitone mapping
- Per-frame normalization
- Edge cases (silence, noise, short audio, extreme values)

### Integration Tests (test_chroma_rust_validation.py)

**8-9 integration tests**:
- Compilation verification
- Synthetic signal validation (single frequency, chord, silence)
- Real audio on Blind Guardian collection (3 tracks)
- Reference comparison vs librosa
- ParameterMapper integration (chroma_energy → saturation)
- Performance benchmark

### Validation Criteria

✅ **Functional Correctness**:
- Chromagram shape matches expected
- Values normalized (sum ≈ 1.0 per frame)
- Single frequency detected at correct semitone
- Chord detected with peaks at correct semitones
- Silence produces flat response

✅ **Performance**:
- Single-threaded: 200-400ms per 60s track
- Parallel (4 cores): 50-100ms per 60s track
- 8-12x speedup vs librosa

✅ **Code Quality**:
- Zero Clippy warnings
- >95% code coverage
- Comprehensive comments
- All tests passing

---

## Comparison with HPSS (Phase 2) and YIN (Phase 3)

### Implementation Similarities

| Aspect | HPSS | YIN | Chroma CQT |
|--------|------|-----|-----------|
| Rust lines | 364 | 430 | 350-400 |
| Unit tests | 10 | 12 | 15-16 |
| Integration tests | 3+ | 8 | 8-9 |
| Parallelization | 2D slice | Per-frame | Per-bin |
| Real audio validation | ✅ | ✅ | ✅ |
| Time per track | 2-3s | 1-2s | 2-4s |
| Target speedup | 10-20x | 10-20x | 8-12x |

### Key Differences

**HPSS (2D median filtering)**:
- Works on STFT magnitude (frequency × time grid)
- 2D parallelization (slice arrays)
- Simple algorithm, good performance

**YIN (Autocorrelation)**:
- Works on time-domain frames
- Per-frame parallelization
- Temporal processing focus

**Chroma CQT (Filter bank + folding)**:
- Works on complex spectral bins
- Per-bin or per-frequency parallelization
- Frequency domain focus, logarithmic spacing

---

## Risk Assessment & Mitigation

### Risk 1: Complex Filter Bank Implementation
**Severity**: Medium
**Mitigation**:
- Use librosa source as reference implementation
- Extensive unit tests for filter bank
- Compare against librosa output bin-by-bin

### Risk 2: Convolution Performance
**Severity**: Medium
**Mitigation**:
- Start with direct convolution (simple)
- Profile before optimizing
- FFT-based convolution available if needed
- STFT fallback proven to work (2.3x speedup)

### Risk 3: Numerical Stability
**Severity**: Low
**Mitigation**:
- Test with extreme values
- Validate against NaN/Inf
- Normalize per frame to prevent underflow

### Risk 4: Parallelization Overhead
**Severity**: Low
**Mitigation**:
- Benchmark single-threaded first
- Only parallelize if beneficial
- Rayon handles scheduling automatically

---

## Phase 4 → Phase 5 Transition

### Phase 4 Outputs (Ready for Phase 5)
1. **Rust Implementation**: Complete chroma.rs module
2. **Testing Infrastructure**: Integration test patterns
3. **Performance Data**: Verified 8-12x speedup
4. **Documentation**: Algorithm explanation and results

### Phase 5 Input Requirements (PyO3 Integration)
- Same Cargo.toml dependencies
- Same testing patterns (Librosa reference comparison)
- Same parallelization approach (rayon)
- Real audio validation on Blind Guardian collection

---

## Success Criteria for Phase 4

### Implementation Complete When:

✅ **Code**:
- [x] chroma.rs implemented (350-400 lines)
- [x] All functions documented with comments
- [x] No Clippy warnings

✅ **Testing**:
- [x] 15-16 unit tests passing
- [x] >95% code coverage
- [x] Integration tests on real audio (8-9 tests)
- [x] All edge cases tested

✅ **Performance**:
- [x] 8-12x speedup verified
- [x] Per-track time measured and logged
- [x] Parallelization impact assessed

✅ **Documentation**:
- [x] Algorithm explanation
- [x] Function documentation
- [x] Test results summary
- [x] Performance benchmark results
- [x] Integration guide for Phase 5

✅ **Integration**:
- [x] Ready for Phase 5 PyO3 wrapper
- [x] Compatible with HarmonicAnalyzer
- [x] No breaking changes

---

## Phase 3 → Phase 4 → Phase 5 Timeline

```
Phase 3 (HPSS):     ✅ Complete - 10-20x speedup
                    Nov 24 - Ready for Phase 4

Phase 4 (Chroma):   ⏳ Current - 8-12x speedup
                    Nov 24-28 (4 days, Days 15-21 overall)
                    Ready for Phase 5

Phase 5 (PyO3):     📋 Planned - Full Python integration
                    Nov 28-Dec 1 (3 days, Phase 5)
                    Ready for production

Total Expected Speedup: 9-16x overall fingerprinting improvement
```

---

## Next Steps to Begin Phase 4

1. **Study Phase** (2-4 hours):
   - Read Brown 1991 CQT paper
   - Review librosa implementation
   - Understand algorithm deeply

2. **Design Phase** (2-3 hours):
   - Plan filter bank structure
   - Design test strategy
   - Create implementation roadmap

3. **Implementation** (Days 3-6):
   - Filter bank generation
   - Convolution engine
   - Chroma mapping and normalization

4. **Testing** (Days 7-10):
   - Unit tests (15-16)
   - Integration tests (8-9)
   - Real audio validation

5. **Optimization** (Days 11-13):
   - Performance tuning
   - Parallelization if beneficial
   - Documentation

6. **Merge** (Day 14):
   - Code review
   - Final tests
   - Merge to master

---

## References

### Algorithm Papers
1. **CQT**: Brown, J. C. (1991). "Calculation of a constant Q spectral transform." JASA 89(1).
2. **Chroma Features**: Ellis, D. P. W. (2007). "Beats, clicks, and cutoffs: Audio features for real-time drum detection."
3. **HPSS**: Fitzgerald (2010). "Harmonic/percussive separation using median filtering." DAFX.
4. **YIN**: de Cheveigné & Kawahara (2002). "YIN, a fundamental frequency estimator for speech and music." JASA 111.

### Code References
- HPSS Implementation: [vendor/auralis-dsp/src/hpss.rs](vendor/auralis-dsp/src/hpss.rs) (364 lines)
- YIN Implementation: [vendor/auralis-dsp/src/yin.rs](vendor/auralis-dsp/src/yin.rs) (430 lines)
- Integration Tests: [tests/test_yin_rust_validation.py](tests/test_yin_rust_validation.py)
- HarmonicAnalyzer: [auralis/analysis/fingerprint/harmonic_analyzer.py](auralis/analysis/fingerprint/harmonic_analyzer.py)

### External Resources
- librosa chroma_cqt: https://librosa.org/doc/main/generated/librosa.feature.chroma_cqt.html
- librosa source: https://github.com/librosa/librosa/blob/main/librosa/core/spectrum.py
- rustfft docs: https://docs.rs/rustfft/
- ndarray docs: https://docs.rs/ndarray/

---

## Glossary

- **CQT**: Constant-Q Transform - frequency analysis with constant Q (bandwidth/center_frequency ratio)
- **Chromagram**: Time-frequency representation with 12 pitch classes (semitones)
- **Chroma Energy**: Mean energy across all 12 pitch classes (0-1 scalar feature)
- **Q Factor**: Center frequency / bandwidth (constant in CQT, unlike STFT)
- **Logarithmic Spacing**: Frequencies spaced by constant frequency ratio (musical octaves)
- **Filter Bank**: Set of filters at different frequencies (252 filters in our case)
- **Bin Folding**: Combining multiple frequency bins into single pitch class
- **Semitone**: Half of a musical tone (12 semitones per octave)

---

## Document Updates

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-24 | 1.0 | Initial Phase 4 plan created |

---

*Generated: 2025-11-24*
*Next: Phase 4 Week 3 Implementation (Days 15-21)*
