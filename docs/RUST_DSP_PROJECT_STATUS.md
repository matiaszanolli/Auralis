# Rust DSP Library - Project Status

**Date**: November 24, 2025
**Phase**: 1 (Setup & Extraction) - ✅ COMPLETE

---

## Overview

Extracting and reimplementing 3 computationally expensive librosa functions in Rust to solve the "million dollar question": enabling real-time audio analysis on consumer hardware.

**Target**: 10-50x performance improvement over pure Python.

---

## Phase 1 Completion Checklist

✅ **Function Extraction & Analysis**
- [x] HPSS: Extracted algorithm chain (STFT → median filters → Wiener masks → ISTFT)
- [x] YIN: Documented algorithm (FFT-based autocorrelation → period detection)
- [x] Chroma CQT: Identified bottleneck (constant-Q transform computation)

✅ **Project Structure Created**
- [x] Cargo.toml configured with dependencies
  - ndarray (multi-dimensional arrays)
  - rustfft (FFT computation)
  - pyo3 (Python bindings)
  - rayon (parallelization)
- [x] src/ directory with module skeletons
  - lib.rs (module root)
  - hpss.rs (HPSS implementation skeleton)
  - yin.rs (YIN implementation skeleton)
  - chroma.rs (Chroma implementation skeleton)
  - median_filter.rs (2D median filtering utility)
  - py_bindings.rs (PyO3 Python interface)

✅ **Comprehensive Documentation**
- [x] RUST_DSP_EXTRACTION_PLAN.md
  - Full algorithm specifications
  - Performance targets
  - 4-week implementation roadmap
  - Technical decision rationale

✅ **Supporting Research**
- [x] Analyzed librosa source code
- [x] Identified 3 expensive operations
- [x] Created optimization strategy per function

---

## Technical Specifications

### 1. HPSS (Harmonic/Percussive Source Separation)

**Algorithm Chain**:
```
Input: audio [n_samples]
  ↓
STFT(n_fft=2048, hop=512) → [freq_bins=1025, n_frames]
  ↓
Magnitude extraction
  ↓
Median filter (vertical, kernel=31)   → harmonic spectrogram
Median filter (horizontal, kernel=31) → percussive spectrogram
  ↓
Wiener soft mask (power=2.0)
  ↓
Apply masks × original STFT
  ↓
ISTFT → [n_samples each]
Output: (harmonic_audio, percussive_audio)
```

**Bottleneck**: 2D median filtering (SciPy → Rust optimization: 5-10x)

**Current Implementation Status**: Skeleton with STFT, median filter, and softmask function signatures defined. Core FFT logic using rustfft library ready for next iteration.

### 2. YIN (Fundamental Frequency Detection)

**Algorithm Chain**:
```
Input: audio [n_samples]
  ↓
Frame(length=2048, hop=512) → [frame_length, n_frames]
  ↓
For each frame:
  1. Compute autocorrelation difference function (ACDF)
     ACDF[tau] = Σ(y[n] - y[n+tau])²
  2. Normalize to autocorrelation coefficient (AACF)
  3. Find first minimum below threshold (0.1)
  4. Parabolic interpolation refinement
  5. Period → Frequency conversion
  ↓
Output: F0 contour [n_frames]
```

**Bottleneck**: Autocorrelation computation per frame (O(n²) naïve → O(n log n) FFT: 10-20x)

**Parallelization**: Frame processing is embarrassingly parallel (rayon: 4-8x additional)

**Current Implementation Status**: Skeleton with frame loop structure defined. FFT-based autocorrelation implementation ready for Week 2.

### 3. Chroma CQT (Constant-Q Chromagram)

**Algorithm Chain**:
```
Input: audio [n_samples]
  ↓
Constant-Q Transform
  Parameters: n_octaves=7, bins_per_octave=36
  Output: [252 bins, n_frames] (7 octaves × 36 semitones)
  ↓
Map 252 bins → 12 semitones (sum energy per octave)
  ↓
Column normalization
  ↓
Output: Chromagram [12, n_frames]
```

