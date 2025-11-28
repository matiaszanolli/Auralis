# Phase 7.3: Fingerprint Optimization - Planning Document

**Status**: 📋 PLANNING
**Target Performance**: 36.6x real-time (10 seconds audio in < 275ms)
**Estimated Scope**: 300-400 lines of optimization code
**Estimated Speedup**: 8-15x faster fingerprint calculations

---

## 🎯 Objectives

### Primary Goal
Optimize the fingerprint calculation pipeline to achieve **36.6x real-time performance** on the full 25-dimensional fingerprint extraction.

### Current Performance Baseline
- Full fingerprint extraction: ~500-800ms per 3-minute track
- Target: ~50-80ms per 3-minute track (36.6x speedup)
- Current bottleneck: VariationAnalyzer + SpectralAnalyzer + SampledHarmonicAnalyzer = 200-350ms of 500-800ms total

### Success Criteria
1. **Measured Speedup**: Achieve 8-15x speedup in identified bottleneck modules
2. **Backward Compatibility**: Zero breaking changes, identical output
3. **Code Quality**: Comprehensive benchmarks and regression tests
4. **Maintainability**: Clear refactoring with no premature abstraction

---

## 📊 Bottleneck Analysis

### Summary Table
| Bottleneck | Module | Current Cost | Target Cost | Speedup | Priority |
|-----------|--------|--------------|-------------|---------|----------|
| Peak detection (2 loops) | VariationAnalyzer | 10-30ms | 2-4ms | 5-8x | 🔴 CRITICAL |
| Spectral rolloff search | SpectralAnalyzer | 15-25ms | 3-5ms | 3-5x | 🔴 CRITICAL |
| Chunk analysis loop | SampledHarmonicAnalyzer | 100-300ms | 20-60ms | 4-6x | 🔴 CRITICAL |
| Band gain loops | ParameterMapper | 2-5ms | 1-2ms | 1.5-2x | 🟢 LOW |
| **TOTAL POTENTIAL** | **All Critical** | **127-360ms** | **26-71ms** | **5-14x** | - |

### Bottleneck Details

#### BOTTLENECK 1: VariationAnalyzer Peak Detection (10-30ms)
**Issue**: Two separate `for i in range(num_frames)` loops computing identical operation

```python
# Current: Loop 1 in _calculate_dynamic_range_variation
peaks = np.zeros(num_frames, dtype=audio.dtype)
for i in range(num_frames):
    start = i * hop_length
    end = min(start + frame_length, len(audio))
    if start < len(audio):
        peaks[i] = np.max(audio_abs[start:end])

# Current: Loop 2 in _calculate_peak_consistency
peaks = np.zeros(num_frames, dtype=audio.dtype)
for i in range(num_frames):  # IDENTICAL PATTERN
    start = i * hop_length
    end = min(start + frame_length, len(audio))
    if start < len(audio):
        peaks[i] = np.max(audio_abs[start:end])
```

**Solution**: Single vectorized method computing peaks once, reused by both calculations
- Replace two loops with NumPy stride tricks or `np.lib.stride_tricks.as_strided()`
- Or reshape+max for simpler implementation
- Estimated speedup: **5-8x** (frame-by-frame max → single vectorized operation)

**Implementation Strategy**:
1. Create `_get_frame_peaks()` method (vectorized)
2. Call once in `analyze()` method
3. Reuse result in both `_calculate_dynamic_range_variation()` and `_calculate_peak_consistency()`
4. Add regression tests (compare output before/after)

---

#### BOTTLENECK 2: SpectralAnalyzer Rolloff Search (15-25ms)
**Issue**: Per-frame `np.where()` search in list comprehension

```python
# Current: List comprehension with per-frame search
rolloff = np.array([
    freqs[np.where(cumsum[:, i] >= 0.85)[0][0]]  # <-- per-frame search
    if np.any(cumsum[:, i] >= 0.85)
    else freqs[-1]
    for i in range(magnitude.shape[1])  # Iterates frame count times
])
```

**Solution**: Vectorized `argmax` on boolean condition
- Use `np.argmax(cumsum >= 0.85, axis=0)` to find all rolloff frequencies in one operation
- Handle edge case: where cumsum never reaches 0.85 (map to last frequency)
- Estimated speedup: **3-5x** (per-frame search → single vectorized search)

