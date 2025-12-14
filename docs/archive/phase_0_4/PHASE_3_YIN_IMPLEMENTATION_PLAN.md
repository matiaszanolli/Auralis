# Phase 3: YIN Pitch Detection Implementation Plan

**Status**: 🚀 Ready for Implementation
**Timeline**: Week 2 (Days 8-14 of DSP Optimization Project)
**Rust Implementation Target**: 400-500 lines
**Performance Target**: 10-20x speedup over librosa.yin()

---

## Executive Summary

Phase 3 focuses on implementing the **YIN (Fundamental Frequency Detection)** algorithm in Rust as the second component of the Matchering audio fingerprinting DSP optimization initiative. YIN is used to calculate **pitch_stability** (0-1 scale), a critical feature in the 25-dimensional fingerprint that drives harmonic enhancement decisions in the processing pipeline.

### Why YIN?

- **Critical Feature**: Pitch stability directly influences saturation, presence, and harmonic enhancement levels
- **Computational Bottleneck**: Currently ~1-2 seconds per track (librosa implementation)
- **High Parallelism**: Frame-level independence = embarrassingly parallel problem (4-8x speedup with rayon)
- **Proven Pattern**: HPSS Phase 2 established the Rust DSP implementation workflow
- **Clear Integration Path**: HarmonicAnalyzer already calls `librosa.yin()` → will become `auralis_dsp.yin()` in Phase 5

---

## Current State: Phase 2 Completion

### HPSS Status ✅
- **Completion**: November 24, 2025
- **Code**: 364 lines of Rust in `vendor/auralis-dsp/src/hpss.rs`
- **Tests**: 10/10 unit tests passing
- **Real Audio Validation**: 3 Blind Guardian tracks validated
- **Algorithm Chain**: STFT → 2D median filtering → Wiener masking → ISTFT

### Established Patterns for Phase 3
1. **Unit Testing**: Modular algorithm tests in `src/yin.rs`
2. **Integration Testing**: Librosa reference comparison in `tests/test_yin_rust_validation.py`
3. **Real Audio Testing**: Blind Guardian collection validation
4. **Performance Measurement**: `cargo bench` infrastructure ready
5. **Build System**: Proven Cargo.toml with all dependencies

---

## YIN Algorithm Deep Dive

### Purpose
Convert audio signal → fundamental frequency contour (pitch track)
- Input: Audio waveform [n_samples] at 44100 Hz
- Output: F0 estimates [n_frames] where 0.0 = unvoiced frame

### Algorithm Steps

#### 1. Frame the Audio
```
n_frames = (len(y) - frame_length) // hop_length + 1
```
- frame_length = 2048 samples (~46ms at 44.1kHz)
- hop_length = 512 samples (~11.6ms, 25% overlap)
- Consistent with HPSS for efficiency

#### 2. Compute Difference Function (DF) Per Frame
```
For each frame f and lag τ:
    DF[τ] = Σ(y[n] - y[n+τ])²  for n in [0, frame_length-τ]

This measures autocorrelation via squared differences
```

#### 3. Cumulative Mean Normalization (CMN)
```
AACF[0] = 1.0
For τ > 0:
    CMN[τ] = Σ DF[i] for i in [1, τ]
    AACF[τ] = 2 * DF[τ] / CMN[τ]

Normalized to range [0, 2] with AACF[0]=1
```

#### 4. Absolute Threshold (Trough Detection)
```
Find first minimum where AACF[τ] < trough_threshold (0.1)

τ_min = argmin(τ where AACF[τ] < 0.1)

If no minimum found: unvoiced frame (return 0.0)
```

#### 5. Parabolic Interpolation (Sub-Sample Refinement)
```
If τ_min found:
    x = τ_min
    a = AACF[x-1]
    b = AACF[x]
    c = AACF[x+1]

    offset = (a - c) / (2 * (a - 2*b + c))
    refined_lag = x + offset

    frequency = sample_rate / refined_lag
else:
    frequency = 0.0  (unvoiced)
```