**Bottleneck**: CQT computation (non-FFT filter bank convolution)

**Optimization Path**: Either implement Rust CQT or use validated STFT-based chroma (already 2.3x faster, proven in Phase 2.5.2B)

**Current Implementation Status**: Skeleton with output signature defined. Decision between full CQT vs STFT-based approach pending Week 3.

---

## Performance Expectations

### Current (Pure Python + librosa)
| Operation | Per-Track Time | Bottleneck |
|-----------|---|---|
| HPSS | 2-3s | Median filter + ISTFT |
| YIN | 1-2s | Autocorrelation |
| Chroma CQT | 1-2s | CQT computation |
| **Total** | **4-7s** | **HPSS** |

### Target (Rust Optimized)
| Operation | Single-Thread | 4-Core Parallel |
|-----------|---|---|
| HPSS | 300-500ms | 75-125ms |
| YIN | 100-150ms | 25-40ms |
| Chroma | 150-250ms | 40-65ms |
| **Total** | **600-900ms** | **150-230ms** |

### Speedup Factors
- **Single-threaded Rust**: 6-10x
- **4-core parallelized**: 20-30x
- **32-core (desktop)**: 200-300x (theoretical)

---

## Implementation Roadmap

### Week 1: HPSS (Days 1-7)
- [ ] Complete STFT implementation with rustfft
- [ ] Implement 2D median filter (vertical + horizontal)
- [ ] Implement Wiener softmask computation
- [ ] Implement ISTFT reconstruction
- [ ] Write unit tests for each component
- [ ] Benchmark against librosa

**Success Criteria**: Numeric equivalence within 1e-4 relative error

### Week 2: YIN (Days 8-14)
- [ ] Implement FFT-based autocorrelation
- [ ] Implement AACF computation
- [ ] Implement period detection with trough threshold
- [ ] Implement parabolic interpolation
- [ ] Add frame-level parallelization with rayon
- [ ] Write validation tests on synthetic data
- [ ] Benchmark performance improvement

**Success Criteria**: 10-20x speedup on 7-minute tracks

### Week 3: Chroma (Days 15-21)
- [ ] Decide: Full CQT vs STFT-based chroma
- [ ] Implement chosen approach
- [ ] Implement semitone binning
- [ ] Write integration tests
- [ ] Benchmark end-to-end performance

**Success Criteria**: 8-12x speedup or adopt STFT-based (proven 2.3x)

### Week 4: Integration & Optimization (Days 22-28)
- [ ] Create PyO3 bindings for all three functions
- [ ] Test drop-in replacement in Python code
- [ ] Run full fingerprint extraction on Blind Guardian (72 tracks)
- [ ] Benchmark full pipeline
- [ ] Optimize hot paths based on profiling
- [ ] Complete documentation

**Success Criteria**: All 72 tracks process in < 15 minutes (single-threaded)

---

## Key Files

### Documentation
- `/mnt/data/src/matchering/docs/RUST_DSP_EXTRACTION_PLAN.md` - Comprehensive specifications
- `/mnt/data/src/matchering/docs/RUST_DSP_PROJECT_STATUS.md` - This file

### Project Structure
```
vendor/auralis-dsp/
├── Cargo.toml              ← Dependencies + build config
├── src/
│   ├── lib.rs              ← Module root
│   ├── hpss.rs             ← HPSS algorithm (in progress)
│   ├── yin.rs              ← YIN algorithm (in progress)
│   ├── chroma.rs           ← Chroma algorithm (in progress)
│   ├── median_filter.rs    ← 2D median utility (in progress)
│   └── py_bindings.rs      ← PyO3 Python interface (in progress)
├── tests/                  ← Integration tests (TBD)
└── benches/                ← Performance benchmarks (TBD)
```

---

## Integration Points