**Implementation Strategy**:
1. Replace list comprehension with vectorized numpy operations
2. Add edge case handling for frames without rolloff
3. Validate output matches current implementation
4. Add performance benchmark test

---

#### BOTTLENECK 3: SampledHarmonicAnalyzer Chunk Loop (100-300ms)
**Issue**: Sequential `for` loop over independent chunks

```python
# Current: Sequential processing
for i, chunk in enumerate(chunks):
    hr = self._calculate_harmonic_ratio(chunk)
    ps = self._calculate_pitch_stability(chunk, sr)
    ce = self._calculate_chroma_energy(chunk, sr)

    chunk_results['harmonic_ratio'].append(hr)
    chunk_results['pitch_stability'].append(ps)
    chunk_results['chroma_energy'].append(ce)
```

**Solution**: ThreadPoolExecutor parallelization over chunks
- Each chunk is independent → perfect for parallelization
- Use 4-6 worker threads (typical system cores)
- Estimated speedup: **4-6x** (5-8 chunks processed in parallel)

**Implementation Strategy**:
1. Extract chunk analysis into `_analyze_chunk(chunk, sr)` method
2. Use `ThreadPoolExecutor(max_workers=4)` to process chunks in parallel
3. Aggregate results in same format as before
4. Add thread-safety validation tests
5. Benchmark speedup with various chunk counts

---

#### BOTTLENECK 4: ParameterMapper Band Loops (2-5ms)
**Issue**: Multiple small `for` loops assigning constant values

```python
# Current: Multiple small loops
if centroid > 3000:
    for i in range(20, 24):
        spectral_gains[i] = -2.0

if energy_ratio > 0.6:
    for i in range(0, 4):
        bass_gains[i] = 1.5
```

**Solution**: Dict/array comprehensions or direct slicing
- Convert to dict comprehensions or numpy array slicing
- Minimal absolute impact but improves code clarity
- Estimated speedup: **1.5-2x** (only 10-50 bands total)

**Implementation Strategy**:
1. Convert small loops to comprehensions or slicing
2. Use numpy array slicing where appropriate
3. Benchmark to confirm improvement
4. Focus on code clarity over performance (absolute impact < 5ms)

---

## 🏗️ Implementation Plan

### Phase 7.3a: Vectorize Peak Detection (Highest Impact)
**File**: `auralis/analysis/fingerprint/variation_analyzer.py`
**Lines Changed**: 30-40 lines (replace 2 identical loops with 1 vectorized method)
**Speedup Target**: 5-8x (10-30ms → 2-4ms)

```python
def _get_frame_peaks(self, audio: np.ndarray, hop_length: int, frame_length: int) -> np.ndarray:
    """
    Vectorized frame peak detection.

    Computes maximum absolute value for each frame in single pass.
    Replaces two separate loops in _calculate_dynamic_range_variation
    and _calculate_peak_consistency.

    Args:
        audio: Input audio signal
        hop_length: Hop size between frames
        frame_length: Frame window length

    Returns:
        Array of peak values for each frame (shape: (num_frames,))
    """
    audio_abs = np.abs(audio)
    num_frames = (len(audio) - frame_length) // hop_length + 1

    # Option 1: NumPy stride tricks (most efficient)
    # from numpy.lib.stride_tricks import as_strided
    # shape = (num_frames, frame_length)
    # strides = (audio_abs.strides[0] * hop_length, audio_abs.strides[0])
    # frames = as_strided(audio_abs, shape=shape, strides=strides)
    # peaks = np.max(frames, axis=1)

    # Option 2: Reshape + max (simpler, slightly slower)
    # Pad audio to exact frame boundaries
    padded_len = (num_frames - 1) * hop_length + frame_length
    padded = np.zeros(padded_len)
    padded[:len(audio_abs)] = audio_abs

    # Reshape into frames
    frames = padded[:num_frames * hop_length].reshape(num_frames, -1)[:, :frame_length]
    peaks = np.max(frames, axis=1)

    return peaks
```

**Changes Required**:
1. Add `_get_frame_peaks()` method
2. Call in `analyze()` method: `self.frame_peaks = self._get_frame_peaks(...)`
3. Refactor `_calculate_dynamic_range_variation()`: replace loop with `self.frame_peaks`
4. Refactor `_calculate_peak_consistency()`: replace loop with `self.frame_peaks`
5. Add regression tests

