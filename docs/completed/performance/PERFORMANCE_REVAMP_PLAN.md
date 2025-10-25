# Auralis Performance Revamp Plan

**Date**: October 24, 2025
**Current Status**: Single-threaded processing using 1-2 of 32 CPU threads
**Goal**: Multi-threaded/multi-process audio processing pipeline achieving 4-8x performance improvement

## Performance Analysis

### Current Architecture Bottlenecks

1. **Sequential Processing Chain** (hybrid_processor.py:204-569)
   - Content analysis → EQ → Dynamics → Stereo → Normalization runs sequentially
   - Processing stages: ~975 lines, all single-threaded

2. **FFT-Heavy Operations**
   - Spectrum analysis (spectrum_analyzer.py): 64 frequency bands with overlapping windows
   - Psychoacoustic EQ (psychoacoustic_eq.py): 26 critical bands with masking calculations
   - Content analysis (content_analyzer.py): Multiple spectral feature extractions

3. **Chunked Processing Loops**
   - Psychoacoustic EQ: 50% overlap chunking (hybrid_processor.py:688-710)
   - Spectrum analysis: 75% overlap by default (spectrum_analyzer.py:215-232)
   - All loops run sequentially

4. **Existing Optimization System**
   - Thread pool exists but underutilized (performance_optimizer.py:312-361)
   - Memory pool available but not used in critical paths
   - SIMD accelerator defined but limited adoption
   - Caching system exists but not applied to computation-heavy operations

### Performance Targets

| Component | Current | Target | Strategy |
|-----------|---------|--------|----------|
| Content Analysis | ~50ms | ~12ms | Parallel feature extraction |
| Psychoacoustic EQ | ~120ms | ~30ms | Parallel band processing + vectorization |
| Dynamics Processing | ~40ms | ~10ms | SIMD vectorization + parallel envelope |
| Spectrum Analysis | ~60ms | ~15ms | Parallel FFT windows |
| **Total Pipeline** | **~270ms** | **~70ms** | **~4x speedup** |
| **Batch Processing (10 tracks)** | **~2.7s** | **~400ms** | **~7x with multiprocessing** |

## Optimization Strategy

### Phase 1: Parallel FFT and Spectrum Analysis

**Target Files:**
- `auralis/analysis/spectrum_analyzer.py`
- `auralis/core/analysis/content_analyzer.py`
- `auralis/dsp/eq/psychoacoustic_eq.py`

**Changes:**

1. **Parallel Window Processing**
   ```python
   # Before: Sequential chunking
   for i in range(0, len(audio), chunk_size // 2):
       chunk = audio[i:end_idx]
       result = process_chunk(chunk)

   # After: Parallel processing with ProcessPoolExecutor
   with ProcessPoolExecutor(max_workers=8) as executor:
       chunks = [audio[i:i+chunk_size] for i in range(0, len(audio), chunk_size//2)]
       results = executor.map(process_chunk, chunks)
   ```

2. **Vectorized Band Energy Calculation**
   ```python
   # Before: Loop through bands
   for i, band in enumerate(bands):
       band_energies[i] = calculate_energy(spectrum, band)

   # After: NumPy vectorized operations
   band_energies = np.array([
       np.mean(spectrum[band_masks[i]]) for i in range(len(bands))
   ])
   ```

3. **Cached FFT Plans**
   - Pre-compute FFT plans for common sizes (512, 1024, 2048, 4096)
   - Store in performance optimizer cache
   - Reduces FFT setup overhead by ~30%

### Phase 2: Parallel Band Processing (EQ)

**Target Files:**
- `auralis/dsp/eq/psychoacoustic_eq.py`
- `auralis/dsp/eq/filters.py`

**Changes:**

1. **Multi-threaded Critical Band Processing**
   ```python
   # Process 26 critical bands in parallel
   with ThreadPoolExecutor(max_workers=8) as executor:
       futures = [
           executor.submit(process_band, audio, band, gain)
           for band, gain in zip(critical_bands, gains)
       ]
       band_results = [f.result() for f in futures]
       result = np.sum(band_results, axis=0)
   ```

2. **SIMD-Optimized Filter Application**
   - Use NumPy's optimized linear algebra operations
   - Pre-compute filter coefficients in batch
   - Apply filters using matrix operations instead of loops

3. **Band Processing Batching**
   - Group similar bands (bass: 0-4, mid: 5-15, treble: 16-25)
   - Process groups in parallel
   - Reduces thread overhead while maintaining parallelism