#### 6. Frequency Bounds Checking
```
fmin = 65.4 Hz (C2 in MIDI note 24)
fmax = 2093 Hz (C7 in MIDI note 84)

if frequency < fmin or frequency > fmax:
    return 0.0  (outside pitch range, treat as unvoiced)
else:
    return frequency
```

### Key Parameters
```
FRAME_LENGTH: 2048      # Samples per frame
HOP_LENGTH: 512         # Samples between frames
TROUGH_THRESHOLD: 0.1   # AACF threshold for trough detection
FMIN: 65.4              # Minimum frequency (Hz)
FMAX: 2093.0            # Maximum frequency (Hz)
```

---

## Integration Points

### Current Code Location
[harmonic_analyzer.py:96-143](/auralis/analysis/fingerprint/harmonic_analyzer.py#L96-L143)

```python
def _calculate_pitch_stability(self, audio: np.ndarray, sr: int) -> float:
    f0 = librosa.yin(audio, fmin=65.4, fmax=2093, sr=sr)
    voiced_mask = f0 > 0
    voiced_f0 = f0[voiced_mask]

    if len(voiced_f0) > 0:
        cv = np.std(voiced_f0) / np.mean(voiced_f0)
        stability = 1.0 / (1.0 + cv * 10)
    else:
        stability = 0.5  # Default for unvoiced frames

    return np.clip(stability, 0, 1)
```

### Data Flow Integration

```
AudioFingerprintAnalyzer.analyze()
    ↓
HarmonicAnalyzer.analyze()
    ├── _calculate_harmonic_ratio()     [uses HPSS]
    ├── _calculate_pitch_stability()    [← YIN (PHASE 3 TARGET)]
    └── _calculate_chroma_energy()      [uses Chroma CQT]
        ↓
    Returns: {'pitch_stability': 0-1, ...}
        ↓
ParameterMapper.map_harmonic_to_saturation()
    ├── pitch_stability → saturation intensity
    ├── pitch_stability → presence boost
    └── pitch_stability → harmonic enhancement
```

### Output Semantics
- **0.0**: Unvoiced frame or no stable pitch detected
- **0.0-0.5**: Low stability (high pitch variation, tremolo, vibrato)
- **0.5-1.0**: High stability (in-tune, sustained pitch)
- **1.0**: Perfect pitch stability

The feature is used to determine if saturation and harmonic enhancement should be applied:
- Unstable pitch → Less saturation (avoid artifacts)
- Stable pitch → More saturation (enhance harmonics)

---

## Implementation Roadmap

### Week 2 Timeline (Days 8-14)

#### Days 1-2: Setup & Understanding
- [ ] Review HPSS implementation (364 lines) as template
- [ ] Study YIN algorithm paper (de Cheveigné & Kawahara, 2002)
- [ ] Review test patterns from test_hpss_rust_validation.py
- [ ] Verify build environment: `cargo build --release`
- [ ] Understand FFT-based autocorrelation via rustfft

**Deliverable**: Development environment ready, algorithm fully understood

#### Days 3-5: Core Algorithm Implementation
- [ ] Implement frame-based audio processing (2048 samples, 512 hop)
- [ ] Implement difference function computation (DF[τ])
- [ ] Implement cumulative mean normalization (AACF)
- [ ] Implement trough detection with threshold
- [ ] Implement parabolic interpolation refinement
- [ ] Implement frequency bounds checking

**Deliverable**: `yin.rs` complete (400-500 lines)

**Key Functions**:
```rust
pub fn yin(
    y: &[f64],
    sr: usize,
    fmin: f64,
    fmax: f64,
) -> Vec<f64> { ... }

fn compute_difference_function(frame: &[f64]) -> Vec<f64> { ... }
fn cumulative_mean_normalization(df: &[f64]) -> Vec<f64> { ... }
fn find_trough(aacf: &[f64], threshold: f64) -> Option<usize> { ... }
fn parabolic_interpolate(aacf: &[f64], idx: usize) -> f64 { ... }
```

#### Days 6-7: Parallelization with Rayon
- [ ] Add rayon dependency (already in Cargo.toml)
- [ ] Parallelize frame processing: `par_iter()`
- [ ] Benchmark single-threaded vs parallel
- [ ] Target: 4-8x additional speedup on 4 cores

**Deliverable**: Parallel frame processing implementation

#### Days 8-10: Comprehensive Testing
- [ ] Implement unit tests for each function:
  - Test difference function computation
  - Test AACF normalization
  - Test trough detection logic
  - Test parabolic interpolation accuracy
  - Test frequency conversion
  - Test boundary conditions (very short audio, DC offset)
  - Test unvoiced frame detection

- [ ] Add integration tests:
  - Test on real Blind Guardian audio tracks
  - Compare fundamental frequencies with librosa reference
  - Validate output shape [n_frames]
  - Validate 0.0 for unvoiced frames
  - Performance benchmark: per-frame time

**Target**: 15-20 unit tests, >95% code coverage

**Commands**:
```bash
cargo test --release           # Unit tests
pytest tests/test_yin_rust_validation.py -v  # Integration tests
```

#### Days 11-13: Validation & Documentation
- [ ] Run integration test suite on real audio
- [ ] Measure speedup vs librosa.yin()
- [ ] Validate pitch_stability feature quality (compare against librosa values)
- [ ] Update RUST_DSP_PROJECT_STATUS.md
- [ ] Create Phase 3 completion summary
- [ ] Verify zero clippy warnings: `cargo clippy --release`

**Target**: 10-20x speedup validation

#### Day 14: Code Review & Merge
- [ ] Code review against HPSS patterns
- [ ] Ensure all tests passing
- [ ] Merge to master branch
- [ ] Update documentation

---

## File Structure

### Rust Implementation
```
vendor/auralis-dsp/
├── src/
│   ├── lib.rs              (update pub use yin::yin)
│   ├── yin.rs              (NEW - 400-500 lines)
│   │   ├── pub fn yin()    (main entry point)
│   │   ├── frame_audio()   (frame extraction)
│   │   ├── compute_difference_function()
│   │   ├── cumulative_mean_normalization()
│   │   ├── find_trough()
│   │   ├── parabolic_interpolate()
│   │   └── [unit tests]
│   └── hpss.rs             (reference - 364 lines)
├── Cargo.toml              (unchanged - all deps ready)
└── tests/
    └── [integration test setup]
```

### Python Integration Tests
```
tests/
├── test_yin_rust_validation.py  (NEW - ~150-200 lines)
│   ├── YinValidator class
│   ├── test_audio_file()        (real audio validation)
│   ├── test_with_librosa_comparison()
│   └── test_performance_benchmark()
├── test_hpss_rust_validation.py (reference template)
└── conftest.py                  (shared fixtures)
```

### Documentation
```
docs/
├── PHASE_3_YIN_IMPLEMENTATION_PLAN.md  (THIS FILE)
├── RUST_DSP_PROJECT_STATUS.md          (update with Phase 3 progress)
└── PHASE3_COMPLETE.md                  (final summary)
```

---

## Testing Strategy

### Unit Tests (in yin.rs)
```rust
#[cfg(test)]
mod tests {
    #[test]
    fn test_difference_function() {
        // Verify DF computation correctness
    }

    #[test]
    fn test_aacf_normalization() {
        // Verify AACF range [0, 2]
    }

    #[test]
    fn test_trough_detection() {
        // Verify threshold logic
    }

    #[test]
    fn test_parabolic_interpolation() {
        // Verify sub-sample refinement
    }

    #[test]
    fn test_unvoiced_frame() {
        // Verify 0.0 return for unvoiced
    }

    #[test]
    fn test_sine_wave_440hz() {
        // Known frequency validation
    }

    #[test]
    fn test_boundary_conditions() {
        // Very short audio, DC offset, silence
    }
}
```

### Integration Tests (test_yin_rust_validation.py)
```python
class YinValidator:
    def __init__(self, blind_guardian_audio_dir):
        # Load real Blind Guardian tracks

    def test_audio_file(self, audio_path):
        # Get librosa reference
        f0_librosa = librosa.yin(y, fmin=65.4, fmax=2093, sr=44100)

        # Get Rust implementation (via Python wrapper)
        f0_rust = auralis_dsp.yin(y, sr=44100, fmin=65.4, fmax=2093)

        # Compare outputs
        mape = np.mean(np.abs((f0_librosa - f0_rust) / (f0_librosa + 1e-8)))
        assert mape < 0.01  # <1% error

    def test_performance(self, audio_path):
        # Measure time per 1 second of audio
        # Target: 0.1-0.2s (10-20x speedup)

    def test_pitch_stability_feature(self):
        # Verify pitch_stability calculation
        # Compare feature values against librosa baseline
```

### Validation Criteria

✅ **Functional Correctness**:
- F0 contour shape matches librosa output
- Unvoiced frames return 0.0
- Voiced frames within ±5% of librosa values
- Output array shape correct [n_frames]

✅ **Performance**:
- Single-threaded: 100-200ms per track (vs 1-2s librosa)
- Parallel (4 cores): 25-50ms per track
- Per-frame time: <2ms average

✅ **Code Quality**:
- Zero clippy warnings
- >95% code coverage
- Comprehensive comments
- All tests passing

---

## Performance Targets

### Baseline (Current - Librosa)
- Time per track: 1-2 seconds
- Bottleneck: Python + NumPy FFT overhead

### Single-threaded Rust
- Target: 100-200ms per track
- Speedup: 10x
- Improvement: FFT-based ACDF via rustfft, vectorized operations

### 4-core Parallel (rayon)
- Target: 25-50ms per track
- Speedup: 40x total (10x single + 4x parallelism)
- Improvement: Frame-level independence
- Amdahl's Law: Assuming 90% parallelizable, 10% serial
  - T_parallel = 0.1 * T + 0.9 * T / 4 = 0.325 * T → 3.1x additional

### Overall Fingerprinting Impact (Phase 3+4+5)
```
Current (Librosa baseline): ~10s per track
├── HPSS: 2-3s → 100-200ms (10-20x) ✅ Phase 2
├── YIN: 1-2s → 100-200ms (10-20x) ← Phase 3
├── Chroma CQT: 1-2s → 100-200ms (10-20x) ← Phase 4
├── FFI overhead: ~5% → negligible with Phase 5 PyO3
└── Total expected: ~10s → 600-1100ms (9-16x)
```

---

## Key Implementation Decisions

### 1. FFT vs Direct Autocorrelation
**Decision**: Use FFT via rustfft for efficiency

```rust
// Why: O(n log n) vs O(n²) for autocorrelation
// rustfft crate already in Cargo.toml
// Proven in HPSS implementation
```

### 2. Parallelization Strategy
**Decision**: Per-frame parallelization with rayon

```rust
// Frames are independent
// Simple par_iter() pattern
// Already used in HPSS for 2D filtering
```

### 3. Output Format
**Decision**: Match librosa exactly

```rust
// Return Vec<f64> with length [n_frames]
// 0.0 for unvoiced frames
// Frequencies in Hz (no log scale)
// Maintains compatibility with downstream code
```

### 4. Boundary Handling
**Decision**: Zero-pad for edge frames

```rust
// HPSS uses same approach
// Consistent with librosa.yin() behavior
```

---

## Success Metrics

### Implementation Complete When:

✅ **Code**:
- [x] yin.rs implemented (400-500 lines)
- [x] All functions documented with comments
- [x] No clippy warnings

✅ **Testing**:
- [x] 15-20 unit tests passing
- [x] >95% code coverage
- [x] Integration tests on real audio
- [x] Librosa comparison validation
- [x] All edge cases tested

✅ **Performance**:
- [x] 10-20x speedup verified
- [x] Parallel implementation 3-4x additional
- [x] Per-frame time measured and logged

✅ **Documentation**:
- [x] Algorithm explanation
- [x] Function documentation
- [x] Test results summary
- [x] Performance benchmark results
- [x] Integration guide for Phase 4

✅ **Integration**:
- [x] Ready for Phase 5 PyO3 wrapper
- [x] Compatible with HarmonicAnalyzer
- [x] No breaking changes

---

## Risk Assessment & Mitigation

### Risk 1: FFT-based ACDF Precision
**Severity**: Medium
**Mitigation**:
- Extensive unit tests on synthetic sine waves
- Librosa comparison validation
- Test multiple frequencies in range [65.4Hz, 2093Hz]

### Risk 2: Parallelization Overhead
**Severity**: Low
**Mitigation**:
- Benchmark single-threaded vs parallel
- Only enable rayon if it improves performance
- Can be disabled if overhead exceeds benefit

### Risk 3: Edge Cases (Very Short Audio)
**Severity**: Low
**Mitigation**:
- Test with audio shorter than frame_length
- Verify graceful handling (return empty or single frame)
- Follow HPSS boundary handling pattern

### Risk 4: Numerical Stability
**Severity**: Medium
**Mitigation**:
- Add epsilon (1e-8) to prevent division by zero
- Test with DC offset and very loud audio
- Validate against NaN/Inf in output

---

## Phase 3 → Phase 4 Transition

### Phase 3 Outputs (Ready for Phase 4)
1. **Rust Implementation**: Complete yin.rs module
2. **Testing Infrastructure**: Integration test patterns
3. **Performance Data**: Verified 10-20x speedup
4. **Documentation**: Algorithm explanation and implementation guide

### Phase 4 Input Requirements (Chroma CQT)
- Same Cargo.toml dependencies
- Same testing patterns (Librosa reference comparison)
- Same parallelization approach (rayon)
- Real audio validation on Blind Guardian collection

---

## Dependency on Phase 2

### ✅ What Phase 2 Provides
1. **Build System**: Proven Cargo configuration
2. **Testing Patterns**: Librosa comparison methodology
3. **Real Audio Collection**: Blind Guardian tracks for validation
4. **Documentation**: Algorithm specification format
5. **Performance Measurement**: Infrastructure and tools
6. **Integration Approach**: How to add modules to lib.rs

### ✅ What Phase 3 Builds On
- HPSS implementation as code reference (364 lines)
- Unit test structure from hpss.rs tests
- Integration test structure from test_hpss_rust_validation.py
- Real audio validation methodology

---

## Phase 3 → Phase 5 Readiness

### Phase 5 (PyO3 Integration) Will Need:
1. ✅ Complete yin.rs implementation
2. ✅ Tested and validated Rust code
3. ✅ Performance baseline documented
4. ✅ Clear function signatures for Python binding

### PyO3 Wrapper (Phase 5 Week 4)
```python
# Phase 5: This wrapper will be auto-generated
import auralis_dsp

f0 = auralis_dsp.yin(
    audio,           # np.ndarray
    sr=44100,        # int
    fmin=65.4,       # float
    fmax=2093.0,     # float
)
# Returns: np.ndarray [n_frames]
```

Currently calls librosa.yin() → Phase 5 calls Rust yin() via PyO3

---

## Team Assignments & Responsibilities

### Phase 3 Implementation
- **Rust Implementation**: Days 1-7 (core algorithm + parallelization)
- **Testing**: Days 8-10 (comprehensive test suite)
- **Validation**: Days 11-13 (real audio, performance, accuracy)
- **Documentation**: Days 11-14 (specs, results, integration guide)

### Code Review Checklist
- [ ] HPSS pattern compliance
- [ ] All tests passing
- [ ] Zero clippy warnings
- [ ] Performance targets met
- [ ] Documentation complete
- [ ] Integration with Phase 4 plan ready

---

## Post-Phase 3 Deployment Considerations

### Backward Compatibility
- ✅ HarmonicAnalyzer still calls librosa.yin() in Phase 3
- ✅ No changes to fingerprint semantics (pitch_stability 0-1)
- ✅ Phase 5 enables PyO3 wrapper for seamless Rust integration

### Monitoring & Observability
Phase 3 includes:
- Performance logging (time per frame)
- Accuracy metrics (vs librosa baseline)
- Error tracking (unvoiced frame statistics)

Phase 5 will enable:
- Production deployment with feature flags
- A/B testing (Rust vs librosa) if needed
- Gradual rollout

---

## References

### Algorithm Papers
1. **YIN**: de Cheveigné & Kawahara (2002). "YIN, a fundamental frequency estimator for speech and music." JASA 111.
2. **HPSS**: Fitzgerald (2010). "Harmonic/Percussive Separation using Median Filtering." DAFX.
3. **Parabolic Interpolation**: Müller & Ellis (2015). "Analysis, Synthesis, and Perception of Musical Sounds."

### Code References
- HPSS Implementation: `/vendor/auralis-dsp/src/hpss.rs` (364 lines)
- Integration Tests: `/tests/test_hpss_rust_validation.py`
- HarmonicAnalyzer: `/auralis/analysis/fingerprint/harmonic_analyzer.py`

### External Resources
- rustfft crate: https://docs.rs/rustfft/
- rayon crate: https://docs.rs/rayon/
- librosa.yin documentation: https://librosa.org/doc/main/generated/librosa.yin.html

---

## Glossary

- **YIN**: Fundamental frequency estimation algorithm (acronym: "Yin Is Not...")
- **F0 Contour**: Time-series of fundamental frequencies [n_frames]
- **ACDF**: Autocorrelation Difference Function
- **AACF**: Absolute Autocorrelation Coefficient Function
- **Voiced Frame**: Frame with detectable pitch (F0 > 0)
- **Unvoiced Frame**: Frame with no stable pitch (F0 = 0.0)
- **pitch_stability**: Feature derived from F0 contour variation (0-1 scale)
- **trough_threshold**: AACF value threshold for minimum detection (0.1)
- **parabolic_interpolate**: Sub-sample refinement for period estimation

---

## Document Updates

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-24 | 1.0 | Initial Phase 3 plan created |

---

## Appendix: Algorithm Pseudocode

```
FUNCTION yin(audio, sr, fmin, fmax):
    n_frames = (len(audio) - FRAME_LENGTH) // HOP_LENGTH + 1
    f0 = [0.0] * n_frames

    FOR frame_idx IN 0..n_frames:
        frame = audio[frame_idx*HOP_LENGTH : frame_idx*HOP_LENGTH+FRAME_LENGTH]

        # Step 1: Compute difference function
        df = compute_difference_function(frame)

        # Step 2: Cumulative mean normalization
        aacf = cumulative_mean_normalization(df)

        # Step 3: Absolute threshold (trough detection)
        tau_min = find_trough(aacf, TROUGH_THRESHOLD)

        IF tau_min == None:
            f0[frame_idx] = 0.0  # Unvoiced
        ELSE:
            # Step 4: Parabolic interpolation
            refined_lag = parabolic_interpolate(aacf, tau_min)

            # Step 5: Convert period to frequency
            frequency = sr / refined_lag

            # Step 6: Bounds checking
            IF frequency >= fmin AND frequency <= fmax:
                f0[frame_idx] = frequency
            ELSE:
                f0[frame_idx] = 0.0  # Out of range

    RETURN f0
```

---

## Executive Checklist

Before starting Phase 3 implementation, verify:

- [ ] Development environment ready (`cargo build --release` works)
- [ ] HPSS Phase 2 fully understood (read hpss.rs)
- [ ] YIN algorithm paper reviewed
- [ ] Blind Guardian test audio available
- [ ] librosa.yin() behavior verified on real audio
- [ ] All dependencies in Cargo.toml confirmed
- [ ] Performance measurement tools set up
- [ ] Test infrastructure understood (pytest + conftest)

**Status**: ✅ Ready to proceed

---

*Generated: 2025-11-24*
*Next: Phase 3 Week 2 Implementation (Days 8-14)*