**Testing Strategy**:
- Compare output of vectorized method with original loop-based implementation
- Test edge cases: short audio, exact frame boundaries, odd frame counts
- Benchmark: measure speedup on 3-minute track

---

### Phase 7.3b: Vectorize Spectral Rolloff (High Impact)
**File**: `auralis/analysis/fingerprint/spectral_analyzer.py`
**Lines Changed**: 15-20 lines (replace list comprehension with vectorized numpy)
**Speedup Target**: 3-5x (15-25ms → 3-5ms)

```python
def _calculate_spectral_rolloff(self, magnitude: np.ndarray, freqs: np.ndarray) -> float:
    """
    Vectorized spectral rolloff calculation.

    Replaces per-frame np.where() search with single vectorized argmax.

    Args:
        magnitude: STFT magnitude (freq_bins x frames)
        freqs: Frequency array

    Returns:
        Mean spectral rolloff across all frames
    """
    # Normalize per frame
    mag_sum = np.sum(magnitude, axis=0, keepdims=True)
    mag_norm = magnitude / np.maximum(mag_sum, 1e-10)
    cumsum = np.cumsum(mag_norm, axis=0)

    # Vectorized: find first row where cumsum >= 0.85 for each frame
    # argmax returns first True index on boolean array
    rolloff_indices = np.argmax(cumsum >= 0.85, axis=0)

    # Edge case: frames where cumsum never reaches 0.85
    # argmax returns 0 for all-False array, so we need special handling
    never_reached = np.all(cumsum < 0.85, axis=0)
    rolloff_indices[never_reached] = len(freqs) - 1

    # Map indices to frequencies
    rolloff_values = freqs[np.clip(rolloff_indices, 0, len(freqs) - 1)]

    return np.mean(rolloff_values)
```

**Changes Required**:
1. Replace list comprehension in `_calculate_spectral_rolloff()`
2. Use `np.argmax(cumsum >= 0.85, axis=0)` for vectorization
3. Handle edge case: frames never reaching 0.85 threshold
4. Update docstring with vectorization note
5. Add regression tests

**Testing Strategy**:
- Verify output identical to original per-frame search
- Test edge cases: low energy frames, all-high frames, mixed
- Benchmark on various STFT sizes

---

### Phase 7.3c: Parallelize Chunk Analysis (Highest Total Impact)
**File**: `auralis/analysis/fingerprint/harmonic_analyzer_sampled.py`
**Lines Changed**: 20-30 lines (replace loop with ThreadPoolExecutor)
**Speedup Target**: 4-6x (100-300ms → 20-60ms)

```python
from concurrent.futures import ThreadPoolExecutor

def _analyze_impl(self, audio: np.ndarray, sr: int) -> dict:
    """
    Analyze harmonic properties with parallel chunk processing.

    Chunks are independent, so we parallelize across 4 worker threads.
    Estimated speedup: 4-6x for 5-8 chunks.
    """
    chunks, start_times = self._extract_chunks(audio, sr)

    # Process chunks in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(self._analyze_chunk, chunk, sr)
            for chunk in chunks
        ]
        results = [f.result() for f in futures]

    # Aggregate: average across chunks
    if not results:
        return {
            'harmonic_ratio': 0.5,
            'pitch_stability': 0.5,
            'chroma_energy': 0.0
        }

    hr_values = [r[0] for r in results]
    ps_values = [r[1] for r in results]
    ce_values = [r[2] for r in results]

    return {
        'harmonic_ratio': float(np.mean(hr_values)),
        'pitch_stability': float(np.mean(ps_values)),
        'chroma_energy': float(np.mean(ce_values))
    }

def _analyze_chunk(self, chunk: np.ndarray, sr: int) -> tuple:
    """
    Analyze single chunk (called in parallel).

    Returns:
        (harmonic_ratio, pitch_stability, chroma_energy)
    """
    hr = self._calculate_harmonic_ratio(chunk)
    ps = self._calculate_pitch_stability(chunk, sr)
    ce = self._calculate_chroma_energy(chunk, sr)
    return (hr, ps, ce)
```