### Phase 3: Vectorized Dynamics Processing

**Target Files:**
- `auralis/dsp/dynamics/compressor.py`
- `auralis/dsp/dynamics/limiter.py`
- `auralis/dsp/advanced_dynamics.py`

**Changes:**

1. **Vectorized Envelope Following**
   ```python
   # Before: Sample-by-sample processing
   for i in range(len(audio)):
       envelope[i] = max(abs(audio[i]), envelope[i-1] * release_coeff)

   # After: NumPy vectorized with cummax
   abs_audio = np.abs(audio)
   envelope = np.maximum.accumulate(
       abs_audio * attack_coeff + envelope_prev * (1 - attack_coeff)
   )
   ```

2. **Parallel Stereo Channel Processing**
   - Process L/R channels simultaneously using multiprocessing
   - Especially beneficial for dynamics with lookahead buffers

3. **SIMD Gain Calculation**
   - Leverage existing SIMDAccelerator.vectorized_gain_apply
   - Batch gain calculations for entire chunks

### Phase 4: Multiprocessing for Batch Operations

**Target Files:**
- `auralis/core/hybrid_processor.py` (new batch processing methods)
- `auralis-web/backend/processing_engine.py`

**Changes:**

1. **Track-Level Parallelism**
   ```python
   # New batch processing method
   def process_batch(self, audio_files: List[str], max_workers: int = 8):
       with ProcessPoolExecutor(max_workers=max_workers) as executor:
           results = executor.map(self.process, audio_files)
       return list(results)
   ```

2. **Shared Memory for Audio Buffers**
   - Use multiprocessing.shared_memory for large audio arrays
   - Reduces IPC overhead by ~60%

3. **Worker Process Pool**
   - Pre-spawn worker processes at application startup
   - Reuse processes for multiple tracks
   - Eliminates process creation overhead

### Phase 5: NumPy Optimization and Vectorization

**Target Files:**
- `auralis/dsp/basic.py`
- `auralis/dsp/unified.py`
- `auralis/dsp/utils/*.py`

**Changes:**

1. **Eliminate Python Loops**
   ```python
   # Before: Python loop for windowed RMS
   for i in range(0, len(audio) - window, hop):
       rms_values.append(calculate_rms(audio[i:i+window]))

   # After: NumPy strided array view
   from numpy.lib.stride_tricks import sliding_window_view
   windows = sliding_window_view(audio, window)[::hop]
   rms_values = np.sqrt(np.mean(windows**2, axis=1))
   ```

2. **Broadcasting Instead of Tile/Repeat**
   - Replace np.tile/np.repeat with broadcasting where possible
   - Reduces memory allocations by ~40%

3. **In-place Operations**
   - Use out= parameter in NumPy operations where safe
   - Reduces memory churn significantly

### Phase 6: Intelligent Caching and Memory Management

**Target Files:**
- `auralis/optimization/performance_optimizer.py`
- `auralis/core/hybrid_processor.py`

**Changes:**

1. **Content Profile Caching**
   ```python
   @cached
   def analyze_content(self, audio: np.ndarray):
       # Hash audio fingerprint (first/middle/last 1024 samples)
       fingerprint = hash((audio[:1024], audio[len(audio)//2:len(audio)//2+1024], audio[-1024:]))
       # Cache based on fingerprint
   ```

2. **EQ Curve Caching**
   - Cache computed EQ curves per genre + intensity combination
   - Reduces psychoacoustic calculations by ~70% for similar content

3. **Memory Pool for Audio Buffers**
   - Leverage existing MemoryPool for all audio processing
   - Pre-allocate common buffer sizes (44100, 88200, 176400 samples)

## Implementation Plan

### Week 1: Foundation (Days 1-2)

**Day 1: Parallel FFT Infrastructure**
- [ ] Implement parallel window processing in SpectrumAnalyzer
- [ ] Add FFT plan caching to PerformanceOptimizer
- [ ] Create parallel_fft_windows() helper function
- [ ] Write unit tests for parallel spectrum analysis

**Day 2: Parallel Band Processing**
- [ ] Refactor PsychoacousticEQ to use ParallelProcessor
- [ ] Implement parallel_band_processing() for 26 critical bands
- [ ] Add band grouping optimization
- [ ] Benchmark EQ processing speed

### Week 2: Core Processing Optimization (Days 3-5)

