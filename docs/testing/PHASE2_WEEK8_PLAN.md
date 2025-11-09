# Phase 2 Week 8: Performance Regression Tests - PLAN

**Status**: <¯ Planning
**Date**: November 9, 2025
**Target Tests**: 100 tests
**Estimated Duration**: 4-5 hours implementation
**Prerequisites**: Week 7 complete (100% pass rate) 

## Overview

Week 8 focuses on performance regression testing to ensure the Auralis system maintains its high-performance characteristics (36.6x real-time factor) and that optimizations remain effective.

## Test Categories

### 1. Real-time Processing Performance (20 tests)

**Real-time Factor Validation** (5 tests):
- Test processing speed on short audio (10s)
- Test processing speed on medium audio (60s)
- Test processing speed on long audio (600s)
- Test real-time factor exceeds 20x threshold
- Test consistency across multiple runs

**Processing Latency** (5 tests):
- Test first-chunk latency (< 100ms)
- Test chunk processing time consistency
- Test streaming buffer latency
- Test preset switching latency
- Test playback start latency

**Throughput Testing** (5 tests):
- Test concurrent track processing (5 tracks)
- Test batch processing throughput
- Test queue processing rate
- Test sustained processing load
- Test memory usage during batch processing

**Optimization Effectiveness** (5 tests):
- Test Numba JIT speedup (40-70x envelope)
- Test NumPy vectorization speedup (1.7x EQ)
- Test parallel processing speedup (3.4x spectrum)
- Test overall pipeline speedup (2-3x)
- Test graceful fallback without Numba

### 2. Memory Usage & Profiling (20 tests)

**Memory Baseline** (5 tests):
- Test idle memory footprint
- Test single track memory usage
- Test memory growth per track
- Test memory ceiling with 100 tracks
- Test memory release after processing

**Memory Leaks Detection** (5 tests):
- Test repeated processing cycles (1000x)
- Test memory recovery after batch
- Test session cleanup effectiveness
- Test cache memory bounds
- Test buffer memory reuse

**Peak Memory** (5 tests):
- Test peak memory during processing
- Test memory during concurrent ops
- Test memory during large file (1GB)
- Test memory during analysis
- Test swap usage (should be zero)

**Memory Efficiency** (5 tests):
- Test memory per track ratio
- Test cache hit rate vs memory
- Test buffer pool effectiveness
- Test lazy loading effectiveness
- Test memory fragmentation

### 3. Cache Effectiveness (20 tests)

**Query Cache Performance** (5 tests):
- Test cache hit rate on repeated queries (>80%)
- Test cache speedup (50x+)
- Test cache invalidation correctness
- Test cache memory overhead (< 10MB)
- Test LRU eviction behavior

**Library Cache** (5 tests):
- Test track metadata cache hits
- Test album cache effectiveness
- Test artist cache performance
- Test playlist cache hits
- Test search result caching

**Audio Cache** (5 tests):
- Test waveform cache hits
- Test spectrum cache effectiveness
- Test fingerprint cache performance
- Test analysis cache hits
- Test cache persistence across restarts

**Cache Invalidation** (5 tests):
- Test invalidation on metadata update
- Test invalidation on file change
- Test invalidation on library scan
- Test selective invalidation
- Test cascade invalidation

### 4. Database Query Performance (20 tests)

**Query Execution Time** (5 tests):
- Test simple query (< 10ms)
- Test join query (< 50ms)
- Test aggregation query (< 100ms)
- Test full-text search (< 200ms)
- Test pagination query (< 20ms)

**Index Effectiveness** (5 tests):
- Test index usage on title search
- Test index usage on date range
- Test index usage on favorite filter
- Test composite index usage
- Test EXPLAIN plan validation

**Large Dataset Queries** (5 tests):
- Test query on 10k tracks
- Test query on 50k tracks
- Test query on 100k tracks
- Test pagination on large sets
- Test sorting on large sets

**Query Optimization** (5 tests):
- Test N+1 query prevention
- Test eager loading effectiveness
- Test query result caching
- Test batch loading performance
- Test connection pool usage

### 5. Optimization Validation (20 tests)

**Numba JIT Validation** (5 tests):
- Test envelope follower with Numba
- Test speedup vs pure Python
- Test correctness of JIT code
- Test Numba compilation time
- Test fallback when Numba unavailable

**Vectorization Validation** (5 tests):
- Test EQ vectorized processing
- Test spectrum vectorized processing
- Test SIMD utilization
- Test vectorization speedup
- Test numerical accuracy

**Parallel Processing** (5 tests):
- Test multi-core utilization
- Test thread pool efficiency
- Test process pool overhead
- Test parallel vs sequential speedup
- Test thread safety

**Algorithm Efficiency** (5 tests):
- Test FFT algorithm choice
- Test filter implementation efficiency
- Test resampling performance
- Test format conversion speed
- Test codec performance

## Implementation Strategy