**Changes Required**:
1. Import `ThreadPoolExecutor` from `concurrent.futures`
2. Extract `_analyze_chunk()` method from loop body
3. Replace sequential `for` loop with `ThreadPoolExecutor.submit()`
4. Aggregate results in same format as before
5. Add thread-safety tests
6. Benchmark with various worker counts

**Testing Strategy**:
- Verify output identical to sequential implementation
- Test thread safety with concurrent chunk processing
- Benchmark: 4 vs 6 vs 8 worker threads
- Test with various track lengths (different chunk counts)

---

### Phase 7.3d: Vectorize Band Assignments (Low Priority)
**File**: `auralis/analysis/fingerprint/parameter_mapper.py` (and `common_metrics.py`)
**Lines Changed**: 10-15 lines (replace loops with comprehensions)
**Speedup Target**: 1.5-2x (2-5ms → 1-2ms)

```python
# Before: Multiple small loops
if centroid > 3000:
    for i in range(20, 24):
        spectral_gains[i] = -2.0

# After: Dict comprehension
if centroid > 3000:
    spectral_gains.update({i: -2.0 for i in range(20, 24)})

# Or with NumPy arrays:
if centroid > 3000:
    spectral_gains[20:24] = -2.0
```

**Changes Required**:
1. Convert small loops to comprehensions
2. Use numpy array slicing where applicable
3. Add comments for clarity
4. No behavioral changes expected

---

## 📈 Benchmarking Strategy

### Benchmark Test Suite
**File**: `tests/test_phase_7_3_fingerprint_optimization.py` (New)

#### Test 1: Peak Detection Vectorization
```python
def test_peak_detection_speedup():
    """Verify vectorized peak detection achieves 5-8x speedup"""
    audio = np.random.randn(441000)  # 10 seconds at 44.1kHz

    # Time original loop-based method
    time_loop = measure_time(original_peak_detection, audio)

    # Time vectorized method
    time_vec = measure_time(vectorized_peak_detection, audio)

    speedup = time_loop / time_vec
    assert speedup > 5.0, f"Expected 5-8x speedup, got {speedup:.1f}x"
```

#### Test 2: Spectral Rolloff Vectorization
```python
def test_rolloff_speedup():
    """Verify vectorized rolloff achieves 3-5x speedup"""
    # Similar benchmark for spectral rolloff
```

#### Test 3: Chunk Parallelization
```python
def test_chunk_parallelization_speedup():
    """Verify parallel chunk processing achieves 4-6x speedup"""
    audio = np.random.randn(441000 * 3)  # 30 seconds

    # Time sequential processing
    time_seq = measure_time(sequential_chunk_analysis, audio)

    # Time parallel processing
    time_par = measure_time(parallel_chunk_analysis, audio)

    speedup = time_seq / time_par
    assert speedup > 4.0, f"Expected 4-6x speedup, got {speedup:.1f}x"
```

#### Test 4: Regression Tests
```python
def test_optimization_output_identical():
    """Verify optimized code produces identical output"""
    audio = np.random.randn(441000)

    output_original = fingerprint_original(audio)
    output_optimized = fingerprint_optimized(audio)

    # Compare all 25 dimensions
    assert np.allclose(output_original, output_optimized, rtol=1e-6)
```

### Performance Targets
| Metric | Target | Current | Improvement |
|--------|--------|---------|-------------|
| Peak detection (10s audio) | 2-4ms | 10-30ms | 5-8x |
| Spectral rolloff (10s audio) | 3-5ms | 15-25ms | 3-5x |
| Chunk analysis (30s audio) | 20-60ms | 100-300ms | 4-6x |
| Full fingerprint (3min track) | 50-80ms | 500-800ms | 8-12x |

---

## 🧪 Testing & Validation

### Regression Test Suite
- Compare output before/after optimization
- Verify all 25 fingerprint dimensions match
- Test on 10+ diverse audio files (speech, music, silence, etc.)

### Benchmark Suite
- Measure speedup on 10-second clips
- Measure speedup on 3-minute tracks
- Compare worker counts (4, 6, 8 threads) for parallelization
- Profile to ensure no new bottlenecks introduced

### Edge Case Testing
- Short audio (< 1 second)
- Very high energy (peaks near clipping)
- Silent sections
- Very low energy signals
- Mixed dynamics (speech + music)