**Day 3: Vectorized Dynamics**
- [ ] Rewrite EnvelopeFollower with vectorized operations
- [ ] Optimize AdaptiveCompressor gain calculation
- [ ] Add SIMD acceleration to limiter
- [ ] Test dynamics processing accuracy

**Day 4: Content Analysis Parallelization**
- [ ] Parallelize spectral feature extraction in ContentAnalyzer
- [ ] Add caching for genre classification
- [ ] Optimize ML feature extraction
- [ ] Validate analysis accuracy

**Day 5: Integration**
- [ ] Update HybridProcessor to use parallel components
- [ ] Add configuration options for parallelism level
- [ ] Implement graceful fallback for single-threaded environments
- [ ] Create performance profiling decorators

### Week 3: Batch Processing & Testing (Days 6-7)

**Day 6: Batch Processing**
- [ ] Implement process_batch() with multiprocessing
- [ ] Add shared memory support for audio buffers
- [ ] Create worker process pool
- [ ] Test batch processing with 10+ tracks

**Day 7: Benchmarking & Validation**
- [ ] Create comprehensive benchmark suite
- [ ] Test on various audio types (classical, rock, electronic, etc.)
- [ ] Validate audio quality (SNR, frequency response, artifacts)
- [ ] Generate performance comparison report

## Expected Results

### Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Single track processing | 270ms | 70ms | **3.9x faster** |
| Batch 10 tracks | 2.7s | 400ms | **6.8x faster** |
| CPU utilization | 3-6% (1-2 cores) | 25-50% (8-16 cores) | **8x better utilization** |
| Memory usage | 150MB peak | 200MB peak | +33% (acceptable) |
| Throughput | 3.7 tracks/sec | 25 tracks/sec | **6.8x higher** |

### Quality Assurance

- Audio quality validation: SNR > 90dB, THD < 0.01%
- Bit-perfect accuracy tests for deterministic operations
- Regression tests against current single-threaded implementation
- A/B listening tests for subjective quality

## Configuration

### New Config Options (UnifiedConfig)

```python
class ParallelProcessingConfig:
    enable_parallel: bool = True
    max_workers: int = min(8, cpu_count())
    use_multiprocessing: bool = True  # False = threading only
    chunk_processing_threshold: int = 44100  # Min samples for parallel
    band_grouping: bool = True  # Group similar bands

    # Memory optimization
    use_memory_pool: bool = True
    shared_memory_threshold_mb: int = 10  # Use shared mem for large arrays

    # Caching
    cache_content_analysis: bool = True
    cache_eq_curves: bool = True
    cache_fft_plans: bool = True
```

### Backward Compatibility

- All optimizations are opt-in via config
- Default behavior preserves existing single-threaded processing
- Graceful degradation on systems with limited cores (<4)

## Monitoring and Profiling

### Performance Metrics to Track

1. **Processing Time Breakdown**
   - Content analysis time
   - EQ processing time
   - Dynamics processing time
   - Total pipeline time

2. **Resource Utilization**
   - CPU usage per core
   - Memory footprint
   - Cache hit rates
   - Thread pool efficiency

3. **Quality Metrics**
   - SNR before/after
   - Frequency response accuracy
   - Dynamic range preservation
   - Artifact detection

### Profiling Tools

- Built-in PerformanceProfiler for timing
- cProfile for hotspot identification
- memory_profiler for memory analysis
- py-spy for live flame graphs

## Risk Mitigation

### Potential Issues

1. **Race Conditions**: Ensure thread-safe operations in shared state
2. **Memory Overhead**: Monitor memory usage with large batches
3. **Audio Artifacts**: Validate chunk boundary handling in parallel processing
4. **Platform Compatibility**: Test on Linux, macOS, Windows

### Fallback Strategy

- All parallel code has single-threaded fallback
- Automatic detection of available resources
- Configuration validation at startup
- Error handling with graceful degradation

## Success Criteria

✅ **Primary Goals**:
- 4x single-track processing speedup
- 6x batch processing speedup
- 8+ core utilization on 32-core system
- Zero audio quality degradation

✅ **Secondary Goals**:
- 70% cache hit rate for similar content
- <5% memory overhead increase
- Compatible with existing API
- Comprehensive performance monitoring

## Next Steps

1. **Immediate**: Begin Phase 1 (Parallel FFT infrastructure)
2. **Code Review**: Get feedback on parallel processing approach
3. **Testing**: Set up continuous performance benchmarking
4. **Documentation**: Update CLAUDE.md with optimization guidelines
5. **Deployment**: Gradual rollout with feature flags
