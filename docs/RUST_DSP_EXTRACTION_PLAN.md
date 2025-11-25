# Rust DSP Library Extraction Plan

## Overview

Extract and reimplement 3 computationally expensive librosa functions in Rust for 10-50x performance improvement.

---

## Function 1: HPSS (Harmonic/Percussive Source Separation)

### Current Implementation Chain
```
librosa.effects.hpss(y)
  ↓
  STFT(y)  → Complex spectrogram [n_fft/2+1, n_frames]
  ↓
  decompose.hpss(spectrogram)  → Median filter + softmask
  ↓
  ISTFT(H_masked, P_masked)  → Time-domain waveforms
```

### Core Algorithm (librosa.decompose.hpss)

**Input**: Complex STFT spectrogram S [freq_bins, time_frames]

**Parameters**:
- `kernel_size`: (31, 31) typical - median filter width
  - harmonic kernel: vertical (frequency-wise)
  - percussive kernel: horizontal (time-wise)
- `power`: 2.0 (Wiener filter exponent)
- `margin`: (1.0, 1.0) (separation aggressiveness)

**Algorithm**:
1. Extract magnitude: `S_mag = |S|`
2. Apply median filters:
   - `H_filt = median_filter(S_mag, kernel=(1, win_harm))`  [harmonic]
   - `P_filt = median_filter(S_mag, kernel=(win_perc, 1))`  [percussive]
3. Compute soft masks using Wiener filtering:
   - `mask_H = softmask(H_filt, P_filt * margin_h, power=2.0)`
   - `mask_P = softmask(P_filt, H_filt * margin_p, power=2.0)`
4. Apply masks to original STFT:
   - `H = S * mask_H`
   - `P = S * mask_P`
5. Return H, P (inverse STFT handled by caller)

### Key Optimization Opportunities

1. **Median Filter**: scipy's median_filter is slow on 2D arrays
   - Rust implementation with proper 2D kernel handling
   - Streaming median can be optimized with order statistics

2. **Softmask**: Currently uses numpy operations
   ```python
   # Current (slow in Python)
   softmask = (M1 ** power) / (M1 ** power + (M2 * margin) ** power)
   ```
   - Vectorized Rust equivalent with SIMD

3. **Memory Layout**:
   - Column-major vs row-major considerations
   - In-place operations where possible

### Expected Speedup
- **Median filter**: 5-10x (SciPy → Rust)
- **Softmask**: 2-3x (NumPy → Rust SIMD)
- **Overall HPSS**: 5-8x

---

## Function 2: YIN (Fundamental Frequency Detection)

### Current Implementation
```
librosa.yin(y, fmin=freq_min, fmax=freq_max, sr=sample_rate)
  ↓
  Output: [n_frames] fundamental frequencies in Hz
```

### Core Algorithm (librosa.core.pitch.yin)

**Input**: Time-domain audio y [n_samples]

**Parameters**:
- `fmin`: 50 Hz (minimum frequency to detect)
- `fmax`: 2000 Hz (maximum frequency to detect)
- `sr`: 44100 Hz (sample rate)
- `frame_length`: 2048 (analysis window)
- `hop_length`: 512 (frame stride)
- `trough_threshold`: 0.1 (minimum allowed AACF value)

**Algorithm**:
1. Frame the audio: [frame_length, n_frames]
2. For each frame:
   a. Compute autocorrelation difference function (ADF):
      ```
      DF[tau] = Σ(y[n] - y[n+tau])²  for tau in range
      ```
   b. Normalize to autocorrelation coefficient (AACF):
      ```
      AACF[tau] = DF[tau] / (2 * Σ y[n]²)
      ```
   c. Find first minimum below `trough_threshold`
   d. Refine using parabolic interpolation
   e. Convert period → frequency

3. Return frequency array [n_frames]

### Key Bottlenecks

1. **Autocorrelation Computation**: O(n²) for each frame
   - Can use FFT-based autocorrelation: FFT → multiply → IFFT → O(n log n)
   - Rust can leverage FFTW or rustfft crates

2. **Frame Looping**: ~100+ frames per track
   - Each frame is independent → parallelizable with rayon