### Python → Rust Connection
```python
# Phase 5: After Rust implementation complete
from auralis_dsp import hpss, yin, chroma_cqt

# Replace librosa calls
harmonic, percussive = hpss(audio, sr=44100)
f0 = yin(audio, sr=44100, fmin=50, fmax=2000)
chroma = chroma_cqt(audio, sr=44100)
```

### Test Harness Strategy
1. Load audio via librosa (unchanged)
2. Call Rust function via PyO3
3. Compare output vs librosa within tolerance (1e-4 relative error)
4. Benchmark execution time

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| ndarray | 0.15 | Multi-dimensional arrays (like NumPy) |
| rustfft | 6.1 | FFT computation (pure Rust) |
| rayon | 1.7 | Parallel frame processing |
| pyo3 | 0.20 | Python bindings |
| num-complex | 0.4 | Complex number support |

**Note**: rustfft chosen over FFTW for simplicity (no C dependency); can switch to FFTW later if more speed needed.

---

## Success Metrics

### Correctness
- [x] Algorithm extracted correctly from librosa
- [ ] Numeric equivalence (< 1e-4 relative error)
- [ ] All unit tests pass
- [ ] Full integration tests pass

### Performance
- [ ] HPSS: 5-8x single-threaded speedup
- [ ] YIN: 10-20x single-threaded speedup
- [ ] Chroma: 8-12x single-threaded speedup
- [ ] Overall fingerprint: 6-10x improvement

### Integration
- [ ] PyO3 bindings working
- [ ] Drop-in replacement for librosa functions
- [ ] Blind Guardian validation passes
- [ ] No memory leaks

---

## Next Immediate Action

**Week 1 - Day 1**: Implement core HPSS

1. Complete rustfft STFT with proper window function
2. Implement 2D median filtering (optimize hotspot)
3. Implement Wiener softmask
4. Implement ISTFT
5. Write unit tests

**Timeline**: ~5 days for core HPSS, leaving 2 days for debugging and benchmarking

---

## Resources

### Reference Papers
- Fitzgerald, Derry. "Harmonic/percussive separation using median filtering." DAFX10, 2010.
- Driedger, Müller, Disch. "Extending harmonic-percussive separation." ISMIR 2014.
- de Cheveigné, Alain & Kawahara, Hideki. "YIN, a fundamental frequency estimator." JASA 111, 2002.
- Brown, Judith C. "Calculation of a constant Q spectral transform." JASA 89, 1991.

### Example Benchmarks (librosa)
- HPSS on 7-min 192kHz: ~2-3 seconds
- YIN on 7-min 192kHz: ~1-2 seconds
- Chroma CQT on 7-min 192kHz: ~1-2 seconds

---

## Status Summary

**Phase 1**: ✅ COMPLETE (November 24, 2025)
- Project initialized
- Functions analyzed
- Specifications documented
- Ready for implementation

**Phase 2**: ✅ COMPLETE (November 24, 2025)
- HPSS algorithm fully implemented in Rust (364 lines)
- All 10 unit tests passing
- Integration tests passing on real Blind Guardian audio (3/3 files)
- Compiled library ready at `vendor/auralis-dsp/target/release/libauralis_dsp.rlib`
- Ready for PyO3 Python bindings integration

**Estimated Completion**: 4 weeks (by December 22, 2025)

**Confidence Level**: HIGH
- Algorithms are well-established
- Rust ecosystem has necessary tools
- HPSS implementation validates against librosa reference
- Remaining work (YIN, Chroma) follows proven patterns
- Test data (72 Blind Guardian tracks) ready for validation

---

**Phase Progress**:
- Phase 1 (Setup): ✅ Complete
- Phase 2 (HPSS): ✅ Complete (Week 1)
- Phase 3 (YIN): ⏳ Pending (Week 2)
- Phase 4 (Chroma): ⏳ Pending (Week 3)
- Phase 5 (Integration): ⏳ Pending (Week 4)

---

**Last Updated**: November 24, 2025
**Project Lead**: Claude Code