---

## 📋 Implementation Checklist

### Phase 7.3a: Peak Detection
- [ ] Create `_get_frame_peaks()` method with vectorization
- [ ] Refactor `_calculate_dynamic_range_variation()` to use vectorized peaks
- [ ] Refactor `_calculate_peak_consistency()` to use vectorized peaks
- [ ] Add regression tests (output comparison)
- [ ] Add benchmark tests (speedup verification)
- [ ] Profile and validate 5-8x speedup claim
- [ ] Update docstrings

### Phase 7.3b: Spectral Rolloff
- [ ] Replace list comprehension with vectorized `argmax`
- [ ] Handle edge case: frames never reaching 0.85
- [ ] Add regression tests
- [ ] Add benchmark tests
- [ ] Profile and validate 3-5x speedup claim

### Phase 7.3c: Chunk Parallelization
- [ ] Extract `_analyze_chunk()` method
- [ ] Implement ThreadPoolExecutor pattern
- [ ] Add thread-safety tests
- [ ] Add benchmark tests (4/6/8 worker threads)
- [ ] Profile and validate 4-6x speedup claim

### Phase 7.3d: Band Loops (If Time)
- [ ] Convert small loops to comprehensions
- [ ] Update docstrings
- [ ] Benchmark to confirm improvement

### Testing & Documentation
- [ ] Create comprehensive benchmark suite
- [ ] Run regression tests on 10+ audio files
- [ ] Measure full fingerprint speedup
- [ ] Document findings in completion report
- [ ] Commit all changes with detailed messages

---

## ⚠️ Risk Assessment

### Low Risk
- **Vectorization (Peak Detection, Rolloff)**: Well-understood numpy operations, extensive regression testing
- **Parallelization (Chunks)**: Independent chunk processing, no shared state
- **Band Loops**: Minimal impact, easy to revert if needed

### Mitigation Strategies
1. **Comprehensive Regression Tests**: All optimizations must produce identical output
2. **Incremental Implementation**: Implement and test one optimization at a time
3. **Performance Benchmarking**: Measure actual speedup before considering complete
4. **Edge Case Testing**: Test short audio, high/low energy, silence, etc.

---

## 🎯 Success Criteria

1. ✅ **Peak Detection**: 5-8x speedup verified with benchmarks
2. ✅ **Spectral Rolloff**: 3-5x speedup verified with benchmarks
3. ✅ **Chunk Parallelization**: 4-6x speedup verified with benchmarks
4. ✅ **Regression Tests**: 100% output match with original implementation
5. ✅ **Full Pipeline**: 8-12x total speedup on 3-minute fingerprint extraction
6. ✅ **Code Quality**: Zero breaking changes, comprehensive docstrings, type hints
7. ✅ **Documentation**: Complete Phase 7.3 completion report

---

## 📅 Timeline (Estimated)

- **Phase 7.3a (Peak Detection)**: 1-2 hours (30-40 lines, high impact)
- **Phase 7.3b (Spectral Rolloff)**: 1-2 hours (15-20 lines, medium impact)
- **Phase 7.3c (Chunk Parallelization)**: 1.5-2 hours (20-30 lines, highest impact)
- **Phase 7.3d (Band Loops)**: 0.5-1 hour (10-15 lines, low impact)
- **Testing & Benchmarking**: 1.5-2 hours (comprehensive test suite)
- **Documentation**: 1-1.5 hours (completion report)

**Total Estimated**: 7-10 hours to complete all optimizations

---

## 🚀 Next Steps After Phase 7.3

### Phase 7.4: Real-time Metrics (Future)
- Streaming metric calculation for live audio
- Incremental updates for fast-moving metrics
- Window-based stability calculations

### Phase 7.5: Metric Caching (Future)
- Cache frequently computed metrics
- Deterministic metric computation with cache validation
- Integration with library query caching system

### Phase 8: Performance Profiling & Analysis
- End-to-end performance benchmarking
- Identify remaining bottlenecks
- Profile with cProfile and memory_profiler

---

**Plan Created**: 2024-11-28
**Status**: 📋 Ready for Implementation
**Next Step**: Begin Phase 7.3a - Vectorize Peak Detection