3. **Parabolic Interpolation**: Simple but repeated
   - Vectorizable

### Expected Speedup
- **Autocorrelation via FFT**: 5-10x per frame
- **Parallelization**: ~4-8x (4-8 cores per track)
- **Overall YIN**: 10-20x

### Challenge: Output Format
- librosa returns [n_frames] array with 0 for unvoiced frames
- Rust needs to maintain exact same output shape and semantics

---

## Function 3: CHROMA_CQT (Constant-Q Chroma)

### Current Implementation
```
librosa.feature.chroma_cqt(y, sr=sample_rate)
  ↓
  Output: Chromagram [12, n_frames]
```

### Algorithm Breakdown

1. **Constant-Q Transform** (librosa.cqt):
   - Time-frequency representation with logarithmic frequency spacing
   - Parameters: n_octaves=7, bins_per_octave=36
   - Creates [252, n_frames] time-frequency representation (7 octaves × 36 bins)

2. **Chroma Mapping** (reduce 252 bins → 12 semitones):
   - Sum energy across octaves for each semitone
   - Normalize by column

### The Bottleneck: CQT Computation

CQT is expensive:
- No FFT shortcut (unlike STFT)
- Uses custom filter bank convolution
- librosa.cqt uses `scipy.signal.convolve` internally

### Optimization Paths

**Option A: Replace with librosa.feature.chroma_stft** (already validated)
- 2.3x faster (proven by Phase 2.5.2B testing)
- STFT-based, can be parallelized

**Option B: Implement CQT in Rust**
- Use librosa's algorithm but optimized
- SIMD vectorization
- Memory-efficient filter bank

**Option C: Hybrid approach**
- Use STFT (fast) but apply better filtering
- Cherry-pick accuracy improvements from CQT

### Recommendation
**Use Option A in production** (proven 2.3x improvement), but implement Option B in Rust for completeness.

### Expected Speedup
- **Rust CQT**: 8-15x
- **Chroma mapping**: 2-3x
- **Overall chroma_cqt**: 8-12x

---

## Rust Implementation Roadmap

### Phase 1: Project Setup (1 day)

Create Rust library structure:
```
auralis-dsp/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── hpss.rs
│   ├── yin.rs
│   ├── chroma.rs
│   └── py_bindings.rs
├── tests/
│   ├── test_hpss.rs
│   ├── test_yin.rs
│   └── test_chroma.rs
└── benches/
    ├── bench_hpss.rs
    ├── bench_yin.rs
    └── bench_chroma.rs
```

**Dependencies**:
- `numpy`: NumPy FFI via ndarray
- `pyo3`: Python bindings
- `ndarray`: Multi-dimensional arrays (like NumPy)
- `num-complex`: Complex number support
- `rayon`: Data parallelism
- `rustfft` or `fftw`: FFT computation
- `scipy-median-filter-rs` (or custom implementation)

### Phase 2: HPSS Implementation (5-7 days)

**Goals**:
1. Implement 2D median filter (frequency-wise, time-wise)
2. Implement softmask Wiener filter
3. Create Python bindings via PyO3
4. Test against librosa output for numerical equivalence

**Key Files**:
- `src/hpss.rs`: Core algorithm
- `src/median_filter.rs`: Optimized 2D median
- `tests/test_hpss.rs`: Validation against librosa

**Testing Strategy**:
1. Unit tests for median filter (small arrays)
2. Integration test: Load real audio → compare HPSS output vs librosa
3. Benchmark: Time vs librosa

### Phase 3: YIN Implementation (5-7 days)

**Goals**:
1. Implement FFT-based autocorrelation
2. Implement AACF and period detection
3. Implement parabolic interpolation
4. Parallelized frame processing
5. Python bindings

**Key Files**:
- `src/yin.rs`: Core YIN algorithm
- `src/autocorrelation.rs`: FFT-based autocorr
- `tests/test_yin.rs`: Validation

**Testing Strategy**:
1. Synthetic test cases (sine waves with known pitch)
2. Real audio comparison vs librosa
3. Benchmark frame-by-frame

### Phase 4: Chroma Implementation (3-5 days)

**Goals**:
1. Implement CQT (or integrate with STFT-based chroma)
2. Implement semitone binning
3. Python bindings