### Phase 1: Performance Test Infrastructure (Day 1)
1. Create `tests/performance/` directory
2. Implement `tests/performance/conftest.py` with performance fixtures
3. Implement `tests/performance/helpers.py` with timing utilities
4. Add pytest markers for performance tests
5. Set up benchmarking infrastructure

### Phase 2: Real-time & Memory Tests (Day 2)
1. Implement `test_realtime_performance.py` (20 tests)
2. Implement `test_memory_profiling.py` (20 tests)
3. Run tests and validate thresholds

### Phase 3: Cache & Database Tests (Day 3)
1. Implement `test_cache_effectiveness.py` (20 tests)
2. Implement `test_database_performance.py` (20 tests)
3. Run tests and validate performance

### Phase 4: Optimization Validation (Day 4)
1. Implement `test_optimization_validation.py` (20 tests)
2. Run full test suite
3. Generate performance report
4. Document results

## Performance Thresholds

### Critical Thresholds (Must Pass)
- Real-time factor: **> 20x** (36.6x current baseline)
- First-chunk latency: **< 100ms**
- Simple query: **< 10ms**
- Cache hit rate: **> 80%**
- Memory per track: **< 50MB**

### Target Thresholds (Should Pass)
- Real-time factor: **> 30x**
- Numba speedup: **> 40x**
- Vectorization speedup: **> 1.5x**
- Cache speedup: **> 50x**
- Memory leak: **< 1MB per 1000 cycles**

### Stretch Thresholds (Nice to Have)
- Real-time factor: **> 40x**
- Cache hit rate: **> 90%**
- Memory per track: **< 30MB**
- Simple query: **< 5ms**

## Test Markers

Add to `pytest.ini`:
```ini
performance: Performance and benchmark tests
realtime: Real-time processing performance tests
memory: Memory usage and profiling tests
cache: Cache effectiveness tests
database: Database query performance tests
optimization: Optimization validation tests
benchmark: Long-running benchmark tests
```

## Success Criteria

-  All 100 tests implemented
-  90%+ pass rate on first run
-  All critical thresholds met
-  No performance regressions detected
-  Optimization effectiveness validated
-  Documentation complete

## Performance Benchmarks

### Baseline Performance (from PERFORMANCE_OPTIMIZATION_QUICK_START.md)
- **Real-time factor**: 36.6x (Iron Maiden - 232.7s in 6.35s)
- **Numba envelope speedup**: 40-70x
- **NumPy EQ speedup**: 1.7x
- **Parallel spectrum speedup**: 3.4x (for audio > 60s)
- **Overall pipeline speedup**: 2-3x

### Expected Results
- **All critical thresholds**: Pass
- **Most target thresholds**: Pass
- **Some stretch thresholds**: Pass
- **No regressions**: All current benchmarks maintained or improved

## Risks & Mitigation

**Risk 1**: Performance varies by hardware
- **Mitigation**: Use relative thresholds (speedup ratios), not absolute times

**Risk 2**: Tests may be flaky due to system load
- **Mitigation**: Run multiple iterations, use median values, set tolerances

**Risk 3**: Numba compilation affects first-run timing
- **Mitigation**: Warm up JIT before timing, test with pre-compiled functions

**Risk 4**: Memory profiling overhead
- **Mitigation**: Use lightweight profiling tools, separate profiling runs

## Next Steps After Week 8

1. **Week 9**: Compatibility & Integration Tests
2. **Week 10**: User Acceptance Tests (UAT)
3. **Phase 3**: Advanced testing and production readiness

## Implementation Notes

### Timing Utilities
```python
import time
from contextlib import contextmanager

@contextmanager
def timer():
    """Context manager for timing code blocks."""
    start = time.perf_counter()
    yield lambda: time.perf_counter() - start

def benchmark(func, iterations=10):
    """Benchmark function with multiple iterations."""
    times = []
    for _ in range(iterations):
        with timer() as get_time:
            func()
        times.append(get_time())
    return {
        'mean': sum(times) / len(times),
        'median': sorted(times)[len(times) // 2],
        'min': min(times),
        'max': max(times),
    }
```

### Memory Profiling
```python
import psutil
import gc

def measure_memory(func):
    """Measure memory usage of function."""
    gc.collect()
    process = psutil.Process()
    before = process.memory_info().rss / 1024 / 1024  # MB

    result = func()

    gc.collect()
    after = process.memory_info().rss / 1024 / 1024  # MB

    return result, after - before
```

### Performance Assertions
```python
def assert_realtime_factor(processing_time, audio_duration, threshold=20.0):
    """Assert real-time factor exceeds threshold."""
    rt_factor = audio_duration / processing_time
    assert rt_factor > threshold, \
        f"Real-time factor {rt_factor:.1f}x below threshold {threshold}x"

def assert_speedup(optimized_time, baseline_time, threshold=1.5):
    """Assert optimization achieves speedup threshold."""
    speedup = baseline_time / optimized_time
    assert speedup > threshold, \
        f"Speedup {speedup:.1f}x below threshold {threshold}x"
```

---

**Created**: November 9, 2025
**Status**: Planning Complete - Ready for Implementation
**Next**: Create test infrastructure and begin implementation