**Or simpler**: Use validated chroma_stft wrapper (already 2.3x faster)

### Phase 5: PyO3 Integration & Testing (3-5 days)

**Goals**:
1. Create Python module `auralis_dsp`
2. Replace librosa calls in Python code
3. Run full test suite
4. Benchmark entire fingerprint pipeline

**Integration Points**:
```python
# Before (librosa)
harmonic, percussive = librosa.effects.hpss(audio)
f0 = librosa.yin(audio, fmin=50, fmax=2000, sr=sr)
chroma = librosa.feature.chroma_cqt(y=audio, sr=sr)

# After (Rust)
from auralis_dsp import hpss, yin, chroma_cqt
harmonic, percussive = hpss(audio)
f0 = yin(audio, fmin=50, fmax=2000, sr=sr)
chroma = chroma_cqt(y=audio, sr=sr)
```

---

## Technical Decisions

### FFT Library
- **rustfft**: Pure Rust, no dependencies, slower (~2-3x vs FFTW)
- **fftw-sys**: FFTW bindings, fast but binary dependency
- **ndarray-linalg**: Uses BLAS, compatible with existing code

**Recommendation**: Start with `rustfft`, switch to FFTW if speed insufficient.

### Array Representation
- **ndarray**: NumPy-like arrays, easy interop
- **nalgebra**: Linear algebra focus, excellent SIMD support
- **polars**: Columnar data, fast but overkill

**Recommendation**: `ndarray` for Phase 1, optimize later if needed.

### Parallelization
- **rayon**: Data parallelism, minimal code changes
- **tokio**: Async, more complex
- **standard threads**: Manual, most control

**Recommendation**: `rayon` for simplicity, good performance.

### Memory Layout
- Keep column-major (Fortran order) for compatibility with NumPy
- Rust arrays are row-major by default → transpose care needed
- Use `order='F'` in ndarray constructors

---

## Performance Targets

### Current (Pure Python)
| Operation | Time/Track | Bottleneck |
|-----------|-----------|-----------|
| HPSS | ~2-3s | Median filter + ISTFT |
| YIN | ~1-2s | Autocorrelation |
| Chroma | ~1-2s | CQT computation |
| **Total (3)** | **~4-7s** | **HPSS** |

### Target (Rust)
| Operation | Target | Speedup |
|-----------|--------|---------|
| HPSS | 300-500ms | 5-8x |
| YIN | 100-150ms | 10-15x |
| Chroma | 150-250ms | 8-10x |
| **Total (3)** | **~600-900ms** | **6-10x** |

### With Parallelization (4 cores)
| Operation | Target |
|-----------|--------|
| HPSS | 75-125ms |
| YIN | 25-40ms |
| Chroma | 40-65ms |
| **Total (3)** | **~150-230ms** |

---

## Success Criteria

1. ✅ Numerical equivalence: Rust output matches librosa within 1e-4 relative error
2. ✅ Speed: Achieve 6-10x overall speedup on full fingerprinting
3. ✅ Integration: Drop-in replacement for librosa calls
4. ✅ Testing: 100% test pass rate on Blind Guardian validation set
5. ✅ Memory: No memory leaks, efficient allocation

---

## Next Steps

1. **Week 1**: Project setup + HPSS implementation
2. **Week 2**: YIN implementation + parallelization
3. **Week 3**: Chroma implementation + integration testing
4. **Week 4**: Optimization + benchmarking + documentation

**Timeline**: 4 weeks to production-ready Rust DSP module

---

## References

### HPSS
- Fitzgerald, Derry. "Harmonic/percussive separation using median filtering." DAFX10, 2010.
- Driedger, Müller, Disch. "Extending harmonic-percussive separation." ISMIR 2014.

### YIN
- de Cheveigné, Alain & Kawahara, Hideki. "YIN, a fundamental frequency estimator for speech and music." JASA 111, 2002.

### Constant-Q
- Brown, Judith C. "Calculation of a constant Q spectral transform." JASA 89, 1991.
- Ellis, Daniel P. "Reproducing the sound of a spider in a bathtub." MIT thesis, 1996.

